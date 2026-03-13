"""Resume-specific validation functions."""

import re
import logging

from doc_tailor.plugins.resume.models import ParsedResume, SourceAnnotation
from doc_tailor.utils.validation import find_best_match

logger = logging.getLogger(__name__)


def check_verb_tense_consistency(resume_text: str) -> bool:
    """Basic check for verb tense consistency in bullet points.

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

    past_pattern = re.compile(r"^(Led|Built|Designed|Developed|Implemented|Created|"
                              r"Managed|Achieved|Reduced|Improved|Increased|Delivered|"
                              r"Established|Launched|Migrated|Optimized|Streamlined|"
                              r"Coordinated|Architected|Automated|Deployed|Integrated|"
                              r"Resolved|Spearheaded|Mentored|Conducted|Analyzed|"
                              r"Collaborated|Maintained|Configured|Engineered|"
                              r"Refactored|Orchestrated|Transformed|Facilitated|"
                              r"Negotiated|Executed|Pioneered)\b", re.IGNORECASE)

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
        return True

    if total_matched > 4:
        ratio = min(past_count, present_count) / total_matched
        return ratio < 0.35

    return True


def validate_resume_annotations(
    annotations: list[SourceAnnotation],
    parsed_resume: ParsedResume,
    threshold: float = 0.85,
) -> tuple[list[SourceAnnotation], list[SourceAnnotation]]:
    """Validate that source annotations reference real resume bullets."""
    actual_bullets = parsed_resume.get_bullet_text_set()
    valid = []
    invalid = []

    for ann in annotations:
        match = find_best_match(
            ann.source_bullet, actual_bullets, threshold
        )
        if match is not None:
            ann.source_bullet = match
            valid.append(ann)
        else:
            invalid.append(ann)

    return valid, invalid


def resume_sanity_checks(state: dict) -> dict[str, bool]:
    """Resume-specific sanity checks for the evaluate node."""
    checks = {}
    output = state.get("tailored_output", "")

    # Verb tense consistency
    checks["consistent_tense"] = check_verb_tense_consistency(output)

    # Validate source annotations against baseline
    annotations = state.get("source_annotations", [])
    parsed_source = state.get("parsed_source")

    if annotations and parsed_source:
        valid, invalid = validate_resume_annotations(
            annotations, parsed_source
        )
        total = len(valid) + len(invalid)
        checks["annotations_valid"] = (
            len(invalid) == 0 if total > 0 else True
        )
        if invalid:
            logger.warning(
                f"{len(invalid)}/{total} source annotations reference "
                f"non-existent baseline bullets"
            )
    else:
        checks["annotations_valid"] = True

    return checks
