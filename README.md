# PitchPilot Live

**Real-time AI presentation coach** — Upload your slides, rehearse with voice, and get live feedback on pacing, filler words, and clarity. Built with **Gemini Live API** and **Google Cloud**.

---

## 📃 Summary (For Judges)

### What It Does

PitchPilot Live is a **Live Agent** that helps presenters improve delivery in real time. Users upload a PDF or PowerPoint, connect their microphone, and rehearse while an AI coach:

- **Listens** to their speech and **sees** the current slide (multimodal: audio + vision).
- Gives **spoken feedback** during the rehearsal (e.g. “Slide 2: Slow down your pace slightly.”) without interrupting the flow.
- Records **key takeaways** per slide (filler words, pacing, clarity) validated with a Pydantic schema.
- Supports **Q&A mode** (“Challenge Me”) where the agent asks predicted audience questions and evaluates answers.

The agent can be **interrupted** (user keeps talking); the backend auto-reconnects on Live API closures (e.g. 1008, 1011) so the session continues.

### Technologies Used

| Layer | Technology |
|-------|------------|
| **AI / Agent** | **Gemini Live API** (bidirectional streaming), **Google GenAI SDK** (`google-genai`), **Google ADK** (Agent Development Kit) for Vertex path |
| **Models** | Gemini (e.g. `gemini-2.5-flash-native-audio-preview-12-2025`, `gemini-2.0-flash-live-preview-04-09`) for live coaching; `gemini-2.0-flash` for Q&A question generation |
| **Backend** | FastAPI, WebSockets, Python 3.10+ |
| **Frontend** | React, Vite |
| **Google Cloud** | **Google Cloud Storage (GCS)** for slide uploads when deployed; **Cloud Run** for hosting the backend (see [DEPLOY.md](DEPLOY.md)) |

### Data Sources

- **User uploads only**: PDF or PPTX presentations. No external datasets. Slide images and extracted text are used in-session for coach context and Q&A; optionally stored in GCS when `PITCHPILOT_GCS_BUCKET` is set.

### Findings & Learnings

- **Streaming**: The Live API sends agent output in small chunks (e.g. word-by-word transcription). The frontend must accumulate these without dropping them (e.g. we removed a 10-character minimum that was hiding coach text).
- **Tool output**: The model sometimes echoed `record_feedback(...)` in speech. We tightened instructions and added frontend stripping of tool syntax; **Pydantic validation** of tool-call args ensures only valid feedback appears in Key takeaways.
- **Resilience**: The Live API can close with 1008 (“Operation not supported”) or 1011 (internal error). We treat both as reconnectable and notify the client with `reconnecting: true` so the session continues.
- **Mixed-language / noisy transcript**: When the transcript is unclear (e.g. mixed language or bad tokenization), we instructed the coach to ignore literal words and give only delivery-focused feedback (pacing, clarity) and to never repeat or paraphrase unclear text.

---

## 🚀 Spin-Up Instructions

### Prerequisites

- **Python 3.10+**
- **Node 18+**
- **Google AI Studio API key** (for local run without GCP) — get one at [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone and open the project

```bash
git clone <your-repo-url>
cd pitchPilot
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at least:

```env
GOOGLE_API_KEY=your-google-ai-studio-api-key
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

Then start the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: **http://localhost:8000**
- Health: **http://localhost:8000/health** → `{"status":"ok"}`

### 3. Frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

- App: **http://localhost:5173**
- Vite proxy forwards `/api` and `/ws` to the backend.

### 4. Try it

1. Open **http://localhost:5173**
2. Upload a **PDF or PPTX** (max 50 MB)
3. Click **Connect & start rehearsal**, allow microphone
4. Speak and change slides; the coach will respond with live feedback and key takeaways

**Optional (Google Cloud):** To use **Vertex AI** and **GCS**, set in `.env`: `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and optionally `PITCHPILOT_GCS_BUCKET`. See [DEPLOY.md](DEPLOY.md) for full Cloud Run + GCS deployment.

---

## 🖥️ Proof of Google Cloud Deployment

We use **Google Cloud** as follows:

1. **Google Cloud Storage (GCS)**  
   - **Where**: [`backend/app/services/storage.py`](backend/app/services/storage.py)  
   - **What**: When `PITCHPILOT_GCS_BUCKET` is set, uploaded slide images are stored in GCS; URLs are returned to the frontend.  
   - **Dependency**: `google-cloud-storage` in [`backend/requirements.txt`](backend/requirements.txt).

2. **Cloud Run (backend hosting)**  
   - **Where**: [DEPLOY.md](DEPLOY.md)  
   - **What**: The FastAPI backend is built with `Dockerfile.backend` and deployed to Cloud Run with a long timeout for Live sessions.

3. **Vertex AI (optional)**  
   - When `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, the app uses Vertex AI for the Live API and question-generation model.

---

## Project Layout

| Path | Description |
|------|--------------|
| `backend/app/main.py` | FastAPI app, WebSocket endpoint, CORS |
| `backend/app/live_session.py` | Gemini Live API session (GenAI SDK), coach instructions, tool validation, logging |
| `backend/app/agent/` | ADK agent and `record_feedback` tool |
| `backend/app/schemas/feedback.py` | Pydantic schema for feedback validation |
| `backend/app/services/storage.py` | GCS upload + in-memory fallback |
| `backend/app/routers/upload.py` | Upload PDF/PPTX, slide URLs, generate questions |
| `frontend/src/` | React app: Upload, Rehearsal, Q&A; `useLiveSession` hook, LiveFeedback UI |

---

## Deployment (Google Cloud)

Full steps (Cloud Run, GCS, env vars): **[DEPLOY.md](DEPLOY.md)**.
