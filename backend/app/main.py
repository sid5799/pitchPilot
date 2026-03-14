"""PitchPilot Live – FastAPI app, WebSocket endpoint, and routes."""
import asyncio
import base64
import json
import logging
import os
import warnings
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Load env before importing agent
load_dotenv(Path(__file__).parent.parent / ".env")


from .agent import root_agent
from .routers import upload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

APP_NAME = "pitchpilot-live"
session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)

app = FastAPI(
    title="PitchPilot Live",
    description="Real-time presentation coach with Gemini Live API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])


@app.get("/health")
def health():
    """Health check for Cloud Run / load balancers."""
    return {"status": "ok"}


def _use_sdk_live() -> bool:
    """Use GenAI SDK Live (API key) instead of ADK when API key is set and not Vertex."""
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    return bool(api_key) and not use_vertex


@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
    proactivity: bool = True,
    affective_dialog: bool = False,
) -> None:
    """WebSocket for bidirectional streaming: GenAI SDK (API key) or ADK (Vertex)."""
    await websocket.accept()
    # Challenge mode: ?mode=challenge&scope=all | scope=slide&slide_index=N
    query = websocket.query_params
    mode = query.get("mode") or ""
    scope = query.get("scope") or "all"
    slide_index_raw = query.get("slide_index")
    slide_index: int | None = None
    if scope == "slide" and slide_index_raw is not None:
        try:
            slide_index = int(slide_index_raw)
        except ValueError:
            slide_index = None

    logger.info("WebSocket connected: user_id=%s session_id=%s mode=%s scope=%s", user_id, session_id, mode or "rehearsal", scope)

    if _use_sdk_live():
        from .live_session import run_live_session
        try:
            await run_live_session(
                websocket,
                session_id=session_id,
                mode="challenge" if mode == "challenge" else None,
                scope=scope if mode == "challenge" else None,
                slide_index=slide_index if mode == "challenge" else None,
            )
        except WebSocketDisconnect:
            logger.info("Client disconnected (SDK Live)")
        return

    model_name = root_agent.model
    is_native_audio = "native-audio" in model_name.lower()
    is_flash_live = "flash-live" in model_name.lower()
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"

    # gemini-2.0-flash-live (reference config): AUDIO + TEXT, speech voice, no session_resumption
    if is_flash_live:
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO", "TEXT"],
            session_resumption=None,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
        )
    elif is_native_audio:
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            session_resumption=None,
            proactivity=(
                types.ProactivityConfig(proactive_audio=True) if (proactivity and use_vertex) else None
            ),
            enable_affective_dialog=affective_dialog if use_vertex else None,
        )
    else:
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["TEXT"],
            session_resumption=None,
        )

    session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if not session:
        await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)

    live_request_queue = LiveRequestQueue()

    async def upstream_task() -> None:
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                audio_data = message["bytes"]
                live_request_queue.send_realtime(
                    types.Blob(mime_type="audio/pcm;rate=16000", data=bytes(audio_data))
                )
            elif "text" in message:
                try:
                    obj = json.loads(message["text"])
                    if obj.get("type") == "text":
                        live_request_queue.send_content(
                            types.Content(parts=[types.Part(text=obj["text"])])
                        )
                    elif obj.get("type") == "image":
                        image_data = base64.b64decode(obj["data"])
                        mime = obj.get("mimeType", "image/jpeg")
                        live_request_queue.send_realtime(types.Blob(mime_type=mime, data=image_data))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Invalid WebSocket text message: %s", e)

    async def downstream_task() -> None:
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            event_json = event.model_dump_json(exclude_none=True, by_alias=True)
            await websocket.send_text(event_json)

    try:
        await asyncio.gather(upstream_task(), downstream_task())
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.exception("Streaming error: %s", e)
    finally:
        live_request_queue.close()
        logger.info("Live session closed")
