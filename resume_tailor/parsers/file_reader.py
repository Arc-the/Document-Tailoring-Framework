"""Read resume/JD content from various file formats (txt, pdf, docx)."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}

# Bullet markers used in resumes
_BULLET_RE = re.compile(r"^\s*[-•*–▪▸▹►◦◉○▫▬]\s")

# Section headers
_SECTION_RE = re.compile(
    r"(?i)^(professional\s+)?(experience|education|skills|summary|projects|"
    r"certifications?|publications?|awards?|volunteer|objective|profile|"
    r"technical\s+skills|core\s+competencies|work\s+experience)"
)

# Experience entry headers — lines with separators and/or dates
_HEADER_RE = re.compile(
    r"[|—\-–].*(?:\d{4}|Present|Current|In Progress)",
    re.IGNORECASE,
)


def read_file(path: Path) -> str:
    """Read text content from a file. Supports .txt, .pdf, and .docx."""
    ext = path.suffix.lower()

    if ext == ".txt":
        return path.read_text(encoding="utf-8")

    if ext == ".pdf":
        return _read_pdf(path)

    if ext == ".docx":
        return _read_docx(path)

    raise ValueError(
        f"Unsupported file format: '{ext}'. "
        f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )


def _is_structural_line(line: str) -> bool:
    """Check if a line is a bullet, section header, or experience header."""
    stripped = line.strip()
    if not stripped:
        return True  # blank lines are structural boundaries
    if _BULLET_RE.match(stripped):
        return True
    if _SECTION_RE.match(stripped.rstrip(":")):
        return True
    if _HEADER_RE.search(stripped):
        return True
    return False


def _rejoin_wrapped_lines(text: str) -> str:
    """Rejoin lines that were wrapped by PDF column width.

    PDF extraction often breaks long bullet points across multiple lines.
    This function joins continuation lines back to their parent line.

    A line is a continuation if:
    - It's not blank
    - It's not a bullet, section header, or experience entry header
    - The previous non-blank line exists and doesn't end with a period-newline boundary
    """
    lines = text.split("\n")
    result = []

    for line in lines:
        stripped = line.strip()

        # Empty lines pass through
        if not stripped:
            result.append("")
            continue

        # Structural lines (bullets, headers) start a new line
        if _is_structural_line(stripped):
            result.append(line)
            continue

        # Continuation line — append to previous non-blank line
        if result:
            # Find the last non-blank line to append to
            for i in range(len(result) - 1, -1, -1):
                if result[i].strip():
                    result[i] = result[i].rstrip() + " " + stripped
                    break
            else:
                # No previous non-blank line, just add it
                result.append(line)
        else:
            result.append(line)

    return "\n".join(result)


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF file using pdfplumber.

    Includes line-rejoin logic to handle wrapped bullet points.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "pdfplumber is required for PDF input. "
            "Install with: pip install pdfplumber"
        )

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

    if not pages:
        logger.warning(f"No text extracted from PDF: {path}")
        return ""

    raw = "\n\n".join(pages)
    return _rejoin_wrapped_lines(raw)


def _read_docx(path: Path) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        import docx
    except ImportError:
        raise ImportError(
            "python-docx is required for DOCX input. "
            "Install with: pip install python-docx"
        )

    doc = docx.Document(str(path))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    if not paragraphs:
        logger.warning(f"No text extracted from DOCX: {path}")
        return ""

    return "\n".join(paragraphs)
