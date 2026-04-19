---
name: Render Free Neon Postgres deploy
overview: Migrate persistence from local SQLite to a free managed Neon Postgres database, then deploy the FastAPI app to Render's Free Web Service tier. The existing `DATABASE_URL`-driven config and SQLAlchemy models are already portable; the work is mostly adding a Postgres driver, hardening the connection pool for Neon's auto-suspend behavior, and configuring the platforms.
todos:
  - id: neon-provision
    content: Provision Neon project, dedicated role, and copy the POOLED connection string
    status: completed
  - id: deps
    content: Add psycopg[binary] to requirements.txt
    status: completed
  - id: url-normalize
    content: Normalize DATABASE_URL to postgresql+psycopg:// in app/settings.py
    status: completed
  - id: engine-tuning
    content: Update app/database.py with pool_pre_ping, pool_recycle, and pool_size for Neon (keeping SQLite branch intact for local dev)
    status: completed
  - id: procfile-runtime
    content: Add Procfile and runtime.txt at repo root
    status: completed
  - id: local-smoke
    content: Locally point DATABASE_URL at Neon, run server, verify CRUD persists across restart
    status: completed
  - id: render-service
    content: Create Render Free Web Service from the repo with all env vars (rotated Green-API token, fresh ADMIN_API_KEY and webhook token, locked-down ALLOWED_ORIGINS)
    status: completed
  - id: green-api
    content: Update Green-API console webhook URL and authorization token to match production
    status: completed
  - id: e2e-verify
    content: "End-to-end test: admin CRUD, real WhatsApp message round-trip, redeploy persistence check, set up uptime ping"
    status: completed
isProject: false
---

# Render Free + Neon Postgres Deployment Plan

## Architecture at a glance

```mermaid
flowchart LR
    WA[WhatsApp user] --> GA[Green-API]
    GA -->|"webhook POST /webhooks/whatsapp"| Render[Render Free Web Service<br/>uvicorn app.main:app]
    Admin[Garage admin browser] -->|"/admin UI + /vehicles API"| Render
    Render -->|psycopg over TLS| Neon[("Neon Postgres<br/>free tier")]
    Render -->|sendMessage| GA
```

Free-tier caveats baked into this plan:
- Render Free spins down after ~15 min idle (~30 s cold start on next hit). The first WhatsApp webhook after idle can time out from Green-API's side. Mitigation: external uptime ping (e.g. UptimeRobot hitting `GET /` every 5 min). 24/7 = 720 h/mo, under Render's 750 h/mo free budget.
- Neon Free auto-suspends idle compute too, but wakes in <1 s. The pool config below handles dropped idle connections.
- No persistent disk on Render Free — that's why all state moves to Neon.

---

## Phase 1 — Provision Neon

- [ ] Sign up at https://neon.tech (free tier, no card).
- [ ] Create a project in a region close to Render's region (e.g. AWS `us-east-1` if Render service runs in Virginia).
- [ ] Default database `neondb` is fine; create a dedicated role (e.g. `garage_app`) with a strong password.
- [ ] Copy the **pooled** connection string from the Neon dashboard. It looks like:
  ```
  postgresql://garage_app:****@ep-xxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
  ```
  Use the **pooled** endpoint (host contains `-pooler`) so we don't blow Neon's per-compute connection cap on Render restarts.

---

## Phase 2 — Code changes (repo)

### 2a. [requirements.txt](requirements.txt) — add Postgres driver
Append:
```
psycopg[binary]>=3.2,<4.0
```
psycopg v3 binary wheel needs no compiler on Render. SQLAlchemy 2.x picks it up via `postgresql+psycopg://`.

### 2b. [app/settings.py](app/settings.py) — normalize the DB URL
Neon sometimes hands out `postgres://` (legacy) or plain `postgresql://`. Normalize to the explicit driver so SQLAlchemy uses psycopg3, not psycopg2. Add near `DB_URL`:

```python
_raw_db_url = os.getenv("DATABASE_URL", "")
if _raw_db_url.startswith("postgres://"):
    _raw_db_url = _raw_db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif _raw_db_url.startswith("postgresql://") and "+psycopg" not in _raw_db_url:
    _raw_db_url = _raw_db_url.replace("postgresql://", "postgresql+psycopg://", 1)
DB_URL: str = _raw_db_url
```

### 2c. [app/database.py](app/database.py) — pool tuned for Neon
Keep the SQLite branch for local dev; add Postgres-only options that survive Neon idle drops and stay within the free-tier connection cap:

```python
is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs: dict = {"connect_args": _connect_args}
if not is_sqlite:
    engine_kwargs.update(
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
    )

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
```

### 2d. [app/main.py](app/main.py) — no functional changes required
The lifespan's `Base.metadata.create_all(bind=engine)` works on Postgres and will create the `vehicles` table plus the two native ENUM types referenced in [app/models/vehicle.py](app/models/vehicle.py) on first boot. Optional polish: log the dialect at startup so we can confirm "postgresql" in Render logs.

### 2e. Models — verified portable
[app/models/vehicle.py](app/models/vehicle.py) uses `String`, `Enum`, and the `_UTCDateTime` `TypeDecorator` (lines 11–34). All three render correctly on Postgres. Note: SQLAlchemy will create Postgres ENUM types `vehiclestatus` and `treatmentreason` automatically. Adding an enum value later requires a manual `ALTER TYPE ... ADD VALUE` — document for future-you.

### 2f. `Procfile` (new file at repo root)
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 2g. `runtime.txt` (new file at repo root)
```
python-3.12.6
```
(Match your local `python --version`.)

### 2h. Update `.env.example` (or `.env` template) with a Postgres line
```
DATABASE_URL=postgresql+psycopg://USER:PASS@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
```
Do NOT commit a real Neon password. The current committed `.env` has a real Green-API token — rotate it as part of go-live.

### 2i. Local smoke test against Neon (before deploying)
- [ ] `pip install -r requirements.txt` (picks up psycopg).
- [ ] Set `DATABASE_URL` locally to the Neon pooled URL.
- [ ] `uvicorn app.main:app --reload`.
- [ ] Hit `GET /` → 200; create a vehicle via the admin UI; verify the row in Neon's SQL editor.
- [ ] Restart the server → row still there (proves persistence).

---

## Phase 3 — Render service setup

- [ ] Push the Phase 2 changes to GitHub.
- [ ] Render dashboard → **New** → **Web Service** → connect repo.
- [ ] Configuration:
  - Runtime: **Python 3**
  - Build command: `pip install -r requirements.txt`
  - Start command: leave blank (Procfile takes over) or paste `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Plan: **Free**
  - Region: same as Neon project for low latency
  - Health check path: `/`
- [ ] Add environment variables (mark all secrets as Secret):
  - [ ] `DATABASE_URL` = Neon **pooled** connection string (with `?sslmode=require`)
  - [ ] `ADMIN_API_KEY` = freshly generated, e.g. `python -c "import secrets;print(secrets.token_urlsafe(32))"`
  - [ ] `ALLOWED_ORIGINS` = `https://<your-service>.onrender.com` (lock down from `*`)
  - [ ] `GREEN_API_BASE_URL` = `https://7107.api.greenapi.com`
  - [ ] `GREEN_API_ID_INSTANCE` = `7107591726`
  - [ ] `GREEN_API_TOKEN_INSTANCE` = **rotated** Green-API token
  - [ ] `GREEN_API_WEBHOOK_TOKEN` = freshly generated random string (same value goes into Green-API console below)
  - [ ] `WHATSAPP_ENABLED` = `true`
  - [ ] `PYTHON_VERSION` = `3.12.6`
- [ ] Deploy. Watch logs for `Application startup complete` and a successful psycopg connection.

---

## Phase 4 — Wire up Green-API to the new URL

- [ ] In https://console.green-api.com → instance `7107591726` → **Settings** → **Notifications**:
  - [ ] **Webhook URL** = `https://<your-service>.onrender.com/webhooks/whatsapp`
        (route registered in [app/routers/whatsapp.py](app/routers/whatsapp.py) at lines 106 + 128)
  - [ ] **Webhook authorization token** = exact value of `GREEN_API_WEBHOOK_TOKEN`
  - [ ] Enable incoming-message notifications.
  - [ ] Save and use the console's **Check** button to ping the endpoint.

---

## Phase 5 — End-to-end verification

- [ ] `GET https://<your-service>.onrender.com/` returns `{"status":"ok",...}`.
- [ ] `https://<your-service>.onrender.com/admin/` loads the UI; create + update a vehicle; verify the row in Neon's SQL editor.
- [ ] Send a real WhatsApp message → reply arrives; Render logs show 200 on `/webhooks/whatsapp`.
- [ ] Force a Render redeploy → previously created vehicle still visible (proves Neon persistence across deploys).
- [ ] Configure UptimeRobot (or similar) to GET `/` every 5 min to mitigate Free-tier cold starts.
- [ ] Tag the release in git (e.g. `v0.1.0-go-live`) for rollback reference.

---

## Out of scope (future hardening, not blocking go-live)

- Migrations tooling (Alembic) instead of `create_all`.
- Forcing `ADMIN_API_KEY` to be non-empty at startup (currently empty silently means "open" in [app/dependencies.py](app/dependencies.py)).
- Rate-limit on `/webhooks/whatsapp`.
- Structured logging / log shipping.
