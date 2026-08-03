# One-time machine setup (local development)

AXIOM local development is driven by **`./axiom`** at the repository root (pure bash, `docker compose`, `curl`, optional `jq` for parsing only).

## Prerequisites

- **Docker Engine** + **Docker Compose v2** (`docker compose`)
- **Bash** 4+
- **[uv](https://docs.astral.sh/uv/)** (Python toolchain)
- **Node.js** 20+ (CI uses 22; 20+ is a reasonable local floor)
- **git**
- **curl**
- **lsof** or **ss** (for port inspection in `./axiom dev` / `./axiom status`)

## Docker group (required)

`./axiom` **never** runs `sudo docker`. Your user **must** be in the **`docker`** group so `docker compose` can talk to the daemon.

If `groups` does not list `docker`, `./axiom` prints:

```text
✗ Your user is not in the docker group.
  Run this once, then log out and back in (or newgrp docker):
    sudo usermod -aG docker $USER && newgrp docker
  More: docs/dev-setup.md
```

One-time fix:

```bash
sudo usermod -aG docker "$USER" && newgrp docker
```

Then confirm: `groups | grep -q docker`.

**ADR:** See **ADR-025** in `docs/decisions.md` for why this is mandatory.

## Environment files

1. Copy **`.env.example`** → **`apps/backend/.env`** (or use repo-root `.env` / `.env.dev` per load order in `docs/auth-setup.md`).
2. Copy **`apps/frontend/.env.example`** → **`apps/frontend/.env.local`** and set **`API_URL`** to the backend (default `http://127.0.0.1:8000` or `http://localhost:8000`).
3. Google OAuth: follow **`docs/auth-setup.md`** (redirect URI, Google Cloud Console).

## First run

From the repository root:

```bash
./axiom dev
```

On the first dev start, if `AXIOM_WORKER_GATEWAY_API_KEY` is missing from `apps/backend/.env`, the CLI mints a project API key for a dedicated local **dev** user/project and writes the `axm_live_…` secret into that file (nothing is printed to the terminal). Later runs verify the same key instead of minting again. Export `AXIOM_WORKER_GATEWAY_API_KEY` in your shell to use a specific key without touching `.env`, or set `AXIOM_WORKER_AUTOMINT=0` to disable automation. Rotate with `./axiom rotate-worker-key` (soft-revokes the old key in the database, writes a new secret, then restart `./axiom dev`).

- Postgres is published on host **`:5433`** → container `:5432`.
- Redis on host **`:6380`** → container `:6379`.
- Backend **`:8000`**, frontend **`:3000`**.

**Ctrl+C** stops app processes and runs **`docker compose stop`** on Redis and Postgres (named volumes are kept).

### Backend tests (`pytest`) vs the dev database

`pytest` targets a **separate** Postgres database **`axiom_test`** (same server as dev, port **5433**) and **Redis logical DB 1**, so integration tests and `TRUNCATE` fixtures cannot wipe your **`axiom`** dev data or flush the same Redis DB the running app uses. **`./axiom dev`** creates `axiom_test` if needed and runs Alembic on it after migrating `axiom`.

To run tests without `./axiom dev`, create the DB once:  
`docker compose exec -T postgres psql -U axiom -d postgres -c "CREATE DATABASE axiom_test OWNER axiom;"`  
then `cd apps/backend && DATABASE_URL=postgresql+asyncpg://axiom:axiom_dev_only@127.0.0.1:5433/axiom_test uv run alembic upgrade head`.

Only for debugging against the live dev DB: **`AXIOM_PYTEST_USE_DEV_DB=1`** (not recommended).

Playwright **`npm run test:e2e`** drives the real UI against whatever **`./axiom dev`** is serving (typically the **`axiom`** database); it does not invoke `pytest`. Destructive **`TRUNCATE`** behavior comes from **backend tests**, not from the Playwright specs themselves.

## `./axiom stop` vs legacy “stop + `docker compose down`”

Phase 2.4 **replaces** the old checked-in **`stop-dev.sh`** helper (it lived under **`scripts/`**). Previously that helper ran **`docker compose down`**, which removed containers (volumes usually survived unless `-v`). **`./axiom stop`** runs **`docker compose stop`** only: containers stay, named volumes stay, restarts are faster.

**Nuclear reset** (drops DB/Redis data): **`./axiom fresh`** → **`docker compose down -v`**.

If you expected the old “everything `down`” behavior for a routine stop, use **`./axiom stop`** and read the troubleshooting row below.

## Troubleshooting

| Symptom | What to do |
|--------|----------------|
| `✗ Your user is not in the docker group` | Add user to `docker` group and re-login / `newgrp docker` (see above). |
| `docker daemon not reachable` | Start Docker Desktop or `systemctl` service; verify `docker info`. |
| `port … held by an unexpected process` on **5433** / **6380** | Usually only **docker-proxy** / **rootlesskit** may hold those host ports. Anything else is a conflict—free the port or fix compose. |
| `port 8000/3000 … non-AXIOM process` | `./axiom` will **not** kill unknown listeners (e.g. `python3 -m http.server` on 8000). Stop that process yourself. |
| Migrations fail | Ensure Postgres is healthy; check `DATABASE_URL` in `apps/backend/.env` matches compose (**host** ports **5433** / **6380** in URLs). |
| OAuth / env issues | See **`docs/auth-setup.md`**. |
