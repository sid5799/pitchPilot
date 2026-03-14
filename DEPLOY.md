# PitchPilot Live – Deployment Runbook (Google Cloud)

## Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`, `gcloud auth application-default login`)
- Vertex AI API and (optional) Cloud Storage API enabled

## 1. Backend (Cloud Run)

Build and deploy the FastAPI + ADK backend from the **repository root**:

```bash
# From repo root (challenge/)
export PROJECT_ID=your-gcp-project
export REGION=us-central1

# Build the image (Docker must be running)
docker build -f Dockerfile.backend -t gcr.io/$PROJECT_ID/pitchpilot-backend .

# Push to Artifact Registry (or use gcr.io with docker push)
docker tag gcr.io/$PROJECT_ID/pitchpilot-backend $REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/pitchpilot-backend
docker push $REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/pitchpilot-backend

# Deploy to Cloud Run (long timeout for Live sessions; WebSockets supported)
gcloud run deploy pitchpilot-backend \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/pitchpilot-backend \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --timeout 3600 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GOOGLE_GENAI_USE_VERTEXAI=TRUE"
```

Optional: create a GCS bucket for uploads and set `PITCHPILOT_GCS_BUCKET` in Cloud Run env. If unset, slide images are kept in memory (per instance, not shared across replicas).

## 2. Frontend

**Option A – Same Cloud Run service**

Build the React app and serve it from the backend:

1. Add to backend a static mount for the built frontend (e.g. in `main.py`: `app.mount("/", StaticFiles(directory="frontend_dist"), name="static")` and build `frontend_dist` in the Docker image).
2. In the Dockerfile, run `cd frontend && npm ci && npm run build` and copy `frontend/dist` to `app/frontend_dist` (or similar), then mount in FastAPI.

**Option B – Cloud Storage + Load Balancer (or Firebase Hosting)**

1. Build: `cd frontend && npm ci && npm run build`
2. Create a GCS bucket, set it for static website hosting, upload contents of `frontend/dist`.
3. Point your domain or Load Balancer to the bucket. Ensure the frontend’s API/WS base URL is the backend Cloud Run URL (e.g. set in env at build time: `VITE_API_URL=https://pitchpilot-backend-xxx.run.app`).

## 3. Environment variables (backend)

| Variable | Description |
|----------|-------------|
| `GOOGLE_GENAI_USE_VERTEXAI` | `TRUE` for Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | e.g. `us-central1` |
| `PITCHPILOT_GCS_BUCKET` | Optional; GCS bucket for uploads. If unset, in-memory storage is used. |
| `DEMO_AGENT_MODEL` | Optional; Live API model ID (default: gemini-2.5-flash-native-audio-preview-12-2025) |

Cloud Run automatically provides credentials (ADC) when the service runs in GCP.

## 4. Frontend configuration for production

Point the frontend to the deployed backend:

- If frontend is on the same origin as the backend (Option A), no change.
- If frontend is on a different domain (Option B), set the WebSocket and API base URL via a build-time env (e.g. Vite `VITE_WS_URL` and `VITE_API_URL`) and use them in `useLiveSession.js` and `api/upload.js`.

## 5. Health check

- `GET https://your-run-url.run.app/health` should return `{"status":"ok"}`.

## 6. Optional: Vertex AI Agent Engine

To deploy the ADK agent to Vertex AI Agent Engine instead of (or in addition to) Cloud Run, follow the [ADK deploy to Agent Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine) docs. The current app uses the agent in-process via `Runner` and `run_live()`; for Agent Engine you would register the same agent and optionally call its runtime from the FastAPI app.
