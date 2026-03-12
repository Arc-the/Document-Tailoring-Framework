"""Evaluate node — scores the tailored resume and decides whether to loop back.

Combines deterministic sanity checks with LLM-based rubric scoring.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from resume_tailor.config import get_config
from resume_tailor.models import EvaluationResult, SourceAnnotation
from resume_tailor.prompts.evaluate import EVALUATE_SYSTEM, EVALUATE_USER
from resume_tailor.state import ResumeState
from resume_tailor.utils.validation import (
    check_duplicate_bullets,
    check_verb_tense_consistency,
    estimate_page_count,
    validate_source_annotations,
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


def _run_sanity_checks(state: ResumeState) -> dict[str, bool]:
    """Run deterministic sanity checks on the tailored resume."""
    resume = state.get("tailored_resume", "")
    constraints = state.get("constraints", {})

    checks = {}

    # Check 1: No duplicate bullets
    duplicates = check_duplicate_bullets(resume)
    checks["no_duplicates"] = len(duplicates) == 0
    if duplicates:
        logger.warning(f"Found {len(duplicates)} near-duplicate bullet pairs")

    # Check 2: Consistent verb tense
    checks["consistent_tense"] = check_verb_tense_consistency(resume)

    # Check 3: Page/length constraint
    max_pages = constraints.get("max_pages", 1)
    estimated_pages = estimate_page_count(resume)
    checks["within_page_limit"] = estimated_pages <= max_pages

    # Check 4: Source annotations exist
    annotations = state.get("source_annotations", [])
    checks["has_annotations"] = len(annotations) > 0

    # Check 5: Validate source annotations against baseline
    if annotations and state.get("parsed_resume"):
        valid, invalid = validate_source_annotations(
            annotations, state["parsed_resume"]
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


def evaluate_node(state: ResumeState) -> dict:
    """Score the resume and determine if it passes or needs revision."""
    config = get_config()

    # Step 1: Deterministic sanity checks
    sanity_checks = _run_sanity_checks(state)
    all_sanity_passed = all(sanity_checks.values())
    logger.info(f"Sanity checks: {sanity_checks}")

    # Step 2: LLM-based rubric scoring
    evidence_map_json = json.dumps(
        [m.model_dump() for m in state.get("evidence_map", [])], indent=2
    )
    annotations_json = json.dumps(
        [a.model_dump() for a in state.get("source_annotations", [])], indent=2
    )
    constraints_json = json.dumps(state.get("constraints", {}), indent=2)

    llm = config.get_llm(temperature=0.1)
    structured_llm = llm.with_structured_output(LLMScores)

    prompt_text = EVALUATE_USER.format(
        tailored_resume=state.get("tailored_resume", ""),
        annotations_json=annotations_json,
        evidence_map_json=evidence_map_json,
        baseline_resume=state["baseline_resume"],
        job_description=state["job_description"],
        constraints_json=constraints_json,
    )

    llm_scores: LLMScores = structured_llm.invoke([
        SystemMessage(content=EVALUATE_SYSTEM),
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

        # Append sanity check failures to critique
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
