"""Parse PDF and PPTX into slide images. PPTX uses in-memory render (python-pptx + Pillow); no LibreOffice required."""
import io
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# EMU to inches: 914400 EMU = 1 inch (python-pptx)
_EMU_PER_INCH = 914400


def _pdf_to_images_pymupdf(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Convert PDF to JPEG bytes using PyMuPDF (no system deps)."""
    import fitz  # pymupdf
    from PIL import Image
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = []
    for page in doc:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        out.append(buf.getvalue())
    doc.close()
    return out


def _pdf_to_images_poppler(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Convert PDF to JPEG bytes using pdf2image (requires poppler)."""
    from pdf2image import convert_from_bytes
    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    out = []
    buf = io.BytesIO()
    for img in images:
        buf.seek(0)
        buf.truncate(0)
        img.save(buf, format="JPEG", quality=85)
        out.append(buf.getvalue())
    return out


def parse_pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Convert PDF pages to JPEG image bytes. Uses PyMuPDF first (no system deps), else pdf2image if poppler is installed."""
    try:
        return _pdf_to_images_pymupdf(pdf_bytes, dpi=dpi)
    except Exception as e:
        logger.debug("PyMuPDF PDF render failed: %s", e)
    try:
        return _pdf_to_images_poppler(pdf_bytes, dpi=dpi)
    except Exception as e:
        if "poppler" in str(e).lower() or "pdfinfo" in str(e).lower():
            raise RuntimeError(
                "PDF rendering failed. Install poppler (e.g. on macOS: brew install poppler) or ensure pymupdf is working."
            ) from e
        raise


def _emu_to_px(emu_val, dpi: int = 150) -> int:
    """Convert EMU (int or Length with .inches) to pixels at given DPI."""
    if hasattr(emu_val, "inches"):
        return int(emu_val.inches * dpi)
    return int(emu_val / _EMU_PER_INCH * dpi)


def _pptx_to_images_memory(pptx_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """
    Convert PPTX to JPEG image bytes using python-pptx + Pillow only (in-memory, no LibreOffice).
    Renders each slide as an image: background, text from shapes, and embedded pictures.
    """
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from PIL import Image, ImageDraw, ImageFont

    prs = Presentation(io.BytesIO(pptx_bytes))
    w_emu = prs.slide_width
    h_emu = prs.slide_height
    if w_emu is None or h_emu is None:
        raise ValueError("Presentation has no slide dimensions.")
    width_px = _emu_to_px(w_emu, dpi)
    height_px = _emu_to_px(h_emu, dpi)
    # Clamp to reasonable size
    width_px = min(max(width_px, 100), 4096)
    height_px = min(max(height_px, 100), 4096)

    out: list[bytes] = []
    if not prs.slides:
        raise ValueError("Presentation has no slides.")
    for slide in prs.slides:
        img = Image.new("RGB", (width_px, height_px), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        font_size = max(12, height_px // 40)
        font = None
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()

        for shape in slide.shapes:
            left_px = _emu_to_px(shape.left, dpi)
            top_px = _emu_to_px(shape.top, dpi)
            shape_w_px = _emu_to_px(shape.width, dpi)
            shape_h_px = _emu_to_px(shape.height, dpi)
            if shape.has_text_frame:
                text = shape.text_frame.text or ""
                if text.strip():
                    # Wrap long text into the shape width (approx)
                    draw.rectangle(
                        [left_px, top_px, left_px + shape_w_px, top_px + shape_h_px],
                        outline=(200, 200, 200),
                        fill=(255, 255, 255),
                    )
                    draw.text((left_px + 4, top_px + 4), text.strip()[:500], fill=(0, 0, 0), font=font)
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE and getattr(shape, "image", None):
                try:
                    blob = shape.image.blob
                    pic = Image.open(io.BytesIO(blob)).convert("RGB")
                    pic.thumbnail((shape_w_px, shape_h_px), Image.Resampling.LANCZOS)
                    x = left_px + (shape_w_px - pic.width) // 2
                    y = top_px + (shape_h_px - pic.height) // 2
                    img.paste(pic, (max(0, x), max(0, y)))
                except Exception as e:
                    logger.debug("Skip picture shape: %s", e)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        out.append(buf.getvalue())
    return out


def _pptx_to_images_libreoffice(pptx_bytes: bytes, dpi: int = 150) -> list[bytes] | None:
    """Convert PPTX to images via LibreOffice (PDF). Returns None if LibreOffice is not available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pptx_path = Path(tmpdir) / "input.pptx"
        pptx_path.write_bytes(pptx_bytes)
        pdf_path = Path(tmpdir) / "input.pdf"
        # Prefer soffice on PATH; common macOS path if installed via .dmg
        for soffice in ("soffice", "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
            cmd = [
                soffice,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(tmpdir),
                str(pptx_path),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=120)
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        else:
            return None
        if not pdf_path.exists():
            return None
        return parse_pdf_to_images(pdf_path.read_bytes(), dpi=dpi)


def parse_pptx_to_images(pptx_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """
    Convert PPTX to slide image bytes. Prefer LibreOffice for faithful rendering (matches PowerPoint).
    Fall back to in-memory render (python-pptx + Pillow) when LibreOffice is not installed.
    """
    # Try LibreOffice first so slides look like the original (theme, fonts, graphics)
    try:
        out = _pptx_to_images_libreoffice(pptx_bytes, dpi=dpi)
        if out:
            return out
    except Exception as e:
        logger.debug("LibreOffice PPTX conversion failed: %s", e)
    # Fallback: in-memory render (no external deps; looks simpler)
    return _pptx_to_images_memory(pptx_bytes, dpi=dpi)


def parse_presentation_to_images(file_bytes: bytes, filename: str) -> list[bytes]:
    """
    Parse a presentation file (PDF or PPTX) into a list of JPEG image bytes.
    """
    name_lower = filename.lower()
    if name_lower.endswith(".pdf"):
        return parse_pdf_to_images(file_bytes)
    if name_lower.endswith(".pptx"):
        return parse_pptx_to_images(file_bytes)
    raise ValueError("Unsupported format. Use PDF or PPTX.")


def parse_pdf_to_texts(pdf_bytes: bytes) -> list[str]:
    """Extract text from each PDF page (for coach context)."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        out = [page.get_text().strip() or "(no text)" for page in doc]
        doc.close()
        return out
    except Exception as e:
        logger.debug("PDF text extraction failed: %s", e)
        return []


def parse_pptx_to_texts(pptx_bytes: bytes) -> list[str]:
    """Extract text from each PPTX slide (for coach context)."""
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(pptx_bytes))
        out = []
        for slide in prs.slides:
            parts = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False) and shape.text_frame:
                    text = (shape.text_frame.text or "").strip()
                    if text:
                        parts.append(text)
            out.append("\n".join(parts) if parts else "(no text)")
        return out
    except Exception as e:
        logger.debug("PPTX text extraction failed: %s", e)
        return []


def parse_presentation_to_texts(file_bytes: bytes, filename: str) -> list[str]:
    """Extract text from each slide/page for use in coach feedback. Returns one string per slide."""
    name_lower = filename.lower()
    if name_lower.endswith(".pdf"):
        return parse_pdf_to_texts(file_bytes)
    if name_lower.endswith(".pptx"):
        return parse_pptx_to_texts(file_bytes)
    return []
