---
project: adr-flow
researched_at: 2026-05-27
recommended_platform: GCP Cloud Run
runner_up: Fly.io
context_type: mvp
tech_stack:
  language: TypeScript (frontend), Python 3.12+ (backend)
  framework: Nuxt 4 (frontend), FastAPI (backend)
  runtime: Node.js (frontend), uvicorn (backend)
data_layer:
  database: Self-hosted PostgreSQL on GCE e2-micro (event store, source of truth)
  cache: In-app asyncio event dispatch (MVP); Redis on GCE (scale-up path)
  ai: OpenRouter (external, pay-per-use)
architecture:
  event_sourcing: true
  event_store: PostgreSQL (append-only events table)
  event_dispatch: asyncio.TaskGroup (MVP) → Redis Streams (production)
  background_jobs: asyncio.TaskGroup with CPU-always-allocated mode
---

## Recommendation

**Deploy both Nuxt 4 frontend and FastAPI backend on GCP Cloud Run, with self-hosted PostgreSQL on a GCE e2-micro instance and in-app event dispatch via asyncio.TaskGroup.**

Cloud Run scores highest on the dimension that matters most for an MVP with a production future: zero migration cost when scaling up. The free tier (180K vCPU-seconds, 360K GiB-seconds, 2M requests/month) covers MVP traffic at $0/month compute. "CPU always allocated" mode (GA) supports asyncio.TaskGroup background tasks — the AI review job runs after the HTTP response without a separate worker. Self-hosted Postgres on a GCE e2-micro eliminates the double cold-start problem (Cloud Run + Neon) and provides sub-millisecond query latency via Direct VPC Egress. The event-sourced architecture stores events in Postgres as the source of truth; the in-app asyncio queue dispatches them. On restart, unprocessed events replay from the database — no Redis dependency at MVP. Redis Streams can be added on the same GCE VM when multi-instance dispatch is needed.

## Platform Comparison

GCP Cloud Run was evaluated against the five agent-friendly criteria and compared with Fly.io (the previous recommendation) and Railway.

| Criterion | GCP Cloud Run | Fly.io | Railway |
|---|---|---|---|
| CLI-first maintenance | Pass | Pass | Pass |
| Managed / serverless | Pass | Pass | Pass |
| Agent-accessible docs | Partial | Pass | Pass |
| Stable deploy API | Pass | Pass | Pass |
| MCP / Integration | Pass (GA, Next '26) | Fail | Pass |
| Stack compatibility | Full | Full | Full |
| Scale-to-zero | Yes (`--min-instances=0`) | Yes (`auto_stop_machines`) | No |
| Est. monthly cost (compute) | $0 (free tier) | $3-8 | $20-40 |
| Background task support | Yes (CPU always allocated) | Implicit (machine stays on) | Yes (always-on) |
| MVP → production path | Zero migration | Dockerfile portable, config rework | Dockerfile portable |

**Interview constraints applied:**

- Q1 (no persistent connections, asyncio.TaskGroup for background) — no platforms filtered.
- Q2 (balanced, leaning cost-conscious) — penalized Railway ($20-40/month), favored Cloud Run ($0).
- Q3 (no platform familiarity) — no tie-breaking bias.
- Q4 (single region) — no edge advantage needed; deprioritized Fly.io multi-region strength.
- Q5 (Postgres as event store, Redis as dispatch layer, OpenRouter for LLM) — favored self-hosted data layer on GCP for co-location and cost.

### Shortlisted Platforms

#### 1. GCP Cloud Run (Recommended)

Cloud Run runs both Nuxt and FastAPI as containers with `--min-instances=0` for scale-to-zero. The free tier covers MVP traffic completely. "CPU always allocated" mode keeps the CPU active between requests, enabling asyncio.TaskGroup to process events after the HTTP response is sent. `gcloud run deploy --source .` builds from source without a Dockerfile (Cloud Build, 120 free build-minutes/day). Direct VPC Egress (GA, free) connects Cloud Run to a GCE instance running Postgres with sub-millisecond latency. All critical features are GA. The `gcloud` CLI handles the full operational loop: deploy, rollback, logs, secrets, traffic splitting.

**Weakness:** More initial setup friction than Fly.io (GCP project, billing, IAM). `gcloud` CLI is verbose. Docs not available as markdown on GitHub (no `llms.txt`).

#### 2. Fly.io (Runner-up)

Fly.io offers the simplest DX — `flyctl` is terse, deploys are fast, scale-to-zero costs $3-8/month at MVP traffic. Docker containers provide portability. However, Fly.io has no native way to co-locate a self-hosted database in the same network at $0 cost (Fly Postgres is deprecated, and Fly Machines are not free-tier). Moving to GCP later requires translating `fly.toml` configs and migrating secrets — estimated 4-8 hours of rework.

**Weakness:** No MCP server. No free tier. Migration to production on GCP requires rework. Self-hosted data layer is harder to co-locate.

#### 3. Railway (Third option)

Railway has the best DX and MCP integration. Nixpacks auto-detects both Nuxt and FastAPI. PR preview environments work out of the box. However, two always-on services cost $20-40/month regardless of traffic — 3-10x more expensive than Cloud Run for an after-hours MVP. No scale-to-zero.

**Weakness:** No scale-to-zero. Cost is prohibitive for a solo, low-traffic MVP.

## Data Layer Configuration

### PostgreSQL: Self-hosted on GCE e2-micro

| Option | Monthly Cost | Ops Overhead | Cold Start | Latency from Cloud Run | Event Store Fit |
|---|---|---|---|---|---|
| **Self-hosted (GCE e2-micro)** ✓ | $0 (US) / $5-7 (EU) | Moderate | None (always on) | <1ms (same VPC) | Excellent |
| Neon free tier | $0 | None | 0.5-3s | 10-20ms (cross-cloud) | Good (0.5 GB limit) |
| Cloud SQL (db-f1-micro) | $9-12 | None | None | <1ms (Auth Proxy) | Excellent |

**Why self-hosted wins for this project:**

- **No cold start chain.** Neon's 0.5-3s wake-up stacks on top of Cloud Run's 3-8s cold start. Self-hosted Postgres on GCE runs 24/7, eliminating the database cold start entirely.
- **Event store growth.** An event-sourced application appends events continuously. Neon's 0.5 GB free-tier storage limit could fill in weeks depending on event granularity — hitting a $19/month cliff (Launch plan). The GCE e2-micro comes with 10 GB free persistent disk (30 GB free tier total).
- **Sub-millisecond queries.** Same-VPC latency via Direct VPC Egress vs. 10-20ms cross-cloud to Neon. For event replay on startup, this difference compounds across hundreds of events.
- **Cost parity.** Both options are $0/month in US regions. In Europe, self-hosted costs ~$5-7/month vs. Neon's $0 free tier, but Neon's $19/month Launch plan is the realistic production cost when storage exceeds 0.5 GB.

**Trade-off accepted:** Manual backup responsibility (mitigated with `pg_dump` cron to Cloud Storage) and single point of failure (acceptable for MVP; mitigate with Cloud SQL migration when justified).

### Event Dispatch: In-app asyncio.TaskGroup (MVP)

| Option | Monthly Cost | Redis Streams | Multi-instance | Durability | Production Path |
|---|---|---|---|---|---|
| **In-app asyncio.TaskGroup** ✓ | $0 | N/A | No | Replay from Postgres | → Redis Streams |
| Self-hosted Redis (GCE) | $0 (shared VM) | Full | Yes | AOF persistence | → Memorystore |
| Upstash Redis | $0 (free tier) | Yes | Yes | Multi-zone replication | → Memorystore |
| GCP Memorystore | ~$35-42 | Full | Yes | Managed | Already there |

**Why in-app dispatch wins for MVP:**

- **Postgres is the event store.** Events are appended to a Postgres table as the source of truth. The dispatch layer only needs to notify handlers that a new event arrived. If the dispatch queue is lost (scale-to-zero, restart), the app replays unprocessed events from Postgres on startup.
- **Fewest moving parts.** No Redis to provision, configure, or pay for. One fewer service to manage.
- **Cloud Run supports it.** "CPU always allocated" mode keeps the CPU active after the response is sent. asyncio.TaskGroup tasks continue processing until the instance scales down. For a 10-30 second AI review job, the instance stays alive long enough.
- **Clear upgrade path.** When multi-instance dispatch is needed, add Redis on the same GCE e2-micro VM (or Upstash). The event dispatch interface stays the same — only the transport changes from asyncio.Queue to Redis Streams.

**Constraint:** Cloud Run must be limited to `--max-instances=1` for MVP to prevent duplicate event processing. This is acceptable at MVP traffic.

## Anti-Bias Cross-Check: GCP Cloud Run + Self-hosted Postgres + In-app Dispatch

### Devil's Advocate — Weaknesses

1. **GCE e2-micro is extremely constrained.** 0.25 vCPU (burstable), 1 GB RAM. Postgres gets ~512 MB after OS overhead. If the event store grows or queries become complex, the VM will thrash.
2. **No automated backups for self-hosted Postgres.** Manual `pg_dump` cron to Cloud Storage required. If misconfigured, the event store (source of truth) has zero recovery beyond the persistent disk.
3. **Single point of failure.** No replication, no failover. Disk corruption or host hardware failure means data loss.
4. **asyncio.TaskGroup dispatch doesn't survive scale-to-zero.** Events queued in-memory are lost when Cloud Run scales down. The startup replay mechanism must be correct and idempotent.
5. **GCE free tier is US-only.** Free e2-micro is only available in `us-west1`, `us-central1`, `us-east1`. European regions cost ~$5-7/month.

### Pre-Mortem — How This Could Fail

The solo developer deployed Cloud Run + GCE e2-micro Postgres + asyncio.TaskGroup. Initial costs: $0/month, events flowing, AI reviews completing. But by week three, the e2-micro's 1 GB RAM meant Postgres ran with minimal shared buffers. As the event store grew, startup event replay scans slowed from 5 to 30 seconds. The micro VM's burstable CPU couldn't sustain index maintenance during write bursts. Meanwhile, the TaskGroup dispatch had a subtle bug: an unhandled exception in one AI review handler crashed the entire TaskGroup, taking down processing for all in-flight events — something a dedicated job queue with per-task isolation would have handled natively. The final straw came after three weeks without backups — the `pg_dump` cron had silently failed. A Cloud Run deployment burst overwhelmed the micro VM's connection limit, Postgres crashed, WAL corrupted. Event store gone. No backups, no replicas, no recovery point.

### Unknown Unknowns

- **GCE e2-micro CPU bursting has credit limits.** Under sustained load, the VM throttles to 0.25 vCPU mid-operation. Postgres query latency spikes unpredictably during event write bursts.
- **Cloud Run instance count isn't deterministic during deploys.** Even with `--max-instances=1`, rolling updates briefly run two instances. Two instances replaying events simultaneously cause duplicate processing without idempotency guards.
- **`gcloud run deploy --source .` uses Cloud Build internally.** Old images in Artifact Registry accumulate at $0.10/GB/month without lifecycle cleanup policies.
- **Standard persistent disk IOPS scales with disk size.** A 10 GB disk gets ~3 IOPS read/write — the minimum. Postgres WAL writes on an event store can bottleneck. SSD persistent disk ($0.17/GB/month) helps.
- **Direct VPC Egress IP consumption.** Each Cloud Run instance takes a VPC IP. Requires correct subnet sizing from the start.

## Operational Story

How GCP Cloud Run operates day to day for ADR Flow.

- **Preview deploys**: Deploy a tagged revision: `gcloud run deploy backend --tag pr-123 --no-traffic`. Creates a dedicated URL (`pr-123---backend-xxxxx.run.app`) without affecting production traffic. Tag-based routing is GA. Clean up after merge: `gcloud run revisions delete`.
- **Secrets**: `gcloud run deploy --set-secrets=DATABASE_URL=db-url:latest,OPENROUTER_API_KEY=api-key:latest`. Secrets stored in Secret Manager, encrypted at rest, injected as env vars. Rotation: update the secret version, redeploy. First 6 active versions free, then $0.06/version/month.
- **Rollback**: `gcloud run services update-traffic backend --to-revisions=REVISION=100` routes all traffic to a previous revision. Typical time-to-revert: 10-30 seconds. Caveat: database schema migrations (event store schema changes) do not roll back automatically — use explicit down-migration scripts.
- **Approval**: All `gcloud` commands can be run by an agent unattended. Destructive operations (`gcloud run services delete`, secret deletion, GCE instance termination) should require explicit human confirmation in agent workflows.
- **Logs**: `gcloud run services logs read backend --region=REGION` for runtime logs. `gcloud logging read "resource.type=cloud_run_revision"` for structured log queries. For the GCE instance: `gcloud compute ssh VM -- journalctl -u postgresql`.

## Risk Register

| Risk | Source | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| GCE e2-micro runs out of RAM under event store growth | Devil's advocate | Medium | Medium | Monitor `free -m` via cron; upgrade to e2-small ($13/month) when approaching limits; index event store columns proactively |
| No automated Postgres backups → data loss | Devil's advocate | Medium | High | Set up `pg_dump` cron (daily) to Cloud Storage on day 1; verify with `gsutil ls` weekly; document recovery procedure |
| Single point of failure — disk corruption or host failure | Devil's advocate | Low | High | Enable GCE persistent disk snapshots (scheduled, ~$0.05/GB/month); test restore procedure once; migrate to Cloud SQL when justified |
| asyncio.TaskGroup crash cascades to all in-flight events | Pre-mortem | Medium | Medium | Wrap each task in try/except with per-event error logging; implement idempotent event handlers; add processed_at timestamp to events table |
| Duplicate event processing during Cloud Run rolling updates | Unknown unknowns | Low | Medium | Add idempotency keys to event handlers; use `processed_at IS NULL` filter for replay queries; consider `--max-instances=1` for MVP |
| Standard persistent disk IOPS bottleneck on event writes | Unknown unknowns | Low | Low | Start with SSD persistent disk (10 GB = $1.70/month) instead of standard; monitor disk latency via `iostat` |
| Artifact Registry storage accumulates silently | Unknown unknowns | Low | Low | Set up lifecycle policy: `gcloud artifacts docker images delete` for images older than 30 days; or use Artifact Registry cleanup policies |
| Cloud Run cold start + app startup event replay > 10s | Pre-mortem | Medium | Medium | Optimize container image (slim base, multi-stage build); limit replay to last N unprocessed events; add startup health check with sufficient timeout |
| GCE free tier US-only — EU deployment costs ~$5-7/month | Unknown unknowns | N/A | Low | Budget $5-7/month for EU; or start in US with higher DB latency until traffic justifies EU spend |
| CPU burst throttling on e2-micro during write spikes | Unknown unknowns | Medium | Low | Keep event payloads small; batch writes where possible; upgrade to e2-small if throttling causes visible latency |

## Getting Started

1. **Create a GCP project and enable APIs:**
   ```bash
   gcloud projects create adr-flow --name="ADR Flow"
   gcloud config set project adr-flow
   gcloud services enable run.googleapis.com \
     compute.googleapis.com \
     secretmanager.googleapis.com \
     cloudbuild.googleapis.com \
     artifactregistry.googleapis.com
   ```

2. **Provision the GCE e2-micro for Postgres:**
   ```bash
   gcloud compute instances create adr-flow-db \
     --zone=us-central1-a \
     --machine-type=e2-micro \
     --boot-disk-size=10GB \
     --boot-disk-type=pd-ssd \
     --image-family=debian-12 \
     --image-project=debian-cloud \
     --tags=postgres

   # SSH in and install Postgres
   gcloud compute ssh adr-flow-db --zone=us-central1-a
   # On the VM:
   sudo apt update && sudo apt install -y postgresql-15
   sudo -u postgres psql -c "CREATE USER adrflow WITH PASSWORD 'CHANGE_ME';"
   sudo -u postgres psql -c "CREATE DATABASE adrflow OWNER adrflow;"
   ```

3. **Set up networking (Direct VPC Egress):**
   ```bash
   # Allow Cloud Run to reach the GCE instance on port 5432
   gcloud compute firewall-rules create allow-cloud-run-to-postgres \
     --direction=INGRESS \
     --action=ALLOW \
     --rules=tcp:5432 \
     --source-ranges=0.0.0.0/0 \
     --target-tags=postgres \
     --network=default
   ```

4. **Deploy the backend (FastAPI):**
   ```bash
   cd backend
   gcloud run deploy adr-flow-api \
     --source . \
     --region=us-central1 \
     --min-instances=0 \
     --max-instances=1 \
     --cpu-boost \
     --no-cpu-throttling \
     --set-secrets=DATABASE_URL=db-url:latest,OPENROUTER_API_KEY=openrouter-key:latest \
     --vpc-egress=all-traffic \
     --network=default \
     --subnet=default
   ```
   `--no-cpu-throttling` enables "CPU always allocated" mode for asyncio.TaskGroup background tasks. `--cpu-boost` provides extra CPU during cold starts.

5. **Deploy the frontend (Nuxt 4):**
   ```bash
   cd frontend
   gcloud run deploy adr-flow-web \
     --source . \
     --region=us-central1 \
     --min-instances=0 \
     --max-instances=2 \
     --cpu-boost \
     --set-env-vars=API_BASE_URL=https://adr-flow-api-xxxxx.run.app
   ```

6. **Set up Postgres backups (on the GCE VM):**
   ```bash
   # Install gsutil and create a backup bucket
   gcloud storage buckets create gs://adr-flow-backups --location=us-central1

   # Cron job for daily pg_dump (add to /etc/cron.d/pg-backup)
   # 0 3 * * * postgres pg_dump -Fc adrflow | gsutil cp - gs://adr-flow-backups/adrflow-$(date +\%Y\%m\%d).dump
   ```

## Migration Path

When ADR Flow outgrows the MVP configuration:

- **Postgres → Cloud SQL**: `pg_dump` from GCE, `pg_restore` to Cloud SQL. Switch to Cloud SQL Auth Proxy connection. Estimated effort: 1-2 hours. Trigger: when manual backup management becomes a risk, or when the e2-micro is resource-constrained.
- **In-app dispatch → Redis Streams**: Install Redis on the same GCE e2-micro (or add Upstash/Memorystore). Replace asyncio.Queue with Redis Streams consumer. The event store in Postgres stays unchanged. Estimated effort: 2-4 hours. Trigger: when `--max-instances=1` becomes a bottleneck.
- **GCE e2-micro → e2-small/medium**: `gcloud compute instances set-machine-type adr-flow-db --machine-type=e2-small`. Requires a brief VM restart. Trigger: when RAM or CPU throttling is observed.
- **Cloud Run → GKE/Cloud Run fully managed**: Same Dockerfiles, different orchestration. Trigger: when you need custom networking, GPU access, or multi-service mesh.

## Out of Scope

The following were not evaluated in this research:
- Docker image configuration (Dockerfiles for Nuxt and FastAPI)
- CI/CD pipeline setup (GitHub Actions workflows)
- Production-scale architecture (multi-region, HA, DR)
- Domain and DNS configuration
- SSL/TLS certificate management (handled automatically by Cloud Run)
- Event sourcing schema design (events table structure, projections)
