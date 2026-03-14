"""Storage for uploads and slide images (GCS or in-memory fallback)."""
import io
import os
import uuid
from typing import Optional

# In-memory fallback when GCS bucket not set (key: session_id, value: list of image bytes)
_sessions: dict[str, list[bytes]] = {}
# Slide text content per session (for coach context; in-memory only)
_session_texts: dict[str, list[str]] = {}


def _bucket() -> Optional[str]:
    return os.environ.get("PITCHPILOT_GCS_BUCKET") or None


def generate_session_id() -> str:
    return str(uuid.uuid4())


def upload_slides_to_gcs(
    session_id: str,
    slide_images: list[bytes],
    content_type: str = "image/jpeg",
    slide_texts: list[str] | None = None,
) -> list[str]:
    """Upload slide images to GCS; return list of public/signed URLs. Optionally store slide texts (in-memory only)."""
    bucket_name = _bucket()
    if not bucket_name:
        # In-memory fallback for local dev
        _sessions[session_id] = slide_images
        if slide_texts is not None and len(slide_texts) == len(slide_images):
            _session_texts[session_id] = slide_texts
        return [f"/api/session/{session_id}/slide/{i}" for i in range(len(slide_images))]

    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        urls = []
        for i, img_bytes in enumerate(slide_images):
            blob = bucket.blob(f"sessions/{session_id}/slide_{i:03d}.jpg")
            blob.upload_from_string(img_bytes, content_type=content_type)
            urls.append(blob.public_url if blob.public_url else blob.generate_signed_url(expiration=3600))
        return urls
    except Exception as e:
        raise RuntimeError(f"GCS upload failed: {e}") from e


def get_slide_from_memory(session_id: str, index: int) -> Optional[bytes]:
    """Return slide image bytes for in-memory sessions (for GET /session/.../slide/...)."""
    if session_id not in _sessions:
        return None
    slides = _sessions[session_id]
    if index < 0 or index >= len(slides):
        return None
    return slides[index]


def get_all_slides_from_memory(session_id: str) -> Optional[list[bytes]]:
    """Return all slide image bytes for a session (for question generation)."""
    return list(_sessions[session_id]) if session_id in _sessions else None


def get_slide_texts(session_id: str) -> Optional[list[str]]:
    """Return slide text content for a session (for coach context). In-memory only."""
    return list(_session_texts[session_id]) if session_id in _session_texts else None
