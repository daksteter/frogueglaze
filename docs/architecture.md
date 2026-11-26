# OpenGlaze Architecture

This document describes the architecture implemented in the current repository. Future/cloud ideas are called out explicitly instead of mixed into the supported launch path.

## Supported launch architecture

```text
Browser / PWA
    |
    v
Flask app (server.py, port 8767 locally / 8768 in Docker)
    |
    +-- SQLite database file (`DATABASE_PATH`)
    +-- Local uploads (`frontend/uploads` or Docker upload volume)
    +-- Ceramics Foundation reference data in repo files
    +-- Optional local/cloud LLM endpoint for Kama
```

The default Docker deployment persists state with named volumes:

- `openglaze_data:/data` for `/data/glaze.db`
- `openglaze_uploads:/app/frontend/uploads` for uploaded images

## Main layers

### Flask API layer

`server.py` owns route registration and request wiring.

| Route prefix | Purpose |
|---|---|
| `/api/glazes` | Glaze CRUD and UMF lookup |
| `/api/combinations` | Layering combinations and simulations |
| `/api/experiments` | Experiment lifecycle and firing logs |
| `/api/chemistry` | Batch, scale, compare, optimize, substitutions, defects |
| `/api/ask` | Kama AI assistant |
| `/api/auth` | Simple login/current-user routes |
| `/api/studios` | Lightweight studio and lab queue collaboration |
| `/api/upload`, `/api/photos` | Image upload and gallery data |
| `/health`, `/api/health` | Health and mode information |

### Data access layer

Data access is SQLite-only. `core/db.py` opens `sqlite3` connections and managers receive a database path.

### Chemistry engine

The chemistry modules implement:

- UMF calculation
- CTE estimation
- compatibility analysis
- recipe comparison
- recipe scaling / batch calculation
- substitutions
- defect prediction
- recipe optimization

These are covered by focused tests in `tests/test_chemistry.py` and route tests in `tests/test_routes.py`.

### Auth and collaboration

The app runs in personal/single-user mode. Studio collaboration uses simple bearer tokens created by `/api/auth/simple-login`. These sessions are in memory and reset on process restart.

### Frontend

The main UI is a vanilla JavaScript SPA in `frontend/` with no build step. It loads static scripts directly from `frontend/index.html` and talks to `/api` through `frontend/scripts/api.js` plus component-level fetches.

## Deployment patterns

### Manual local development

```text
Browser -> Flask dev server :8767 -> SQLite file `glaze.db`
```

### Docker self-hosting

```text
Browser -> Docker-published Flask :8768 -> SQLite `/data/glaze.db`
                                      -> upload volume `/app/frontend/uploads`
```

### Optional reverse proxy

```text
Browser -> nginx/Caddy/Traefik TLS -> Flask :8768
```

The included `nginx.conf` is minimal and intended as a starting point.

## Known architectural limits

- Simple-auth sessions are process-local and not durable.
- In-memory rate limiting is per-process.
- Uploads are local files, not object storage.
- Background jobs are not separated from request handling.
- `/api/health` is application-level; it does not deeply probe AI/database dependencies.

## Future scaling path

1. Add durable sessions/rate limits via SQLite or Redis.
2. Move long AI/batch work to background jobs.
4. Add object storage for uploads.
5. Add deeper health checks and structured production logging.
