# Local setup

## Recommended Docker backend

1. Install Docker, Node.js 22, and npm.
2. Copy `.env.example` to `.env`.
3. Replace the local PostgreSQL placeholder consistently. Do not use a production secret.
4. Start the backend stack.

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Compose starts PostgreSQL, Redis, ClamAV, the API, a generic/dashboard worker, a pipeline worker, and a one-shot storage ownership initializer. The API entrypoint applies Alembic migrations and deterministic governance/connection-type seeds.

Start the frontend:

```bash
npm ci
npm run dev
```

Open `http://localhost:3009`.

## Create the first local operator

Run the interactive CLI so the password is not placed in command history:

```bash
docker compose exec api python -m vip_api.cli create-user \
  --username local-admin \
  --email local-admin@example.com \
  --display-name "Local Administrator"
docker compose exec api python -m vip_api.cli grant-platform-admin \
  --email local-admin@example.com
```

The first command prompts securely. Do not add the chosen password to `.env`, documentation, a demo workbook, or a shell script.

## Native API development

Start only dependencies with Compose, then install the locked backend environment:

```bash
docker compose up -d postgres redis clamav
cd apps/api
python -m venv .venv
# Activate the virtual environment for your shell.
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
cp .env.example .env
alembic upgrade head
uvicorn vip_api.main:app --reload --no-access-log
```

If the API runs on the host, ensure `DATABASE_URL`, `REDIS_URL`, and `CLAMAV_HOST` use host-reachable addresses rather than Compose service names.

## Stop and reset

`docker compose down` stops services while preserving named volumes. `docker compose down -v` destroys local databases and artifacts and must be used only when that data is disposable and backed up if needed.
