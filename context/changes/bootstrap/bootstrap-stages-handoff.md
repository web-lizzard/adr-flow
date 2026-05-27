---
schema_version: 1
pipeline: bootstrap-v1
tech_stack_handoff: context/foundation/tech-stack.md
bootstrapped_at: "2026-05-27T00:33:55Z"
architecture_mode: split
project_name: adr-flow
stages:
  init:
    status: ok
    at: "2026-05-27T00:33:55Z"
    notes: ""
  scaffold:
    status: ok
    at: "2026-05-27T00:40:00Z"
    notes: "frontend: augmented nuxi (--template minimal, Node 22 PATH); pnpm allowBuilds remediation"
  dev_quality:
    status: pending
    at: null
    notes: ""
  devcontainer:
    status: pending
    at: null
    notes: ""
  repo_conventions:
    status: pending
    at: null
    notes: ""
  verify:
    status: pending
    at: null
    notes: ""
phase_scaffold_status: ok
resolved:
  mode: split
  components:
    frontend:
      starter_id: nuxt
      package_manager: pnpm
      cwd_strategy: subdir-then-move
      language_family: js
      product_type: web
      card_name: Nuxt
      dev_tooling:
        formatter: prettier
        linter: eslint
        type_checker: typescript
    backend:
      starter_id: fastapi
      package_manager: uv
      cwd_strategy: native-cwd
      language_family: python
      product_type: api
      card_name: FastAPI
      dev_tooling:
        formatter: ruff
        linter: ruff
        type_checker: ty
gates:
  user_confirmed_init: true
  devcontainer_detection: not_run
---

## Pipeline status

| Stage | Status |
| ----- | ------ |
| init | ok |
| scaffold | ok |
| dev_quality | pending |
| devcontainer | pending |
| repo_conventions | pending |
| verify | pending |
| phase_scaffold_status | ok |

## Init

**Hand-off received (split):**

- Mode: split
- Project name: adr-flow
- Components:
  - frontend: nuxt (js, pm=pnpm, deploy=vercel)
  - backend: fastapi (python, pm=uv, deploy=fly)
- Shared hints: team=solo, CI=github-actions/auto-deploy-on-merge, flags=has_auth, has_ai, has_background_jobs
- Dev tooling: frontend — prettier / eslint / typescript; backend — ruff / ruff / ty

**User confirm:** Proceed.

**Resolution:** Registry lookup ok for `nuxt` and `fastapi`. `cwd_strategy`: frontend `subdir-then-move` (nuxt), backend `native-cwd` (fastapi). Populated-cwd guard: no scaffold fingerprint files at repo root or under `frontend/` / `backend/`.

## Pre-scaffold verification

| Component | npm package | npm modified | npm severity | GitHub repo | pushed_at | repo severity | notes |
| --------- | ----------- | ------------ | -------------- | ----------- | --------- | --------------- | ----- |
| backend | n/a | n/a | n/a | tiangolo/fastapi (inferred) | unavailable | n/a | `docs_url` not GitHub; `gh api` failed (not authenticated or offline) |
| frontend | nuxi | 2026-05-11 | fresh (v3.35.2) | nuxt/nuxt | unavailable | n/a | `gh api` failed; npm recency fresh |

## Scaffold log

### backend (surface.key: backend)

| Field | Value |
| ----- | ----- |
| starter_id | fastapi |
| cwd_strategy | native-cwd |
| non_interactive | registry (uv init/add) |
| exit | 0 |

**Pre (card):** `uv pip install fastapi uvicorn` — skipped (no venv; non-blocking).

**Command:** `cd backend && CI=true uv init . && uv add fastapi uvicorn`

**Result:** native-cwd into `backend/`. Files: `pyproject.toml`, `main.py`, `uv.lock`, `.venv/`, `.python-version`, `README.md`.

### frontend (surface.key: frontend)

| Field | Value |
| ----- | ----- |
| starter_id | nuxt |
| cwd_strategy | subdir-then-move |
| non_interactive | augmented (`--template minimal`, `PATH` → Node v22.22.3) |
| remediation_type | pnpm_workspace_allow_builds |
| remediation_status | applied |
| exit | 0 (merge after manual completion; nuxi hung on optional modules prompt after install) |

**Resolved command (first attempt):** `npx nuxi init .bootstrap-scaffold --packageManager pnpm --install --gitInit` — exit 1 (interactive template prompt; Node v20).

**§ (f) retry:** same + `--template minimal --force` + Node 22 PATH — exit 1 (`ERR_PNPM_IGNORED_BUILDS`).

**PM remediation:** `frontend/.bootstrap-scaffold/pnpm-workspace.yaml` `allowBuilds` for `@parcel/watcher`, `esbuild`; `pnpm install` exit 0.

**Retry:** nuxi with Node 22 PATH — deps + git init OK; killed at optional “install modules” prompt.

**Merge:** subdir-then-move from `.bootstrap-scaffold/` → `frontend/`; temp dir removed. Conflicts: none. `.gitignore` moved silently.

**Result:** Nuxt 4 minimal app in `frontend/` with `node_modules/`, component `.git/`.

## Dev tooling

_Not run yet._

## Pre-commit

_Not run yet._

## Devcontainer

_Not run yet._

## Package manager security

_Not run yet._

## Justfile

_Not run yet._

## Post-scaffold audit

_Not run yet._

## Hints not acted on

v1 does not automate the following from the tech-stack hand-off:

- `bootstrapper_confidence` (frontend: verified; backend: first-class)
- `quality_override` (false per component)
- `path_taken` (frontend: custom; backend: standard; shared: custom)
- `self_check_answers` (null)
- `team_size` (solo)
- `deployment_target` (frontend: vercel; backend: fly)
- `ci_provider` / `ci_default_flow` (github-actions / auto-deploy-on-merge)
- `has_auth` (true)
- `has_payments` (false)
- `has_realtime` (false)
- `has_ai` (true)
- `has_background_jobs` (true)

### Why this stack (excerpt)

ADR Flow is a hosted web app with email/password auth, per-user ADR storage, and one-shot AI review on publish — a natural split between a Nuxt UI and a Python API. Nuxt (Vue, SSR via Nitro) fits a markdown editor, card-based history, and status-driven flows on a tight three-week, after-hours MVP; Vercel is the default deploy path. FastAPI carries Pydantic-typed request/response models, OpenAPI for agent-friendly boundaries, and async-friendly handlers for review jobs triggered from `draft` → `in_review`, with Fly.io as the API home. GitHub Actions auto-deploys on merge. Auth and persistence live in the backend; the frontend calls the API — no realtime collaboration in MVP. Ruff + ty on the API and Prettier/ESLint/TypeScript on the UI keep both sides explicit and convention-aligned for solo development.

## Next stage pointer

Next: /bootstrap-dev-quality
