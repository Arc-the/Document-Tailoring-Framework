"""Deterministic validation utilities for the resume tailoring pipeline.

These functions enforce hard constraints without LLM calls:
- Bullet text matching (exact + fuzzy)
- Source annotation verification
- Sanity checks for the final resume
"""

import re
from difflib import SequenceMatcher

from resume_tailor.models import (
    EvidenceEntry,
    EvidenceMap,
    ParsedResume,
    SourceAnnotation,
)


def clean_input_text(text: str) -> str:
    """Clean raw input text from copy-paste or PDF extraction.

    Handles common artifacts without altering meaningful content:
    - Non-breaking spaces and other unicode whitespace
    - Excessive blank lines
    - Smart quotes and fancy dashes
    - Stray bullet unicode characters at line starts
    - Leading/trailing whitespace per line
    """
    # Replace non-breaking spaces and other unicode whitespace with regular space
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")   # zero-width space
    text = text.replace("\ufeff", "")   # BOM
    text = text.replace("\t", "    ")   # tabs to spaces

    # Normalize smart quotes and fancy dashes
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2022", "-")  # bullet dot → dash
    text = text.replace("\u25cf", "-")  # black circle
    text = text.replace("\u25cb", "-")  # white circle
    text = text.replace("\u25aa", "-")  # small black square
    text = text.replace("\u2023", "-")  # triangular bullet

    # Strip trailing whitespace per line, collapse 3+ blank lines to 2
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned = []
    blank_count = 0
    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                cleaned.append("")
        else:
            blank_count = 0
            cleaned.append(line)

    return "\n".join(cleaned).strip()


def normalize_text(text: str) -> str:
    """Normalize whitespace and punctuation for comparison."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Normalize common punctuation variants
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return text


def fuzzy_match_score(a: str, b: str) -> float:
    """Return similarity ratio between two strings after normalization."""
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def find_best_bullet_match(
    claimed_bullet: str,
    actual_bullets: set[str],
    threshold: float = 0.85,
) -> str | None:
    """Find the best matching bullet from the resume.

    Returns the matched bullet text if above threshold, None otherwise.
    Tries exact match first, then prefix/substring match, then fuzzy match.
    """
    # Strip trailing "..." that LLMs often add when truncating
    cleaned_claim = claimed_bullet.rstrip(".").rstrip()
    normalized_claim = normalize_text(cleaned_claim)

    if not normalized_claim:
        return None

    # Exact match (after normalization)
    for bullet in actual_bullets:
        if normalize_text(bullet) == normalized_claim:
            return bullet

    # Prefix match — LLM truncated the bullet
    # If the claimed text (minus trailing ...) is a prefix of a real bullet
    if len(normalized_claim) >= 30:  # only for meaningful-length prefixes
        for bullet in actual_bullets:
            norm_bullet = normalize_text(bullet)
            if norm_bullet.startswith(normalized_claim):
                return bullet
            # Also check if the real bullet starts with the claim
            if normalized_claim.startswith(norm_bullet):
                return bullet

    # Substring match — LLM quoted a middle portion
    if len(normalized_claim) >= 40:
        for bullet in actual_bullets:
            norm_bullet = normalize_text(bullet)
            if normalized_claim in norm_bullet or norm_bullet in normalized_claim:
                return bullet

    # Fuzzy match
    best_score = 0.0
    best_match = None
    for bullet in actual_bullets:
        score = fuzzy_match_score(cleaned_claim, bullet)
        if score > best_score:
            best_score = score
            best_match = bullet

    if best_score >= threshold:
        return best_match
    return None


def validate_evidence_map(
    evidence_map: EvidenceMap,
    parsed_resume: ParsedResume,
    threshold: float = 0.85,
) -> tuple[list[EvidenceEntry], list[EvidenceEntry]]:
    """Validate that all evidence entries reference real resume bullets.

    Returns:
        (valid_entries, rejected_entries)
    """
    actual_bullets = parsed_resume.get_bullet_text_set()
    valid = []
    rejected = []

    for mapping in evidence_map.mappings:
        for entry in mapping.evidence:
            match = find_best_bullet_match(
                entry.source_bullet, actual_bullets, threshold
            )
            if match is not None:
                # Update to the exact text from the resume
                entry.source_bullet = match
                valid.append(entry)
            else:
                rejected.append(entry)

    return valid, rejected


def validate_source_annotations(
    annotations: list[SourceAnnotation],
    parsed_resume: ParsedResume,
    threshold: float = 0.85,
) -> tuple[list[SourceAnnotation], list[SourceAnnotation]]:
    """Validate that source annotations reference real resume bullets.

    Returns:
        (valid_annotations, invalid_annotations)
    """
    actual_bullets = parsed_resume.get_bullet_text_set()
    valid = []
    invalid = []

    for ann in annotations:
        match = find_best_bullet_match(
            ann.source_bullet, actual_bullets, threshold
        )
        if match is not None:
            ann.source_bullet = match
            valid.append(ann)
        else:
            invalid.append(ann)

    return valid, invalid


def check_duplicate_bullets(resume_text: str) -> list[tuple[str, str, float]]:
    """Find near-duplicate bullet points in the generated resume.

    Returns list of (bullet_a, bullet_b, similarity_score) tuples.
    """
    # Extract bullet-like lines
    lines = resume_text.strip().split("\n")
    bullets = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("-", "•", "*", "–")):
            # Remove the bullet marker
            cleaned = re.sub(r"^[-•*–]\s*", "", stripped)
            if len(cleaned) > 20:  # skip very short lines
                bullets.append(cleaned)

    duplicates = []
    for i in range(len(bullets)):
        for j in range(i + 1, len(bullets)):
            score = fuzzy_match_score(bullets[i], bullets[j])
            if score > 0.75:
                duplicates.append((bullets[i], bullets[j], score))

    return duplicates


def check_verb_tense_consistency(resume_text: str) -> bool:
    """Basic check for verb tense consistency in bullet points.

    Checks if bullets consistently start with past or present tense.
    Returns True if consistent, False otherwise.
    """
    lines = resume_text.strip().split("\n")
    bullets = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("-", "•", "*", "–")):
            cleaned = re.sub(r"^[-•*–]\s*", "", stripped).strip()
            if cleaned:
                bullets.append(cleaned)

    if not bullets:
        return True

    # Common past tense endings
    past_pattern = re.compile(r"^(Led|Built|Designed|Developed|Implemented|Created|"
                              r"Managed|Achieved|Reduced|Improved|Increased|Delivered|"
                              r"Established|Launched|Migrated|Optimized|Streamlined|"
                              r"Coordinated|Architected|Automated|Deployed|Integrated|"
                              r"Resolved|Spearheaded|Mentored|Conducted|Analyzed|"
                              r"Collaborated|Maintained|Configured|Engineered|"
                              r"Refactored|Orchestrated|Transformed|Facilitated|"
                              r"Negotiated|Executed|Pioneered)\b", re.IGNORECASE)

    # Common present tense patterns
    present_pattern = re.compile(r"^(Lead|Build|Design|Develop|Implement|Create|"
                                 r"Manage|Achieve|Reduce|Improve|Increase|Deliver|"
                                 r"Establish|Launch|Migrate|Optimize|Streamline|"
                                 r"Coordinate|Architect|Automate|Deploy|Integrate|"
                                 r"Resolve|Spearhead|Mentor|Conduct|Analyze|"
                                 r"Collaborate|Maintain|Configure|Engineer|"
                                 r"Refactor|Orchestrate|Transform|Facilitate|"
                                 r"Negotiate|Execute|Pioneer)\b", re.IGNORECASE)

    past_count = sum(1 for b in bullets if past_pattern.match(b))
    present_count = sum(1 for b in bullets if present_pattern.match(b))

    total_matched = past_count + present_count
    if total_matched == 0:
        return True  # can't determine, assume ok

    # Allow some mixing (current job present, past jobs past)
    # Flag only if it's roughly 50/50 split
    if total_matched > 4:
        ratio = min(past_count, present_count) / total_matched
        return ratio < 0.35  # less than 35% minority tense is acceptable

    return True


def estimate_page_count(resume_text: str, chars_per_page: int = 3000) -> int:
    """Rough estimate of page count based on character count."""
    return max(1, (len(resume_text) + chars_per_page - 1) // chars_per_page)
