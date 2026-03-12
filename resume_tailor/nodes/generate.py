"""Generate node — produces the tailored resume.

Enforces baseline truth via source annotations. On retry, addresses
only the specific feedback from evaluation.
"""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from resume_tailor.config import get_config
from resume_tailor.models import SourceAnnotation
from resume_tailor.prompts.generate import (
    GENERATE_SYSTEM,
    GENERATE_USER,
    GENERATE_RETRY_USER,
)
from resume_tailor.state import ResumeState

logger = logging.getLogger(__name__)


def _parse_annotations(text: str) -> list[SourceAnnotation]:
    """Parse source annotations from the LLM output.

    Expected format after ---SOURCE ANNOTATIONS---:
    OUTPUT: [bullet text]
    SOURCE: [source bullet text]
    EXPERIENCE_ID: [id]
    """
    annotations = []
    # Find the annotations section
    marker = "---SOURCE ANNOTATIONS---"
    idx = text.find(marker)
    if idx == -1:
        # Try alternative markers
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
            # Save previous annotation if complete
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

    # Don't forget the last one
    if current_output and current_source:
        annotations.append(SourceAnnotation(
            output_bullet=current_output,
            source_bullet=current_source,
            experience_id=current_exp_id,
        ))

    return annotations


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


def generate_node(state: ResumeState) -> dict:
    """Generate the tailored resume with source annotations."""
    config = get_config()
    is_retry = state.get("iteration_count", 0) > 0
    evaluation = state.get("evaluation")

    evidence_map_json = json.dumps(
        [m.model_dump() for m in state["evidence_map"]], indent=2
    )
    suppressions_json = json.dumps(
        [s.model_dump() for s in state.get("suppressions", [])], indent=2
    )
    emphasis_plan = state.get("emphasis_plan")
    emphasis_plan_json = json.dumps(
        emphasis_plan.model_dump() if emphasis_plan else {}, indent=2
    )
    constraints_json = json.dumps(state.get("constraints", {}), indent=2)

    llm = config.get_llm(temperature=config.generation_temperature)

    if is_retry and evaluation:
        prompt_text = GENERATE_RETRY_USER.format(
            previous_resume=state.get("tailored_resume", ""),
            critique=evaluation.critique,
            baseline_resume=state["baseline_resume"],
            evidence_map_json=evidence_map_json,
            suppressions_json=suppressions_json,
            emphasis_plan_json=emphasis_plan_json,
            constraints_json=constraints_json,
        )
    else:
        prompt_text = GENERATE_USER.format(
            baseline_resume=state["baseline_resume"],
            evidence_map_json=evidence_map_json,
            suppressions_json=suppressions_json,
            emphasis_plan_json=emphasis_plan_json,
            constraints_json=constraints_json,
        )

    response = llm.invoke([
        SystemMessage(content=GENERATE_SYSTEM),
        HumanMessage(content=prompt_text),
    ])

    full_output = response.content

    # Parse out resume and annotations
    tailored_resume = _extract_resume(full_output)
    source_annotations = _parse_annotations(full_output)

    iteration = state.get("iteration_count", 0) + 1
    logger.info(
        f"Generation complete (iteration {iteration}), "
        f"{len(source_annotations)} annotations parsed"
    )

    return {
        "tailored_resume": tailored_resume,
        "source_annotations": source_annotations,
        "iteration_count": iteration,
    }
