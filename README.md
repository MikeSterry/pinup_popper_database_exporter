# PUP Lookup Exporter (Flask + Gunicorn)

A Docker-friendly Flask app that reproduces the VPS “PUP lookup” CSV export logic, with:
- a **single `/export` endpoint** (HTML button + API mode)
- a **background scheduler** (default: hourly) that only generates a new output when remote data updates
- local caching of remote files under `/data`
- output rotation into `/backups`
- `/health` and `/status` endpoints (including iframe-friendly HTML themes)

## Endpoints

### Export
- **UI:** `GET /export`
- **Manual force export:** `POST /export?force=1`
- **API JSON (only when created):** `GET /export?api=1`
  - returns **200 + JSON** when a new file is created
  - returns **204 No Content** when nothing was created
- **API download:** `GET /export?api=1&download=1`
- **API force export:** `GET /export?api=1&force=1`
- **API force re-download cache:** `GET /export?api=1&force_download=1`

### Health
- `GET /health` → `{"status":"ok"}`
- Used by `docker-compose` healthchecks.

### Status
- **HTML (iframe):** `GET /status?theme=transparent` (themes: `light`, `dark`, `transparent`)
- **JSON:** `GET /status?api=1`

The status payload includes the local cached `lastUpdated.json` epoch-ms (i.e., when the app last pulled a newer remote dataset).

## How sync works

Remote “last updated” is:
- `https://virtualpinballspreadsheet.github.io/vps-db/lastUpdated.json`

Local cache:
- `/data/lastUpdated.json`
- `/data/puplookup.csv`
- `/data/vpsdb.json`

Rules:
- **Scheduled job**: generates a new `/output/puplookup.csv` only if remote epoch-ms is newer than local.
- **Manual export**: can bypass the “no update” gate with `force=1`.
- **Force download**: `force_download=1` re-downloads remote files regardless of timestamps.

On first boot, `/data` is populated automatically. If `/output/puplookup.csv` does not exist, the app generates an initial export on startup (best-effort).

## Run with Docker

```bash
docker compose up --build
```

Open:
- Export UI: `http://localhost:8000/export`
- Status UI: `http://localhost:8000/status?theme=transparent`
- Health: `http://localhost:8000/health`

## Volumes

Compose mounts:
- `./data -> /data`
- `./output -> /output`
- `./backups -> /backups`

## Configuration

All config is env-overridable (see `docker-compose.yml`):
- `SYNC_INTERVAL_SECONDS` (default 3600)
- `MAX_BACKUPS` (default 10)
- `LOG_LEVEL` (DEBUG/INFO/ERROR)
- URLs, mount paths, timeouts, output filename, etc.


## Export page themes
- `GET /export?theme=light|dark|transparent`
- CSS: `app/static/styles/export.css`
