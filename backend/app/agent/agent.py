"""PitchPilot Live presentation coach agent (ADK + Gemini Live API)."""
import os

from google.adk.agents import Agent

from .tools import record_feedback

# Live API model. For Gemini API (API key) use a model that supports bidiGenerateContent (v1alpha).
# Documented Live models: gemini-2.0-flash-live-preview-04-09, gemini-2.5-flash-native-audio-preview-12-2025
_USE_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
_DEFAULT_MODEL = (
    "gemini-2.5-flash-native-audio-preview-12-2025" if _USE_VERTEX else "gemini-2.0-flash-live-preview-04-09"
)
MODEL = os.getenv("DEMO_AGENT_MODEL", _DEFAULT_MODEL)

# Tools: enabled for gemini-2.0-flash-live (reference uses tools); optional override via env
_ENABLE_TOOLS_ENV = os.getenv("PITCHPILOT_ENABLE_LIVE_TOOLS", "").lower() in ("1", "true", "yes")
_DISABLE_TOOLS_ENV = os.getenv("PITCHPILOT_DISABLE_LIVE_TOOLS", "").lower() in ("1", "true", "yes")
_USE_TOOLS = (_ENABLE_TOOLS_ENV or "flash-live" in MODEL.lower()) and not _DISABLE_TOOLS_ENV

# Single source of truth: same instruction as SDK Live path (live_session.py)
from app.live_session import COACH_INSTRUCTION

root_agent = Agent(
    name="pitchpilot_coach",
    model=MODEL,
    description="Real-time presentation coach: feedback on filler words, pacing, clarity; Q&A practice.",
    instruction=COACH_INSTRUCTION,
    tools=[record_feedback] if _USE_TOOLS else [],
)
