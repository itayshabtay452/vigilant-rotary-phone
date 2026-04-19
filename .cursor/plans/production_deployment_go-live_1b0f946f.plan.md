---
name: Production deployment Go-Live
overview: Deploy the FastAPI MVP to Render with a persistent disk so the SQLite database survives restarts, harden secrets via the platform's env-var manager, and re-point the Green-API webhook to the new permanent URL.
todos:
  - id: prep-files
    content: Add Procfile and runtime.txt to repo root; verify requirements.txt is deploy-ready
    status: pending
  - id: render-setup
    content: Create Render Web Service (Starter) + Persistent Disk mounted at /var/data
    status: pending
  - id: env-vars
    content: Configure all env vars in Render (rotated Green-API token, fresh ADMIN_API_KEY and GREEN_API_WEBHOOK_TOKEN, DATABASE_URL pointing to /var/data/garage.db, locked-down ALLOWED_ORIGINS)
    status: pending
  - id: deploy-verify
    content: Deploy, verify GET / health check and /admin UI on the new permanent URL
    status: pending
  - id: green-api-webhook
    content: Update Green-API console webhook URL to https://<service>.onrender.com/webhooks/whatsapp and matching authorization token
    status: pending
  - id: smoke-test
    content: "End-to-end smoke test: send a real WhatsApp message and confirm reply"
    status: pending
isProject: false
---


# Production Deployment Plan (Go-Live)

## 1. Hosting platform recommendation

**Primary recommendation: Render.com.** It is the simplest path for a FastAPI MVP — connect the GitHub repo, point at `app.main:app`, and Render builds + runs it. The web service tier is free; a persistent disk requires a Starter web service (~$7/mo) + disk (~$0.25/GB/mo). For a garage MVP, the disk add-on is what makes SQLite a viable production choice.

**Free alternative: Fly.io.** Smallest VM + 1 GB volume runs for ~$0–2/mo and supports SQLite the same way. More setup (CLI + `fly.toml` + `Dockerfile`), but cheaper if budget is the hard constraint.

Rest of the plan assumes **Render**. Fly equivalents are noted at the end.

## 2. SQLite persistence strategy

Cloud filesystems are ephemeral — every deploy/restart creates a fresh container, wiping `garage.db`. Fix:

- Provision a **Render Persistent Disk** (e.g. 1 GB, mount path `/var/data`).
- Override the DB location through the existing `DATABASE_URL` env var (already supported in [app/settings.py](app/settings.py) and [app/database.py](app/database.py)):
  - `DATABASE_URL=sqlite:////var/data/garage.db` (four slashes = absolute path)
- The disk is mounted before the process starts, so the existing `Base.metadata.create_all(...)` call in the lifespan in [app/main.py](app/main.py) will initialize tables on first boot and reuse the file thereafter.
- Do not commit `garage.db` (already in `.gitignore`). Initial seed data, if any, can be loaded once via a one-off `render shell` SQL session.

This is the easiest MVP path. If/when you outgrow SQLite, the swap is just changing `DATABASE_URL` to a Postgres URL — no code changes.

## 3. Secrets / environment variables

Do NOT commit `.env`. The current `.env` contains a real Green-API token and must be rotated before go-live (treat the value in the repo as leaked).

In Render dashboard → Service → **Environment**, add:

- `ADMIN_API_KEY` — generate a fresh long random string (e.g. `python -c "import secrets;print(secrets.token_urlsafe(32))"`). Required in prod; the dependency in [app/dependencies.py](app/dependencies.py) currently treats empty as "open", so we must set it.
- `GREEN_API_BASE_URL` — e.g. `https://7107.api.greenapi.com`
- `GREEN_API_ID_INSTANCE` — `7107591726`
- `GREEN_API_TOKEN_INSTANCE` — **rotated** token from Green-API console
- `GREEN_API_WEBHOOK_TOKEN` — fresh long random string (same value goes into Green-API console below)
- `WHATSAPP_ENABLED=true`
- `ALLOWED_ORIGINS=https://<your-service>.onrender.com` (lock down from `*`)
- `DATABASE_URL=sqlite:////var/data/garage.db`
- `PYTHON_VERSION=3.12.6` (or whatever your local `python --version` is)

Mark all secret values as "Secret" in Render so they are masked in logs.

## 4. WhatsApp webhook re-pointing (Green-API console)

Once the service is live and you have the permanent URL `https://<your-service>.onrender.com`:

1. Log in to https://console.green-api.com.
2. Open your instance (`7107591726`) → **Settings** → **Notifications**.
3. Set **Webhook URL** to:
   `https://<your-service>.onrender.com/webhooks/whatsapp`
   (route defined in [app/routers/whatsapp.py](app/routers/whatsapp.py) at line 106 + 128)
4. Set **Webhook authorization token** to the exact value of `GREEN_API_WEBHOOK_TOKEN` you put in Render.
5. Enable the notification types you currently use (incoming messages at minimum).
6. Save, then click **Check** / send a test message from a real WhatsApp client.
7. Verify in Render logs that the request was authenticated and processed. If Green-API reports 401, the webhook token doesn't match; if 200 but no reply, check `WHATSAPP_ENABLED=true`.

## 5. Code / repo prep before deploying

Small, contained changes:

### 5a. Add `Procfile` at repo root
Render auto-detects this for Python services:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

(No `Dockerfile` needed on Render for this stack. Fly.io would need one.)

### 5b. Add `runtime.txt` (or rely on `PYTHON_VERSION` env var)
Pin the interpreter so Render doesn't auto-bump:

```
python-3.12.6
```

### 5c. `requirements.txt` adjustments
The current file in [requirements.txt](requirements.txt) is sufficient — `uvicorn` ships its own server. Optional polish:
- Switch `uvicorn>=0.32.0,<1.0.0` to `uvicorn[standard]>=0.32.0,<1.0.0` for better perf (httptools, websockets, uvloop where available). Not required for MVP.
- Do **not** add gunicorn for an MVP; single uvicorn worker is fine and matches the lifespan-based table init in [app/main.py](app/main.py).

### 5d. `app/main.py` review
No code changes strictly required — it already:
- Reads config via env (`ALLOWED_ORIGINS` from `app.settings`).
- Creates tables on startup via lifespan.
- Exposes `GET /` as a health check (line 49–51), which Render's health probe can hit.

Optional hardening to consider later (out of scope for this go-live): structured logging, rate-limit on `/webhooks/whatsapp`, and forcing `ADMIN_API_KEY` to be non-empty at startup instead of silently allowing open access.

### 5e. Frontend
[frontend/app.js](frontend/app.js) calls `'/vehicles'` (relative path, line 2), so it works automatically on the new domain. The admin UI will be at `https://<your-service>.onrender.com/admin/`.

## Deployment sequence (do in this order)

1. Locally: rotate the Green-API token in the console (the existing one is in committed-adjacent `.env`, treat it as compromised).
2. Add `Procfile` + `runtime.txt`, commit, push to `main`.
3. Render dashboard → **New** → **Web Service** → connect repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: leave blank (Procfile takes over) or `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Plan: **Starter** (required for persistent disk).
4. Add a **Disk**: name `garage-data`, mount path `/var/data`, size 1 GB.
5. Add all env vars from section 3.
6. Trigger deploy. Watch logs for `Application startup complete`.
7. Hit `https://<your-service>.onrender.com/` — expect `{"status":"ok",...}`.
8. Hit `https://<your-service>.onrender.com/admin/` — verify UI loads.
9. Update Green-API console webhook (section 4).
10. Send a real WhatsApp message → confirm reply arrives.
11. Tag the release in git for rollback reference.

## Fly.io alternative (only if you choose it instead of Render)

- Add a `Dockerfile` (python:3.12-slim, copy app, `CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8080"]`).
- `fly launch` → create app + 1 GB volume mounted at `/data`.
- Set `DATABASE_URL=sqlite:////data/garage.db`.
- Same secret/webhook steps as above.
