# Frontend Demo Dashboard (Non‑Destructive)

This folder adds a **demo-only frontend UI** for the existing Python multi-agent customer support system.

**Backend is unchanged.** No agent/tool/retry/DLQ logic is modified.

## What it shows
- Dashboard KPI cards + charts
- Ticket processing view (table + detail)
- **Retry demo**: TKT‑023 timeline (attempts 1→2→3)
- **DLQ demo**: TKT‑021 (failed_step, reason, error_code)
- Audit trail stepper (per-ticket steps)
- Architecture flow diagram
- Final system metrics

## Run (recommended)
From repo root:
```bash
cd frontend
npx live-server
```
Then open the URL printed in the terminal.

> Note: The UI uses `fetch()` to load `frontend/assets/sample-data.json`, so opening `index.html` directly via `file://` may block loading due to browser security. A simple local server avoids that.

## Data source
- `frontend/assets/sample-data.json` is generated from `project/audit_log.json`.
- This is **static** demo data (no API integration).

## Regenerate sample data (optional)
This UI expects the full schema already present in `frontend/assets/sample-data.json` (metrics + ticket summaries + audit map + retry/DLQ demos).

For submission/demo stability, it’s recommended to keep the checked-in `sample-data.json` as-is.

If you *do* want to refresh visuals after re-running the backend, regenerate `frontend/assets/sample-data.json` with a script that outputs the same keys as the existing file (do not output only `audits`, or the UI will not load).

## Files
- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`
- `frontend/assets/sample-data.json`
