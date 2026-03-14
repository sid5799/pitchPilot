"""Generate predicted audience questions from slide images using Gemini."""
import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_slides_for_session(session_id: str) -> Optional[list[bytes]]:
    """Get slide image bytes for a session (in-memory only for now)."""
    from . import storage
    return storage.get_all_slides_from_memory(session_id)


def generate_predicted_questions(session_id: str, max_questions: int = 5) -> list[str]:
    """
    Use Gemini to generate likely audience questions based on slide images.
    Returns a list of question strings.
    """
    slides = get_slides_for_session(session_id)
    if not slides:
        return []

    try:
        from google import genai
    except ImportError:
        logger.warning("google.genai not available for question generation")
        return []

    try:
        client = genai.Client()
    except Exception as e:
        logger.warning("Genai client init failed (set GOOGLE_API_KEY or Vertex env): %s", e)
        return []

    from google.genai import types
    part_list = []
    for img_bytes in slides[:15]:
        part_list.append(types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=img_bytes)))
    part_list.append(types.Part(text=(
        f"Based on these presentation slides only, generate {max_questions} likely questions "
        "an audience might ask after this presentation. Return ONLY a JSON array of question strings, "
        'e.g. ["Question 1?", "Question 2?"]'
    )))

    try:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_QUESTION_MODEL", "gemini-2.0-flash"),
            contents=[types.Content(role="user", parts=part_list)],
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text and getattr(response, "candidates", None) and response.candidates:
            c0 = response.candidates[0]
            if getattr(c0, "content", None) and getattr(c0.content, "parts", None):
                text = (getattr(c0.content.parts[0], "text", None) or "").strip()
        if not text:
            return []
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        import json
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(q) for q in arr[:max_questions]]
        return []
    except Exception as e:
        logger.exception("Question generation failed: %s", e)
        return []
