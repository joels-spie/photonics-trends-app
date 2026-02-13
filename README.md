# Photonics Publishing Intelligence (V1)

Local-first dashboard for photonics publishing trend and competitive intelligence using the Crossref REST API.

## Stack
- Backend: Python 3.11+, FastAPI, httpx, pydantic, sqlite3 cache
- Frontend: React + Vite + TypeScript
- Charts: Plotly.js via `react-plotly.js`

## Repository Layout
- `backend/` FastAPI app and analytics engine
- `frontend/` single-page dashboard
- `config/` YAML topic/publisher/app defaults
- `tests/` unit tests for matcher/query builder/cache

## Setup (Windows PowerShell)

### 1) Create/activate venv
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install backend dependencies
```powershell
pip install -r backend/requirements.txt
```

### 3) Run backend
```powershell
uvicorn app.main:app --app-dir backend --reload --port 8000
```

### 4) Run frontend
In a second PowerShell window:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://127.0.0.1:5173`.

## API Endpoints
- `GET /api/health`
- `GET /api/config`
- `POST /api/analyze/topic`
- `POST /api/analyze/compare_publishers`
- `POST /api/analyze/emerging_topics`
- `POST /api/analyze/gap_analysis`
- `POST /api/analyze/institutions`
- `POST /api/analyze/time_to_pub`

## Demo Defaults
- Topic: `silicon_photonics`
- Query: `silicon photonics OR photonic integrated circuit`
- Date range: `2018-01-01` to today
- Publishers: SPIE, IEEE, Optica
- Max records: 1200

## Demo Mode Walkthrough
1. Start backend and frontend.
2. Open Overview tab and click `Run Current Tab`.
3. Visit Publishers, Emerging Topics, and Gap Analysis tabs, running each.
4. Use `Copy Query` to copy JSON inputs.
5. Use CSV/JSON export buttons from each tab.

## Sample Backend Requests
```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/analyze/topic" -ContentType "application/json" -Body '{
  "topic_key": "silicon_photonics",
  "ad_hoc_query": "silicon photonics OR photonic integrated circuit",
  "from_pub_date": "2019-01-01",
  "until_pub_date": "2025-12-31",
  "doc_types": ["journal-article", "proceedings-article"],
  "publishers": ["SPIE", "IEEE", "Optica"],
  "max_records": 800
}'
```

## Testing
```powershell
$env:PYTHONPATH="backend"
pytest -q
```

## Build A Windows Installer (Standalone App)
This creates a Windows installer that packages:
- React frontend in Electron
- FastAPI backend as a bundled `photonics-backend.exe` (PyInstaller)

### Prerequisites (on Windows)
- Python 3.11+
- Node.js 20+
- npm

### Build Command
From repo root in PowerShell:
```powershell
.\scripts\windows\build_windows_installer.ps1
```

Installer output:
- `frontend\release\Photonics-Trends-Setup-0.1.0.exe`

### Notes
- The packaged backend cache is written to user-local app data (not install directory).
- During development, web mode remains unchanged (`vite` + backend on `127.0.0.1:8000`).

### Corporate-Ready Signed Builds
For managed enterprise environments, signed binaries are strongly recommended (SmartScreen reputation, endpoint policy allow-listing, software distribution tooling).

Set signing variables in your shell/session (example values in `frontend/.env.release.example`):
- `CSC_LINK`
- `CSC_KEY_PASSWORD`

Build signed installer:
```powershell
.\scripts\windows\build_windows_installer.ps1 -RequireCodeSigning
```

Build signed NSIS + MSI artifacts (typical corporate deployment formats):
```powershell
.\scripts\windows\build_windows_installer.ps1 -RequireCodeSigning -CorporateArtifacts
```

If signing is required but certificate variables are missing/invalid, build fails by design.

### Notarization-Ready (macOS Release Pipelines)
Notarization is for macOS binaries (not Windows). The project now includes an `afterSign` notarization hook that runs automatically on mac builds when these env vars are set:
- `APPLE_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_TEAM_ID`

## Data Quality Notes
The app always displays:
- record counts
- metadata coverage rates (abstract, affiliation, accepted-date)
- warnings for low-coverage conditions

Crossref metadata is incomplete in some dimensions (especially abstract and accepted-date); all analyses are best-effort and explicitly coverage-scored.

## Screenshot Instructions
After launching frontend:
1. Run Overview analysis.
2. Capture the full dashboard with left filters and active Overview tab.
3. Repeat for Gap Analysis tab.
