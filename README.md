# tenderEye

A local-dev tender evaluation platform with a FastAPI backend and a Next.js frontend.

## Prerequisites

- Python 3.11+ (tested on 3.13)
- Node.js 18+ and npm
- Git

## 1. Clone / pull the latest code

```powershell
git clone https://github.com/a-Ayush-kumar/tenderEye.git
cd tenderEye


## 2. Install dependencies

Backend (note: the requirements file is `requiremnts.txt`, with the typo):

```powershell
python -m pip install -r backend/requiremnts.txt
```

Frontend (only needed the first time, or after a pull that updates the lockfile):

```powershell
npm install --prefix frontend
```

## 3. Run via `run_local.py`

`run_local.py` lives in the project root. It sets up SQLite + local storage env vars, seeds the database, and starts each service. Run the two commands in **separate terminals** from the project root.

**Terminal 1 — Backend (FastAPI on port 8000):**

```powershell
python run_local.py --backend
```

- API:  http://localhost:8000
- Docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

**Terminal 2 — Frontend (Next.js on port 3000):**

```powershell
python run_local.py --frontend
```

- App: http://localhost:3000

Stop either server with `Ctrl+C` in its terminal.

## 4. Verify it is running

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:3000        -UseBasicParsing
```

Both should return status `200`.

## Project layout

```
tenderEye/
├── run_local.py          # local dev runner (backend + frontend)
├── backend/
│   ├── app/              # FastAPI app (main.py, models.py, database.py, api/, services/)
│   ├── scipts/           # seed scripts
│   └── requiremnts.txt   # backend Python deps
└── frontend/             # Next.js app
```

## Troubleshooting

- **`Could not import module "app.main"`** — make sure you are running the backend command from the project root (not from inside `backend/`). `run_local.py` handles the cwd for you.
- **Port already in use** — another `next dev` or `uvicorn` is still running. Kill it (e.g. `taskkill /PID <pid> /F` on Windows) and retry.
- **WeasyPrint warning at backend startup** — harmless; PDF generation falls back to `fpdf2`.
- **Stubbed endpoints** — financial evaluation, VIGIL analysis, CCI referral, and evidence locker currently return placeholder data; swap in real logic when ready.
