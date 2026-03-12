"""LangGraph state definition for the resume tailoring pipeline."""

from typing import Annotated, TypedDict

from resume_tailor.models import (
    EmphasisPlan,
    EvaluationResult,
    ParsedResume,
    RequirementMapping,
    SourceAnnotation,
    SuppressionEntry,
)


class ResumeState(TypedDict, total=False):
    # --- Intake (step 1) ---
    job_description: str
    company_name: str
    target_role: str
    baseline_resume: str
    parsed_resume: ParsedResume
    constraints: dict  # e.g. {"max_pages": 1, "tone": "conservative"}

    # --- Research (step 2) ---
    research_context: dict  # keyed by category: resume_relevant, supplementary, etc.

    # --- Extract & Match (step 3) ---
    evidence_map: list[RequirementMapping]

    # --- Select Content (step 4) ---
    suppressions: list[SuppressionEntry]
    emphasis_plan: EmphasisPlan

    # --- Generate (step 5) ---
    tailored_resume: str
    source_annotations: list[SourceAnnotation]
    iteration_count: int

    # --- Evaluate (step 6) ---
    evaluation: EvaluationResult
