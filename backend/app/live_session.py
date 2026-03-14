"""Live API session using Google GenAI Python SDK with API key (no ADK)."""
import asyncio
import base64
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DEMO_AGENT_MODEL = os.getenv(
    "DEMO_AGENT_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"
)
# Explicit language for Live API: improves transcription. Model may not support all codes (e.g. en-IN unsupported on some).
# Set PITCHPILOT_LIVE_LANGUAGE_CODE to en-US, en-GB, etc. Default en-US; leave unset to skip (auto-detect).
LIVE_LANGUAGE_CODE = os.getenv("PITCHPILOT_LIVE_LANGUAGE_CODE", "en-US").strip() or None

COACH_INSTRUCTION = """
You are PitchPilot, a real-time AI presentation coach.

You receive:
1. The presenter's live speech (audio transcript)—may be noisy, mixed-language, or fragmented.
2. The current slide image whenever the slide changes.
3. The message "[Presenter is now on slide N]" when they change slides (N = current slide number).

Your goal is to help the presenter improve delivery WITHOUT interrupting their flow.

OUTPUT RULES (CRITICAL)
- Speak ONLY in complete, self-contained sentences. Never output fragments, mid-sentence cuts, or run-ons (e.g. no "Consider organizing... perhaps", "or 4, to maintain clarity", "Hello. You can start with the presentation" after the session has started).
- Each time you speak, give exactly 1–2 full sentences that make sense on their own. Do not start a sentence you cannot finish.
- If the transcript is unclear, mixed-language, or badly tokenized: ignore the literal words and give feedback only on delivery you can infer (e.g. pacing, clarity). Do not repeat, paraphrase, or refer to unclear transcript. Do not output greetings like "Hello, you can start" once the rehearsal is under way—only give delivery tips.
- Focus strictly on presentation delivery: pacing, filler words, clarity, slide alignment. Do not suggest reorganizing slide content or changing what they say; only how they deliver it.

SLIDE LABELLING
- When you know the current slide (from "[Presenter is now on slide N]"), start your spoken feedback with the slide number (e.g. "Slide 2: Slow down your pace slightly."). In record_feedback, include the slide number in the message (e.g. "Slide 2: Slow down your pace slightly.").
- If you have not seen a slide number yet, use "Slide 1" or omit the prefix.

CORE BEHAVIOR
- When the presenter could benefit from a tip, respond soon in 1–2 complete sentences. Do not wait for long pauses.
- Example of good feedback: "Slide 2: You're speaking a bit fast. Pause after each bullet so the audience can absorb it."

FEEDBACK PRIORITY (highest to lowest)
1. Excess filler words ("um", "like", "you know", "basically")
2. Poor pacing (too fast, too slow, long pauses)
3. Misalignment between speech and slide content
4. General clarity improvements

When multiple issues occur, focus on the MOST important one. One improvement per turn.

FEEDBACK STYLE
- Be supportive, calm, and constructive. Focus on actionable advice.
- Never criticize harshly.

REAL-TIME COACHING
- Respond promptly when there is a tip worth giving (roughly every 20–40 seconds if needed).
- Always call record_feedback with the same tip so it appears in Key takeaways. Use feedback_type = one of ["filler", "pacing", "clarity", "general"] and message = one complete sentence including slide number when known (e.g. "Slide 2: Slow down your pace slightly."). Message must be natural language only, 5–500 characters; no function names or syntax.

TOOL USAGE (IMPORTANT)
- Your spoken output must be ONLY natural language. Never say or output "record_feedback" or any function-call syntax. The tool is invoked separately; the user must never see or hear it.
- You MUST call the record_feedback tool for every concrete tip. Only skip when the presenter is doing well and you have nothing to suggest.

Q&A MODE
When Q&A mode is active: ask ONE question at a time, wait for the answer, give a brief evaluation, then the next question. No greetings or off-topic content.

GENERAL RULE
You are a supportive presentation coach. Output only complete, relevant delivery feedback. No fragments, no greetings mid-session, no repeating unclear transcript.
"""

CHALLENGE_INSTRUCTION = """
You are an interviewer in "Challenge Me" mode. Your role is to ask the user Q&A questions about the presentation slide(s) provided below.

YOU MUST SPEAK FIRST: As soon as the session starts, do not wait for the user. Give a very brief greeting (one short sentence) and immediately ask your first question based on the slide content. The user will then answer by voice.

RULES:
- Ask ONE question at a time about the slide content. Base questions only on the slide text(s) you are given.
- Wait for the user to answer (they will speak). Listen to their answer.
- Briefly evaluate their answer (one or two sentences): note what was good and, if relevant, what could be clearer.
- Then ask the next question. Keep alternating: question -> listen -> brief evaluation -> next question.
- Keep your spoken responses concise and natural for voice. Do not give long monologues.
- Do not discuss slide changes, coaching, or pacing—only Q&A about the slide content.
- If the user asks to stop or says they are done, wrap up politely and stop asking questions.
"""

# Tools enabled by default so the coach can call record_feedback (feedback list in UI)
_DISABLE_TOOLS = os.getenv("PITCHPILOT_DISABLE_LIVE_TOOLS", "").lower() in ("1", "true", "yes")
USE_TOOLS = not _DISABLE_TOOLS

RECORD_FEEDBACK_DECLARATION = {
    "name": "record_feedback",
    "description": "Record a coaching tip so it appears in the Key takeaways list in the UI. You MUST call this for every concrete tip you give (filler, pacing, clarity, or general)—otherwise the user will not see any key takeaways. Always include the slide number in the message (e.g. 'Slide 2: Slow down your pace slightly.') so feedback is grouped by slide.",
    "parameters": {
        "type": "object",
        "properties": {
            "feedback_type": {"type": "string", "description": "Category: filler, pacing, clarity, general"},
            "message": {"type": "string", "description": "Short, actionable feedback. Start with slide number, e.g. 'Slide 2: Slow down your pace slightly.'"},
        },
        "required": ["feedback_type", "message"],
    },
}


def _build_instruction(slide_texts: list[str] | None = None) -> str:
    """Build coach system instruction; append slide contents for slide evaluation when available."""
    text = COACH_INSTRUCTION.strip()
    if slide_texts:
        text += "\n\n--- Slide contents (for slide evaluation and alignment feedback) ---\n"
        text += "You will also see \"[Presenter is now on slide N]\" when they change slides.\n\n"
        for i, content in enumerate(slide_texts[:50], 1):  # cap at 50 slides
            excerpt = (content.strip() or "(no text)")[:800]  # limit length per slide
            text += f"Slide {i}:\n{excerpt}\n\n"
    return text


def _build_challenge_instruction(slide_texts: list[str]) -> str:
    """Build challenge-mode system instruction with the given slide content(s)."""
    text = CHALLENGE_INSTRUCTION.strip()
    text += "\n\n--- Slide content(s) to ask questions about ---\n\n"
    for i, content in enumerate(slide_texts[:50], 1):
        excerpt = (content.strip() or "(no text)")[:800]
        text += f"Slide {i}:\n{excerpt}\n\n"
    return text


def _live_config(
    slide_texts: list[str] | None = None,
    *,
    challenge_slide_texts: list[str] | None = None,
):
    """Build Live API config. If challenge_slide_texts is set, use challenge instruction and no tools."""
    if challenge_slide_texts is not None and len(challenge_slide_texts) > 0:
        instruction = _build_challenge_instruction(challenge_slide_texts)
        use_tools = False
    else:
        instruction = _build_instruction(slide_texts)
        use_tools = USE_TOOLS

    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": types.Content(
            role="user",
            parts=[types.Part(text=instruction)],
        ),
        "input_audio_transcription": types.AudioTranscriptionConfig(),
        "output_audio_transcription": types.AudioTranscriptionConfig(),
        "context_window_compression": types.ContextWindowCompressionConfig(
            trigger_tokens=10_000,
            sliding_window=types.SlidingWindow(target_tokens=5_000),
        ),
    }
    if LIVE_LANGUAGE_CODE:
        config["speech_config"] = types.SpeechConfig(language_code=LIVE_LANGUAGE_CODE)
    if use_tools:
        config["tools"] = [{"function_declarations": [RECORD_FEEDBACK_DECLARATION]}]
    return config


def _part_to_json(p) -> dict:
    """Serialize a Part to JSON, ensuring inline_data.data (audio bytes) is base64-encoded for the frontend."""
    d = p.model_dump(mode="json", exclude_none=True)
    # Ensure audio (and any blob) data is present so the frontend can play agent speech.
    inline = getattr(p, "inline_data", None)
    if inline is not None and getattr(inline, "data", None) is not None:
        blob_data = inline.data
        if isinstance(blob_data, bytes):
            if not isinstance(d.get("inline_data"), dict):
                d["inline_data"] = {}
            idict = d["inline_data"]
            if idict.get("data") is None:
                idict["data"] = base64.standard_b64encode(blob_data).decode("ascii")
            if idict.get("mime_type") is None:
                idict["mime_type"] = getattr(inline, "mime_type", None)
    return d


def _message_to_frontend(msg: types.LiveServerMessage) -> dict:
    """Serialize LiveServerMessage to the JSON shape the frontend expects."""
    out = {}
    try:
        if getattr(msg, "server_content", None):
            sc = msg.server_content
            if getattr(sc, "input_transcription", None) is not None:
                out["input_transcription"] = sc.input_transcription.model_dump(mode="json", exclude_none=True)
            if getattr(sc, "output_transcription", None) is not None:
                out["output_transcription"] = sc.output_transcription.model_dump(mode="json", exclude_none=True)
            if getattr(sc, "model_turn", None) and getattr(sc.model_turn, "parts", None):
                out["content"] = {
                    "parts": [_part_to_json(p) for p in sc.model_turn.parts]
                }
            if getattr(sc, "interrupted", None) is True:
                out["interrupted"] = True
        if getattr(msg, "tool_call", None) is not None:
            out["tool_call"] = msg.tool_call.model_dump(mode="json", exclude_none=True)
        if getattr(msg, "go_away", None) is not None:
            out["go_away"] = msg.go_away.model_dump(mode="json", exclude_none=True)
    except Exception as e:
        logger.warning("Serializing LiveServerMessage: %s", e)
    return out


def _sanitize_for_log(obj: dict) -> dict:
    """Replace base64 data with a placeholder so logs stay readable."""
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k == "data" and isinstance(v, str) and len(v) > 60:
            out[k] = f"<base64 len={len(v)}>"
        elif isinstance(v, dict):
            out[k] = _sanitize_for_log(v)
        elif isinstance(v, list):
            out[k] = [_sanitize_for_log(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


def _log_agent_output(payload: dict) -> None:
    """Log agent response only (no user transcript): output_transcription, content, tool_call, validated_feedback, etc."""
    if not payload:
        return
    agent_only = {
        k: v
        for k, v in payload.items()
        if k
        in (
            "output_transcription",
            "content",
            "tool_call",
            "validated_feedback",
            "interrupted",
            "go_away",
        )
    }
    if not agent_only:
        return
    to_log = _sanitize_for_log(agent_only)
    logger.info("Agent response: %s", json.dumps(to_log, default=str))


async def _run_downstream(sess, websocket, session_lock) -> None:
    """Run the receive loop for one Live API session. Raises when the connection is lost."""
    _receive = getattr(sess, "_receive", None)
    if _receive is None:
        while True:
            async for response in sess.receive():
                payload = _message_to_frontend(response)
                if getattr(response, "tool_call", None) and getattr(
                    response.tool_call, "function_calls", None
                ):
                    from app.agent.tools import record_feedback
                    from app.schemas.feedback import validate_feedback_args
                    function_responses = []
                    validated_messages = []
                    for fc in response.tool_call.function_calls:
                        if getattr(fc, "name", None) != "record_feedback":
                            function_responses.append(
                                types.FunctionResponse(
                                    name=fc.name,
                                    id=fc.id,
                                    response={"result": record_feedback("general", "")},
                                )
                            )
                            continue
                        raw_args = fc.args if hasattr(fc, "args") and fc.args else {}
                        validated = validate_feedback_args(raw_args)
                        if validated:
                            function_responses.append(
                                types.FunctionResponse(
                                    name=fc.name,
                                    id=fc.id,
                                    response={"result": record_feedback(
                                        validated.feedback_type,
                                        validated.message,
                                    )},
                                )
                            )
                            validated_messages.append(validated.message)
                        else:
                            function_responses.append(
                                types.FunctionResponse(
                                    name=fc.name,
                                    id=fc.id,
                                    response={"result": {"status": "error", "reason": "invalid_args"}},
                                )
                            )
                    if validated_messages and payload is not None:
                        payload["validated_feedback"] = [{"message": m} for m in validated_messages]
                    if function_responses:
                        await sess.send_tool_response(function_responses=function_responses)
                if payload:
                    _log_agent_output(payload)
                    await websocket.send_text(json.dumps(payload))
    else:
        while True:
            response = await _receive()
            payload = _message_to_frontend(response)
            if getattr(response, "tool_call", None) and getattr(
                response.tool_call, "function_calls", None
            ):
                from app.agent.tools import record_feedback
                from app.schemas.feedback import validate_feedback_args
                function_responses = []
                validated_messages = []
                for fc in response.tool_call.function_calls:
                    if getattr(fc, "name", None) != "record_feedback":
                        function_responses.append(
                            types.FunctionResponse(
                                name=fc.name,
                                id=fc.id,
                                response={"result": record_feedback("general", "")},
                            )
                        )
                        continue
                    raw_args = fc.args if hasattr(fc, "args") and fc.args else {}
                    validated = validate_feedback_args(raw_args)
                    if validated:
                        function_responses.append(
                            types.FunctionResponse(
                                name=fc.name,
                                id=fc.id,
                                response={"result": record_feedback(
                                    validated.feedback_type,
                                    validated.message,
                                )},
                            )
                        )
                        validated_messages.append(validated.message)
                    else:
                        function_responses.append(
                            types.FunctionResponse(
                                name=fc.name,
                                id=fc.id,
                                response={"result": {"status": "error", "reason": "invalid_args"}},
                            )
                        )
                if validated_messages and payload is not None:
                    payload["validated_feedback"] = [{"message": m} for m in validated_messages]
                if function_responses:
                    await sess.send_tool_response(function_responses=function_responses)
            if payload:
                _log_agent_output(payload)
                await websocket.send_text(json.dumps(payload))


async def run_live_session(
    websocket,
    session_id: str | None = None,
    mode: str | None = None,
    scope: str | None = None,
    slide_index: int | None = None,
) -> None:
    """Run a Live API session over the given WebSocket. Stays open until the client disconnects (Stop rehearsal).
    Reconnects to the Live API automatically on 1011, 1008, or connection loss so feedback continues until you stop.
    If session_id is provided, slide text content for that session is injected so the coach can give specific feedback.
    When mode='challenge', scope is 'all' or 'slide' and slide_index is used for single-slide scope; challenge instruction is used with no tools."""
    if not GOOGLE_API_KEY:
        await websocket.send_text(json.dumps({"error": "GOOGLE_API_KEY not set"}))
        return

    slide_texts: list[str] | None = None
    challenge_slide_texts: list[str] | None = None

    if session_id:
        try:
            from app.services import storage
            all_texts = storage.get_slide_texts(session_id)
            if all_texts is not None:
                if mode == "challenge" and scope:
                    if scope == "all":
                        challenge_slide_texts = all_texts
                    elif scope == "slide" and slide_index is not None and 0 <= slide_index < len(all_texts):
                        challenge_slide_texts = [all_texts[slide_index]]
                    else:
                        challenge_slide_texts = all_texts  # fallback to all if scope/slide_index invalid
                else:
                    slide_texts = all_texts
        except Exception as e:
            logger.debug("Could not load slide texts for session %s: %s", session_id, e)

    # Challenge mode with no slide texts (e.g. GCS-only): still use challenge instruction with placeholder
    if mode == "challenge" and challenge_slide_texts is None and scope:
        challenge_slide_texts = ["(No slide text available for this session. Ask general presentation or Q&A questions.)"]

    client = genai.Client(api_key=GOOGLE_API_KEY)
    config = _live_config(
        slide_texts=slide_texts,
        challenge_slide_texts=challenge_slide_texts,
    )
    session_ref: list = []  # [sess] or []
    session_lock = asyncio.Lock()

    async def upstream() -> None:
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message:
                    chunk = message["bytes"]
                    if not session_ref:
                        continue
                    async with session_lock:
                        if session_ref:
                            await session_ref[0].send_realtime_input(
                                audio=types.Blob(mime_type="audio/pcm;rate=16000", data=bytes(chunk))
                            )
                elif "text" in message:
                    try:
                        obj = json.loads(message["text"])
                        if obj.get("type") == "text" and session_ref:
                            async with session_lock:
                                if session_ref:
                                    await session_ref[0].send_realtime_input(text=obj["text"])
                        elif obj.get("type") == "image" and session_ref:
                            slide_index = obj.get("slideIndex")
                            if slide_index is not None:
                                try:
                                    n = int(slide_index)
                                    async with session_lock:
                                        if session_ref:
                                            await session_ref[0].send_realtime_input(
                                                text=f"[Presenter is now on slide {n}]"
                                            )
                                except (TypeError, ValueError):
                                    pass
                            data = base64.b64decode(obj["data"])
                            mime = obj.get("mimeType", "image/jpeg")
                            async with session_lock:
                                if session_ref:
                                    await session_ref[0].send_realtime_input(
                                        video=types.Blob(mime_type=mime, data=data)
                                    )
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Invalid WebSocket text message: %s", e)
        except Exception as e:
            logger.debug("Upstream ended: %s", e)

    def _should_reconnect(e: BaseException) -> bool:
        """True if we should auto-reconnect (1011, 1008, or connection loss)."""
        code = getattr(e, "code", None)
        if code in (1011, 1008):
            return True
        msg = str(e).lower()
        return "1011" in msg or "1008" in msg or "internal error" in msg or "not implemented" in msg or "not supported" in msg

    async def run_downstream_loop() -> None:
        """Connect to Live API and run downstream; reconnect on 1011/1008/connection loss until cancelled."""
        while True:
            session_ref.clear()
            try:
                async with client.aio.live.connect(model=DEMO_AGENT_MODEL, config=config) as sess:
                    session_ref.append(sess)
                    if mode == "challenge":
                        try:
                            await sess.send_realtime_input(
                                text="The user has joined the challenge. Greet them briefly and ask your first question."
                            )
                        except Exception as e:
                            logger.debug("Challenge start trigger failed: %s", e)
                    try:
                        await _run_downstream(sess, websocket, session_lock)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        reconnect = _should_reconnect(e)
                        if reconnect:
                            logger.warning("Live API connection closed (code %s). Reconnecting…", getattr(e, "code", None))
                        else:
                            logger.warning("Live connection error: %s", e)
                        # Notify client first so they show "Reconnecting…" before we sleep
                        try:
                            await websocket.send_text(json.dumps({"reconnecting": True}))
                        except Exception:
                            pass
                        session_ref.clear()
                        await asyncio.sleep(2 if reconnect else 1)
                        continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Live connection error: %s", e)
                try:
                    await websocket.send_text(json.dumps({"reconnecting": True}))
                except Exception:
                    pass
                session_ref.clear()
                await asyncio.sleep(2)

    downstream_task = None
    try:
        upstream_task = asyncio.create_task(upstream())
        downstream_task = asyncio.create_task(run_downstream_loop())
        # Session stays open until client disconnects (Stop rehearsal)
        await upstream_task
    except Exception as e:
        logger.exception("Live session error: %s", e)
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        if downstream_task is not None:
            downstream_task.cancel()
            try:
                await downstream_task
            except asyncio.CancelledError:
                pass
        session_ref.clear()
