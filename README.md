# PitchPilot Live

Real-time AI presentation coach using **Gemini Live API** and **ADK** (Agent Development Kit). Upload a PDF or PowerPoint, rehearse with live feedback on filler words, pacing, and clarity, and practice Q&A.

## Requirements

- Python 3.10+
- Node 18+
- Google Cloud project with Vertex AI (and optional GCS bucket)
- Or Google AI Studio API key for local dev

## Backend (FastAPI + ADK)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # set GOOGLE_CLOUD_PROJECT, etc.
uvicorn app.main:app --reload --app-dir .
```

API: `http://localhost:8000`. Health: `GET /health`.

## Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:5173`. Proxy forwards `/api` and `/ws` to the backend.

## Project layout

- `backend/app/` – FastAPI app, ADK agent, upload router, WebSocket (live), services (slide parser, GCS)
- `frontend/src/` – React app: Upload, Rehearsal, Q&A pages; hooks and API client

## Deployment (Google Cloud)

- **Backend**: Build with `Dockerfile.backend` from repo root; deploy to **Cloud Run** with long timeout (e.g. 3600 s) for Live sessions. Set env: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=TRUE`; optional `PITCHPILOT_GCS_BUCKET` for slide storage.
- **Frontend**: Run `npm run build` in `frontend/`; serve the `dist/` output from the same Cloud Run service (mount static in FastAPI) or upload to **GCS** / Firebase Hosting and set the backend URL for API and WebSocket.
- Full steps and env reference: see [DEPLOY.md](DEPLOY.md).
