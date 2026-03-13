"""Deterministic validation utilities for the document tailoring pipeline.

These functions enforce hard constraints without LLM calls:
- Text matching (exact + fuzzy)
- Sanity checks for the final output
"""

import re
from difflib import SequenceMatcher


def clean_input_text(text: str) -> str:
    """Clean raw input text from copy-paste or PDF extraction.

    Handles common artifacts without altering meaningful content.
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


def find_best_match(
    claimed_text: str,
    actual_texts: set[str],
    threshold: float = 0.85,
) -> str | None:
    """Find the best matching text segment from the source document.

    Returns the matched text if above threshold, None otherwise.
    Tries exact match first, then prefix/substring match, then fuzzy match.
    """
    # Strip trailing "..." that LLMs often add when truncating
    cleaned_claim = claimed_text.rstrip(".").rstrip()
    normalized_claim = normalize_text(cleaned_claim)

    if not normalized_claim:
        return None

    # Exact match (after normalization)
    for text in actual_texts:
        if normalize_text(text) == normalized_claim:
            return text

    # Prefix match — LLM truncated the text
    if len(normalized_claim) >= 30:
        for text in actual_texts:
            norm_text = normalize_text(text)
            if norm_text.startswith(normalized_claim):
                return text
            if normalized_claim.startswith(norm_text):
                return text

    # Substring match — LLM quoted a middle portion
    if len(normalized_claim) >= 40:
        for text in actual_texts:
            norm_text = normalize_text(text)
            if normalized_claim in norm_text or norm_text in normalized_claim:
                return text

    # Fuzzy match
    best_score = 0.0
    best_match = None
    for text in actual_texts:
        score = fuzzy_match_score(cleaned_claim, text)
        if score > best_score:
            best_score = score
            best_match = text

    if best_score >= threshold:
        return best_match
    return None


# Backwards-compatible alias
find_best_bullet_match = find_best_match


def check_duplicate_bullets(text: str) -> list[tuple[str, str, float]]:
    """Find near-duplicate bullet points in the generated output.

    Returns list of (item_a, item_b, similarity_score) tuples.
    """
    lines = text.strip().split("\n")
    bullets = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("-", "•", "*", "–")):
            cleaned = re.sub(r"^[-•*–]\s*", "", stripped)
            if len(cleaned) > 20:
                bullets.append(cleaned)

    duplicates = []
    for i in range(len(bullets)):
        for j in range(i + 1, len(bullets)):
            score = fuzzy_match_score(bullets[i], bullets[j])
            if score > 0.75:
                duplicates.append((bullets[i], bullets[j], score))

    return duplicates


def estimate_page_count(text: str, chars_per_page: int = 3000) -> int:
    """Rough estimate of page count based on character count."""
    return max(1, (len(text) + chars_per_page - 1) // chars_per_page)
