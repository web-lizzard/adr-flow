# project-template

## Dev container: project assets

On **Rebuild Container**, `initialize.sh` runs on the **host** (before the container starts) and executes every `*.sh` script in `initialize.d/` in sorted order:

1. **`10-fetch-assets-skills.sh`** — clones `ASSETS_REPO` into `.devcontainer/.project-assets-cache`, then installs `.cursor/skills/` into this workspace (gitignored).
2. **`20-fetch-assets-permissions.sh`** — copies `.cursor/permissions.json` from that cache into `.devcontainer/.permissions-cache/permissions.json` (for the dev container only).
3. **`30-cleanup-project-assets-cache.sh`** — removes the git clone cache.

Helpers live in `initialize.d/lib/` (not run by `initialize.sh`).

The permissions file is bind-mounted into the container at **`~/.cursor/permissions.json`**. It is **not** installed on the host. Do not keep a project `.cursor/permissions.json` in this repo if you use `ASSETS_REPO` — it used to override the full allowlist from project-assets.

### Setup

1. Copy `.env.example` to `.env` and set `ASSETS_REPO` to an SSH URL (e.g. `git@github.com:your-org/cursor-project-assets.git`).
2. Put the real allowlist in **`ASSETS_REPO`** at `.cursor/permissions.json`.
3. Ensure your host SSH agent can access that repo (`ssh-add -l`, `ssh -T git@github.com`).
4. Rebuild the dev container.

The assets repo should include at least:

- `.cursor/skills/` — Cursor agent skills
- `.cursor/permissions.json` — Cursor auto-run allowlist (canonical copy for all projects)

Default sparse-checkout path is `.cursor` (override with `ASSETS_SPARSE_PATH` in `.env`).

If `ASSETS_REPO` is unset or the clone fails, permissions cache is `{}` and Cursor uses the in-app allowlist.

Add new host initialize steps as numbered scripts in `.devcontainer/initialize.d/`.

### Allowlista w kontenerze

1. **Cursor → Agents → Auto-run → Allowlist**
2. **Rebuild Container** (initialize must clone `ASSETS_REPO` successfully)
3. W kontenerze: `cat ~/.cursor/permissions.json` — powinien odpowiadać plikowi z project-assets, nie domyślnej krótkiej liście z template

## Dev container: post-create setup

On **Rebuild Container**, `postCreateCommand` runs `.devcontainer/post-create.sh`, which executes every `*.sh` script in `.devcontainer/post-create.d/` in sorted order. Add new setup steps there (for example when you configure a tech stack).

Currently this installs [pre-commit](https://pre-commit.com/) and registers git hooks. The repo config (`.pre-commit-config.yaml`) starts with trailing-whitespace only; extend hooks as the project grows.
