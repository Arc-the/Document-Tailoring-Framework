"""Resume document type plugin."""

import logging

from pydantic import BaseModel

from doc_tailor.plugin import DocumentTypePlugin, register_plugin
from doc_tailor.plugins.resume.content import compute_resume_suppressions
from doc_tailor.plugins.resume.models import ParsedResume, SourceAnnotation
from doc_tailor.plugins.resume.parser import parse_resume
from doc_tailor.plugins.resume.prompts import build_resume_prompts
from doc_tailor.plugins.resume.validation import resume_sanity_checks

logger = logging.getLogger(__name__)


def _get_matchable_text(parsed_source: BaseModel) -> set[str]:
    """Return all citable text segments from a ParsedResume."""
    parsed: ParsedResume = parsed_source
    return parsed.get_all_matchable_text()


def _parse_resume_output(text: str) -> tuple[str, list[SourceAnnotation]]:
    """Parse LLM generation output into (tailored_resume, annotations)."""
    # Extract resume portion (before annotations)
    tailored = _extract_resume(text)
    annotations = _parse_annotations(text)
    return tailored, annotations


def _extract_resume(text: str) -> str:
    """Extract just the resume portion, before annotations."""
    markers = [
        "---SOURCE ANNOTATIONS---",
        "SOURCE ANNOTATIONS",
        "## Source Annotations",
        "## Annotations",
    ]
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            return text[:idx].strip()
    return text.strip()


def _parse_annotations(text: str) -> list[SourceAnnotation]:
    """Parse source annotations from the LLM output."""
    annotations = []
    marker = "---SOURCE ANNOTATIONS---"
    idx = text.find(marker)
    if idx == -1:
        for alt in ["SOURCE ANNOTATIONS", "## Source Annotations", "## Annotations"]:
            idx = text.find(alt)
            if idx != -1:
                break

    if idx == -1:
        logger.warning("No source annotations section found in generation output")
        return annotations

    annotation_text = text[idx:]
    lines = annotation_text.split("\n")

    current_output = None
    current_source = None
    current_exp_id = ""

    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("OUTPUT:"):
            if current_output and current_source:
                annotations.append(SourceAnnotation(
                    output_bullet=current_output,
                    source_bullet=current_source,
                    experience_id=current_exp_id,
                ))
            current_output = stripped[7:].strip()
            current_source = None
            current_exp_id = ""
        elif stripped.upper().startswith("SOURCE:"):
            current_source = stripped[7:].strip()
        elif stripped.upper().startswith("EXPERIENCE_ID:"):
            current_exp_id = stripped[14:].strip()

    if current_output and current_source:
        annotations.append(SourceAnnotation(
            output_bullet=current_output,
            source_bullet=current_source,
            experience_id=current_exp_id,
        ))

    return annotations


RESUME_DEFAULT_CONFIG = {
    "max_experiences": 4,
    "min_bullets_per_block": 2,
    "base_bullet_target": 2.5,
    "max_bullet_target": 5,
}


def register_resume_plugin():
    """Register the resume document type plugin."""
    plugin = DocumentTypePlugin(
        name="resume",
        parse_source=parse_resume,
        get_matchable_text=_get_matchable_text,
        prompts=build_resume_prompts(),
        compute_suppressions=compute_resume_suppressions,
        parse_output=_parse_resume_output,
        sanity_checks=resume_sanity_checks,
        default_plugin_config=RESUME_DEFAULT_CONFIG,
    )
    register_plugin(plugin)
