"""Resume parsing into structured form.

Splits a plain-text resume into experience blocks with IDs so downstream
nodes can reference specific bullets by experience_id.
"""

import re
from doc_tailor.plugins.resume.models import ExperienceBlock, ParsedResume, ResumeBullet


# Section headers commonly found in resumes
SECTION_PATTERNS = [
    (r"(?i)^(?:professional\s+)?(?:work\s+)?experience", "experience"),
    (r"(?i)^(?:education|academic)", "education"),
    (r"(?i)^(?:projects|personal\s+projects|side\s+projects)", "projects"),
    (r"(?i)^(?:skills|technical\s+skills|core\s+competencies)", "skills"),
    (r"(?i)^(?:summary|professional\s+summary|objective|profile)", "summary"),
    (r"(?i)^(?:certifications?|licenses?)", "certifications"),
    (r"(?i)^(?:publications?|papers?)", "publications"),
    (r"(?i)^(?:awards?|honors?|achievements?)", "awards"),
    (r"(?i)^(?:volunteer|community)", "volunteer"),
]

# Pattern for experience entry headers
EXPERIENCE_HEADER_PATTERN = re.compile(
    r"^(.+?)\s*(?:[—\-–|,])\s*(.+?)(?:\s*(?:[—\-–|,])\s*(.+?))?$"
)

# Bullet point markers
BULLET_PATTERN = re.compile(r"^\s*[-•*–]\s+(.+)")


def _slugify(text: str) -> str:
    """Create a simple slug from text for use as experience_id."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return slug.strip("_")[:50]


def _detect_section(line: str) -> str | None:
    """Check if a line is a section header."""
    stripped = line.strip().rstrip(":")
    for pattern, section_name in SECTION_PATTERNS:
        if re.match(pattern, stripped):
            return section_name
    return None


def _is_bullet(line: str) -> bool:
    """Check if a line is a bullet point."""
    return bool(BULLET_PATTERN.match(line))


def _extract_bullet_text(line: str) -> str:
    """Extract text from a bullet point line."""
    match = BULLET_PATTERN.match(line)
    if match:
        return match.group(1).strip()
    return line.strip()


def _looks_like_entry_header(line: str) -> bool:
    """Heuristic: does this line look like an experience entry header?"""
    stripped = line.strip()

    if not stripped or len(stripped) < 5:
        return False

    if _is_bullet(stripped):
        return False

    has_separator = bool(re.search(r"[—\-–|]", stripped))

    has_date = bool(re.search(
        r"(?:\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\b.*\d{4}|Present|Current)",
        stripped,
        re.IGNORECASE,
    ))

    return has_separator or has_date


def parse_resume(text: str) -> ParsedResume:
    """Parse a plain-text resume into a structured ParsedResume."""
    lines = text.strip().split("\n")
    parsed = ParsedResume(raw_text=text)

    current_section = ""
    current_block: ExperienceBlock | None = None
    blocks: list[ExperienceBlock] = []
    skills_lines: list[str] = []
    summary_lines: list[str] = []
    block_counter = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        section = _detect_section(stripped)
        if section:
            if current_block and current_block.bullets:
                blocks.append(current_block)
                current_block = None
            current_section = section
            continue

        if current_section == "skills":
            items = re.split(r"[,;•|]", stripped)
            for item in items:
                item = item.strip().strip("-•* ")
                if item and len(item) > 1:
                    parsed.skills.append(item)
            continue

        if current_section == "summary":
            summary_lines.append(stripped)
            continue

        if current_section in ("experience", "education", "projects", "volunteer", ""):
            if _is_bullet(stripped):
                bullet_text = _extract_bullet_text(stripped)
                if current_block is None:
                    block_counter += 1
                    current_block = ExperienceBlock(
                        experience_id=f"block_{block_counter:03d}",
                        section=current_section or "experience",
                    )
                current_block.bullets.append(ResumeBullet(
                    text=bullet_text,
                    experience_id=current_block.experience_id,
                ))
            elif _looks_like_entry_header(stripped):
                if current_block and current_block.bullets:
                    blocks.append(current_block)

                block_counter += 1
                match = EXPERIENCE_HEADER_PATTERN.match(stripped)
                if match:
                    parts = [p.strip() for p in match.groups() if p]
                    company = parts[0] if len(parts) > 0 else ""
                    title = parts[1] if len(parts) > 1 else ""
                    dates = parts[2] if len(parts) > 2 else ""
                else:
                    company = stripped
                    title = ""
                    dates = ""

                exp_id = _slugify(f"{company}_{title}") or f"block_{block_counter:03d}"
                current_block = ExperienceBlock(
                    experience_id=exp_id,
                    company=company,
                    title=title,
                    dates=dates,
                    section=current_section or "experience",
                )

    if current_block and current_block.bullets:
        blocks.append(current_block)

    parsed.experience_blocks = blocks
    parsed.summary = " ".join(summary_lines)

    return parsed
