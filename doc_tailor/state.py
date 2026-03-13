"""LangGraph state definition for the document tailoring pipeline."""

from typing import Any, TypedDict

from doc_tailor.models import (
    EmphasisPlan,
    EvaluationResult,
    RequirementMapping,
    SuppressionEntry,
)


class TailoringState(TypedDict, total=False):
    # --- Plugin metadata ---
    doc_type: str  # "resume", "cover_letter", etc.

    # --- Intake (step 1) ---
    job_description: str
    company_name: str
    target_role: str
    source_document: str  # was "baseline_resume"
    parsed_source: Any  # plugin-specific parsed model
    constraints: dict

    # --- Research (step 2) ---
    research_context: dict

    # --- Extract & Match (step 3) ---
    evidence_map: list[RequirementMapping]

    # --- Select Content (step 4) ---
    suppressions: list[SuppressionEntry]
    emphasis_plan: EmphasisPlan

    # --- Generate (step 5) ---
    tailored_output: str  # was "tailored_resume"
    source_annotations: list[Any]  # plugin-specific annotation model
    iteration_count: int

    # --- Evaluate (step 6) ---
    evaluation: EvaluationResult
