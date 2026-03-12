"""Extract & Match node — the most critical node in the pipeline.

Reads the full JD and resume together, outputs a structured evidence map.
This is the spine of the entire pipeline. Invest the most prompt engineering here.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from resume_tailor.config import get_config
from resume_tailor.models import (
    EvidenceEntry,
    EvidenceMap,
    MatchStrength,
    PriorityTier,
    RequirementMapping,
)
from resume_tailor.prompts.extract_and_match import (
    EXTRACT_AND_MATCH_SYSTEM,
    EXTRACT_AND_MATCH_USER,
)
from resume_tailor.state import ResumeState
from resume_tailor.utils.validation import find_best_bullet_match

logger = logging.getLogger(__name__)


# --- Structured output models for the LLM ---

class LLMEvidenceEntry(BaseModel):
    source_bullet: str = Field(description="Exact text of a bullet from the resume")
    experience_id: str = Field(description="ID of the experience block")
    match_strength: MatchStrength
    relevance_note: str

class LLMRequirementMapping(BaseModel):
    requirement: str = Field(description="A specific requirement from the job description")
    priority: PriorityTier
    evidence: list[LLMEvidenceEntry] = Field(default_factory=list)

class LLMEvidenceMap(BaseModel):
    """Complete evidence map output from the LLM."""
    mappings: list[LLMRequirementMapping] = Field(
        description="List of all requirements with their evidence mappings"
    )


def extract_and_match_node(state: ResumeState) -> dict:
    """Build the evidence map — the central artifact of the pipeline."""
    config = get_config()
    parsed_resume = state["parsed_resume"]
    actual_bullets = parsed_resume.get_all_matchable_text()

    # Build research section for prompt
    research_context = state.get("research_context", {})
    if research_context:
        relevant = research_context.get("resume_relevant", [])
        supplementary = research_context.get("supplementary", [])
        research_items = relevant + supplementary
        research_section = "## Research Context\n" + "\n".join(
            f"- {item}" for item in research_items[:10]
        )
    else:
        research_section = "## Research Context\nNo additional research available."

    # Call LLM with structured output
    llm = config.get_llm()
    structured_llm = llm.with_structured_output(LLMEvidenceMap)

    prompt_text = EXTRACT_AND_MATCH_USER.format(
        job_description=state["job_description"],
        baseline_resume=state["baseline_resume"],
        research_section=research_section,
    )

    raw_map: LLMEvidenceMap = structured_llm.invoke([
        SystemMessage(content=EXTRACT_AND_MATCH_SYSTEM),
        HumanMessage(content=prompt_text),
    ])

    # --- Post-LLM validation: verify every source_bullet exists in the resume ---
    validated_mappings: list[RequirementMapping] = []
    total_entries = 0
    rejected_count = 0

    for raw_mapping in raw_map.mappings:
        validated_evidence: list[EvidenceEntry] = []

        for raw_entry in raw_mapping.evidence:
            total_entries += 1
            matched_bullet = find_best_bullet_match(
                raw_entry.source_bullet,
                actual_bullets,
                threshold=config.bullet_match_threshold,
            )

            if matched_bullet is not None:
                validated_evidence.append(EvidenceEntry(
                    source_bullet=matched_bullet,  # use exact text from resume
                    experience_id=raw_entry.experience_id,
                    match_strength=raw_entry.match_strength,
                    relevance_note=raw_entry.relevance_note,
                ))
            else:
                rejected_count += 1
                logger.warning(
                    f"Rejected evidence entry — no matching bullet found: "
                    f"'{raw_entry.source_bullet[:80]}...'"
                )

        validated_mappings.append(RequirementMapping(
            requirement=raw_mapping.requirement,
            priority=raw_mapping.priority,
            evidence=validated_evidence,
        ))

    if total_entries > 0:
        logger.info(
            f"Evidence map validation: {total_entries - rejected_count}/{total_entries} "
            f"entries validated ({rejected_count} rejected)"
        )

    return {
        "evidence_map": validated_mappings,
    }
