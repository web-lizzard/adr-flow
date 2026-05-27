# Repository Guidelines

ADR Flow is a split-stack MVP: Nuxt 4 UI in `frontend/` and a FastAPI API in `backend/`, with product and stack context in `context/foundation/`. Auth, persistence, and AI review belong in the backend; the frontend calls the API only.

## Hard Rules

- Do not add setup steps to `.devcontainer/post-create.sh` or `initialize.sh` — add numbered `*.sh` scripts under `.devcontainer/post-create.d/` or `initialize.d/` per @.cursor/rules/devcontainer-hooks.mdc.
- Do not commit a project `.cursor/permissions.json` when using `ASSETS_REPO`; the allowlist comes from project-assets via initialize (see @README.md).
- Run hooks before pushing: `pre-commit run --all-files` (trailing whitespace, Prettier on `frontend/`, Ruff on `backend/`, ESLint, `tsc`, `ty`).
- Respect release-age policy: `frontend/pnpm-workspace.yaml` (`minimumReleaseAge: 10080`) and `backend/pyproject.toml` (`exclude-newer = "7 days"`). Refresh locks with `pnpm install` / `uv lock` when bumping deps.
- Local dev: `just dev` (split: `just dev-frontend`, `just dev-backend`) per @Justfile.

## Project Structure

| Path | Role |
|------|------|
| `frontend/` | Nuxt app (`app/`, `nuxt.config.ts`) |
| `backend/` | FastAPI entry at `main.py`, deps via `uv` |
| `context/foundation/` | PRD, tech stack, shaping notes |
| `context/changes/` | Bootstrap handoff and verification logs |
| `Justfile` | Root dev orchestration |

Deeper product and architecture: @context/foundation/prd.md, @context/foundation/tech-stack.md, @context/changes/bootstrap-verification/verification.md.

## Build, Test, and Development

- `just dev` — frontend and backend together (requires [just](https://github.com/casey/just#installation) on the host).
- `just dev-frontend` / `just dev-backend` — `pnpm run dev` (Nuxt) or `uv run uvicorn main:app --reload`.
- `cd frontend && pnpm run build` — production Nuxt build.
- `cd frontend && pnpm run lint` / `pnpm run format` / `pnpm run typecheck` — ESLint, Prettier, TypeScript.
- `cd backend && uv run ruff check .` / `uv run ruff format .` / `uv run ty check` — Python lint, format, types.

No automated test suite is configured yet; add tests beside the component you change when introducing a runner.

## Coding Style

- **Frontend:** TypeScript, ESLint (@frontend/eslint.config.mjs), Prettier (@frontend/.prettierrc). Nuxt 4 conventions under `frontend/app/`.
- **Backend:** Python 3.12+, Ruff line length 88 (@backend/pyproject.toml). Keep request/response models explicit for OpenAPI consumers.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commits prefixes: `feat`, `chore`, `docs` with optional scopes (e.g. `chore(bootstrap): …`). PRs target `main` on `github.com:web-lizzard/adr-flow.git`. CI workflows are not in-repo yet; treat pre-commit as the local gate until GitHub Actions land per @context/foundation/tech-stack.md.

## Security & Configuration

- Copy `.env.example` to `.env` for `ASSETS_REPO` and devcontainer asset fetch (@README.md).
- Devcontainer Postgres uses placeholder `dev`/`dev` — change before sharing the repo (@context/changes/bootstrap-verification/verification.md).
