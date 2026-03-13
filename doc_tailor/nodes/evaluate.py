"""Evaluate node — scores the tailored document and decides whether to loop back.

Combines deterministic sanity checks with LLM-based rubric scoring.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from doc_tailor.config import get_config
from doc_tailor.models import EvaluationResult
from doc_tailor.plugin import get_plugin
from doc_tailor.state import TailoringState
from doc_tailor.utils.validation import (
    check_duplicate_bullets,
    estimate_page_count,
)

logger = logging.getLogger(__name__)


# --- Structured output for LLM scoring ---

class LLMScores(BaseModel):
    relevance: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    conciseness: float = Field(ge=0, le=10)
    keyword_coverage: float = Field(ge=0, le=10)
    evidence_strength: float = Field(ge=0, le=10)
    readability: float = Field(ge=0, le=10)
    truthfulness: float = Field(ge=0, le=10)
    critique: str = Field(
        default="",
        description="Specific actionable feedback if any score is below 7",
    )


def _run_generic_checks(state: TailoringState) -> dict[str, bool]:
    """Run generic sanity checks on the tailored output."""
    output = state.get("tailored_output", "")
    constraints = state.get("constraints", {})

    checks = {}

    # Check 1: No duplicate items
    duplicates = check_duplicate_bullets(output)
    checks["no_duplicates"] = len(duplicates) == 0
    if duplicates:
        logger.warning(f"Found {len(duplicates)} near-duplicate item pairs")

    # Check 2: Page/length constraint
    max_pages = constraints.get("max_pages", 1)
    estimated_pages = estimate_page_count(output)
    checks["within_page_limit"] = estimated_pages <= max_pages

    # Check 3: Source annotations exist
    annotations = state.get("source_annotations", [])
    checks["has_annotations"] = len(annotations) > 0

    return checks


def evaluate_node(state: TailoringState) -> dict:
    """Score the output and determine if it passes or needs revision."""
    config = get_config()
    plugin = get_plugin(state.get("doc_type", "resume"))

    # Step 1: Generic sanity checks + plugin-specific checks
    sanity_checks = _run_generic_checks(state)
    plugin_checks = plugin.sanity_checks(state)
    sanity_checks.update(plugin_checks)

    all_sanity_passed = all(sanity_checks.values())
    logger.info(f"Sanity checks: {sanity_checks}")

    # Step 2: LLM-based rubric scoring
    evidence_map_json = json.dumps(
        [m.model_dump() for m in state.get("evidence_map", [])], indent=2
    )
    annotations_json = json.dumps(
        [a.model_dump() if hasattr(a, 'model_dump') else a
         for a in state.get("source_annotations", [])],
        indent=2,
    )
    constraints_json = json.dumps(state.get("constraints", {}), indent=2)

    llm = config.get_llm(temperature=0.1)
    structured_llm = llm.with_structured_output(LLMScores)

    prompt_text = plugin.prompts.evaluate_user.format(
        tailored_output=state.get("tailored_output", ""),
        annotations_json=annotations_json,
        evidence_map_json=evidence_map_json,
        source_document=state["source_document"],
        job_description=state["job_description"],
        constraints_json=constraints_json,
    )

    llm_scores: LLMScores = structured_llm.invoke([
        SystemMessage(content=plugin.prompts.evaluate_system),
        HumanMessage(content=prompt_text),
    ])

    scores = {
        "relevance": llm_scores.relevance,
        "clarity": llm_scores.clarity,
        "conciseness": llm_scores.conciseness,
        "keyword_coverage": llm_scores.keyword_coverage,
        "evidence_strength": llm_scores.evidence_strength,
        "readability": llm_scores.readability,
        "truthfulness": llm_scores.truthfulness,
    }

    # Step 3: Determine pass/fail
    min_score = config.min_passing_score
    all_scores_pass = all(s >= min_score for s in scores.values())
    passed = all_scores_pass and all_sanity_passed

    # Step 4: Determine failure level
    failure_level = ""
    critique = llm_scores.critique

    if not passed:
        evidence_scores = [scores["truthfulness"], scores["evidence_strength"]]
        if any(s < min_score for s in evidence_scores):
            failure_level = "evidence"
        else:
            failure_level = "surface"

        failed_checks = [k for k, v in sanity_checks.items() if not v]
        if failed_checks:
            sanity_feedback = f"\n\nSanity check failures: {', '.join(failed_checks)}"
            critique += sanity_feedback

    iteration = state.get("iteration_count", 0)
    logger.info(
        f"Evaluation (iteration {iteration}): "
        f"passed={passed}, scores={scores}, failure_level={failure_level}"
    )

    evaluation = EvaluationResult(
        passed=passed,
        scores=scores,
        sanity_checks=sanity_checks,
        critique=critique,
        failure_level=failure_level,
    )

    return {"evaluation": evaluation}
