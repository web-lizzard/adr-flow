# MCP servers (devcontainer)

Cursor MCP servers run **inside** the devcontainer. Definitions: [`.cursor/mcp.json`](../.cursor/mcp.json).

| Server | Purpose | Prerequisites |
|--------|---------|---------------|
| `gcloud` | GCP CLI from chat | `gcloud auth login`, project/region set |
| `gcp-observability` | Logs, metrics, traces | Same gcloud auth |
| `github` | Actions / repo metadata | `GITHUB_PERSONAL_ACCESS_TOKEN` in root `.env` |
| `dbeast` | Local Postgres debug (schema, SELECT, EXPLAIN, health) | Devcontainer Postgres; `DATABASE_URL` in `devcontainer.json` |

Install hooks run via [post-create.sh](post-create.sh) → `post-create.d/` (no `postStartCommand` — MCP subprocesses start on demand when Cursor connects).

## First-time setup

1. Copy [`.env.example`](../.env.example) → `.env` and set `GITHUB_PERSONAL_ACCESS_TOKEN` (fine-grained PAT: Actions Read, Metadata Read).
2. Rebuild the devcontainer (runs `18-mcp-github-binary.sh`, `19-mcp-dbeast.sh`, …).
3. Run `just mcp-verify` from the workspace root.
4. In Cursor: **Settings → Tools & MCP** — confirm `gcloud`, `gcp-observability`, `github`, and `dbeast` are enabled and connected.

## DBeast (PostgreSQL)

[DBeast](https://github.com/snss10/DBeast) is installed with `uv tool install` from git tag `v0.2.1` (`19-mcp-dbeast.sh`). Cursor starts it through [`scripts/mcp/dbeast-stdio.sh`](../scripts/mcp/dbeast-stdio.sh) (upstream `dbeast` console entry point is broken).

**Connection:** `DATABASE_URL` from devcontainer `remoteEnv` (`postgresql://postgres:postgres@postgres:5432/adr_flow`), overridable via root `.env`.

**Audit logs:** `logs/mcp_audit/` (gitignored).

**Example prompts:**

- „Pokaż schemat tabeli `users`”
- „Jakie widoki są w `public`?”
- „Uruchom `SELECT count(*) FROM …`”
- „Sprawdź `database_health` i wolne query”

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| MCP process uses host paths | Reopen folder in devcontainer; paths must be `/workspace/...` |
| `github` fails | Set `GITHUB_PERSONAL_ACCESS_TOKEN` in `.env`; reload MCP |
| `dbeast` not installed | Rebuild devcontainer or run `bash .devcontainer/post-create.d/19-mcp-dbeast.sh` |
| `dbeast` cannot connect to Postgres | Ensure `postgres` service is up (`docker compose ps`); credentials match [docker-compose.yml](docker-compose.yml) |
| `gcloud` auth errors | `just gcp-auth` / `gcloud auth login` |

Shell check: `just mcp-verify`.
