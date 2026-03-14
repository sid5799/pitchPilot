"""Upload presentation (PDF/PPTX) and return session + slide URLs; generate Q&A questions."""
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from ..services import question_generator, slide_parser, storage

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = (".pdf", ".pptx")


@router.post("/upload")
async def upload_presentation(file: UploadFile = File(..., description="PDF or PPTX file")):
    """Accept PDF or PPTX; parse to slides; upload to GCS or store in memory; return session_id and slide URLs."""
    filename = file.filename or ""
    if not any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Only PDF and PPTX files are allowed.")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50 MB).")

    try:
        slide_images = slide_parser.parse_presentation_to_images(raw, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not slide_images:
        raise HTTPException(status_code=422, detail="No slides found in the presentation.")

    slide_texts = slide_parser.parse_presentation_to_texts(raw, filename)
    if len(slide_texts) != len(slide_images):
        slide_texts = []

    session_id = storage.generate_session_id()
    urls = storage.upload_slides_to_gcs(session_id, slide_images, slide_texts=slide_texts or None)
    return {"session_id": session_id, "slide_urls": urls, "slide_count": len(urls)}


@router.get("/session/{session_id}/slide/{index}")
def get_slide_image(session_id: str, index: int):
    """Serve a slide image for in-memory sessions (when GCS is not configured)."""
    try:
        idx = int(index)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid slide index.")
    data = storage.get_slide_from_memory(session_id, idx)
    if data is None:
        raise HTTPException(status_code=404, detail="Slide not found.")
    return Response(content=data, media_type="image/jpeg")


@router.post("/session/{session_id}/generate-questions")
def generate_questions(session_id: str, max_questions: int = 5):
    """Generate predicted audience questions from the session's slides (in-memory only)."""
    questions = question_generator.generate_predicted_questions(session_id, max_questions=max_questions)
    return {"questions": questions}
