---
bootstrapped_at: "2026-05-27T00:33:55Z"
architecture_mode: split
starter_id: frontend:nuxt,backend:fastapi
starter_name: Nuxt, FastAPI
project_name: adr-flow
language_family: multi
package_manager: frontend:pnpm, backend:uv
cwd_strategy: frontend:subdir-then-move, backend:native-cwd
bootstrapper_confidence: frontend:verified, backend:first-class
phase_3_status: ok
audit_command: frontend:npm audit --json (failed; pnpm audit supplemental), backend:pip-audit
---

## Hand-off

```yaml
project_name: adr-flow
architecture_mode: split
components:
  frontend:
    product_type: web
    starter_id: nuxt
    package_manager: pnpm
    hints:
      language_family: js
      deployment_target: vercel
      bootstrapper_confidence: verified
      quality_override: false
      path_taken: custom
      dev_tooling:
        formatter: prettier
        linter: eslint
        type_checker: typescript
  backend:
    product_type: api
    starter_id: fastapi
    package_manager: uv
    hints:
      language_family: python
      deployment_target: fly
      bootstrapper_confidence: first-class
      quality_override: false
      path_taken: standard
      dev_tooling:
        formatter: ruff
        linter: ruff
        type_checker: ty
hints:
  team_size: solo
  ci_provider: github-actions
  ci_default_flow: auto-deploy-on-merge
  path_taken: custom
  self_check_answers: null
  has_auth: true
  has_payments: false
  has_realtime: false
  has_ai: true
  has_background_jobs: true
```

## Why this stack

ADR Flow is a hosted web app with email/password auth, per-user ADR storage, and one-shot AI review on publish — a natural split between a Nuxt UI and a Python API. Nuxt (Vue, SSR via Nitro) fits a markdown editor, card-based history, and status-driven flows on a tight three-week, after-hours MVP; Vercel is the default deploy path. FastAPI carries Pydantic-typed request/response models, OpenAPI for agent-friendly boundaries, and async-friendly handlers for review jobs triggered from `draft` → `in_review`, with Fly.io as the API home. GitHub Actions auto-deploys on merge. Auth and persistence live in the backend; the frontend calls the API — no realtime collaboration in MVP. Ruff + ty on the API and Prettier/ESLint/TypeScript on the UI keep both sides explicit and convention-aligned for solo development.

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

| Scope | formatter | linter | type_checker | status |
| ----- | --------- | ------ | ------------ | ------ |
| frontend | prettier installed; `.prettierrc` added; `format` script | eslint installed; `lint` script | typescript installed; `typecheck` script | ok (pnpm needed Node 22 PATH) |
| backend | ruff installed; `[tool.ruff]` appended | ruff (shared dep) | ty installed | ok |

## Pre-commit

User: **Yes — install hooks (Recommended)**.

| Hook id | tool | scope | files filter | status |
| ------- | ---- | ----- | ------------ | ------ |
| prettier | prettier | frontend | `^frontend/` | added |
| ruff | ruff | backend | `^backend/` | added |
| ruff-format | ruff | backend | `^backend/` | added |
| frontend-eslint | eslint | frontend | `^frontend/` | added (local) |
| frontend-typecheck | typescript | frontend | `^frontend/` | added (local) |
| backend-ty | ty | backend | `^backend/` | added (local) |
| trailing-whitespace | pre-commit-hooks | repo | (existing) | kept |

`pre-commit install`: ok (`uv run --directory backend pre-commit install`). `pre-commit` devDep added in `backend/`.

## Devcontainer

| Sub-step | Result | Detail |
| -------- | ------ | ------ |
| detection | detected | `.devcontainer/devcontainer.json`, `Dockerfile` |
| gate | applied | user accepted setup |
| postcreate | append | `.devcontainer/post-create.sh` — `frontend` pnpm install, `backend` uv sync |
| extensions catalog | append | js (eslint, prettier, volar) + python (python, pylance, ruff) |
| extensions extra | append | `humao.rest-client` (.http files) |
| services | append | redis:7-alpine:6379, postgres:16-alpine:5432 in `.devcontainer/docker-compose.yml` |

## Package manager security

User: **Yes — 7-day cooldown (Recommended)**.

| Scope | package_manager | action | path | result |
| ----- | --------------- | ------ | ---- | ------ |
| frontend | pnpm | merged | frontend/pnpm-workspace.yaml | minimumReleaseAge: 10080 |
| backend | uv | merged | backend/pyproject.toml | exclude-newer = "7 days" |

## Justfile

| Scope | recipe | discovered command | status |
| ----- | ------ | ------------------ | ------ |
| frontend | dev-frontend | cd frontend && pnpm run dev | written |
| backend | dev-backend | cd backend && uv run uvicorn main:app --reload | written |
| root | dev | dev-frontend & dev-backend (parallel) | written |

Install [just](https://github.com/casey/just#installation) on the host to run recipes; not installed by bootstrap.

## Post-scaffold audit

### frontend

**Tool**: `npm audit --json`
**Status**: failed to run
**Reason**: ENOLOCK — this component uses `pnpm` (`pnpm-lock.yaml`); `npm audit` requires `package-lock.json`.

**Supplemental**: `pnpm audit --json` (Node 22 PATH) — exit 0.

**Summary**: 0 CRITICAL, 0 HIGH, 0 MODERATE, 0 LOW (from pnpm `metadata.vulnerabilities`).
**Direct vs transitive**: not distinguished by pnpm audit JSON summary.

#### CRITICAL findings

(none)

#### HIGH findings

(none)

#### MODERATE findings

(none)

#### LOW / INFO findings

(none)

### backend

**Tool**: `pip-audit --format json` (invoked as `uvx pip-audit --format json`; `pip-audit` not on PATH)
**Summary**: 0 CRITICAL, 0 HIGH, 0 MODERATE, 0 LOW
**Direct vs transitive**: not distinguished by pip-audit JSON output

#### CRITICAL findings

(none)

#### HIGH findings

(none)

#### MODERATE findings

(none)

#### LOW / INFO findings

(none)

## Hints recorded but not acted on

| Hint | Value |
| ---- | ----- |
| bootstrapper_confidence | frontend: verified; backend: first-class |
| quality_override | false per component |
| path_taken | frontend: custom; backend: standard; shared: custom |
| self_check_answers | null |
| team_size | solo |
| deployment_target | frontend: vercel; backend: fly |
| ci_provider | github-actions |
| ci_default_flow | auto-deploy-on-merge |
| has_auth | true |
| has_payments | false |
| has_realtime | false |
| has_ai | true |
| has_background_jobs | true |

## Next steps

Next: a future skill will set up agent context (CLAUDE.md, AGENTS.md). For now, your project is scaffolded and verified — happy hacking.

Useful manual steps in the meantime:

- Install [just](https://github.com/casey/just#installation) and run `just dev` from the repo root (split: `just dev-frontend`, `just dev-backend`, or aggregate `just dev`).
- `git init` (if you have not already) to start your own repo history.
- Review any `.scaffold` siblings the conflict policy created and decide which version of each file to keep.
- Address audit findings per your project's risk tolerance — the full breakdown is in this log.
- If release-age policy was applied, run `pnpm install` / `uv lock` when ready to refresh lockfiles under the new constraint.
- Review devcontainer compose credentials (`dev`/`dev`) before sharing the repo.
- If pre-commit was installed, run `pre-commit run --all-files` once after `git init` to validate hooks.
- Optional: run `/agents` to generate `AGENTS.md` for AI coding agents in this repo.
