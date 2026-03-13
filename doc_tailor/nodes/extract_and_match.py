"""Extract & Match node — the most critical node in the pipeline.

Reads the full target spec and source document, outputs a structured evidence map.
This is the spine of the entire pipeline.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from doc_tailor.config import get_config
from doc_tailor.models import (
    EvidenceEntry,
    MatchStrength,
    PriorityTier,
    RequirementMapping,
)
from doc_tailor.plugin import get_plugin
from doc_tailor.state import TailoringState
from doc_tailor.utils.validation import find_best_match

logger = logging.getLogger(__name__)


# --- Structured output models for the LLM ---

class LLMEvidenceEntry(BaseModel):
    source_text: str = Field(description="Exact text from the source document")
    section_id: str = Field(description="ID of the section/block")
    match_strength: MatchStrength
    relevance_note: str

class LLMRequirementMapping(BaseModel):
    requirement: str = Field(description="A specific requirement from the target spec")
    priority: PriorityTier
    evidence: list[LLMEvidenceEntry] = Field(default_factory=list)

class LLMEvidenceMap(BaseModel):
    """Complete evidence map output from the LLM."""
    mappings: list[LLMRequirementMapping] = Field(
        description="List of all requirements with their evidence mappings"
    )


def extract_and_match_node(state: TailoringState) -> dict:
    """Build the evidence map — the central artifact of the pipeline."""
    config = get_config()
    plugin = get_plugin(state.get("doc_type", "resume"))

    parsed_source = state["parsed_source"]
    actual_texts = plugin.get_matchable_text(parsed_source)

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

    prompt_text = plugin.prompts.extract_and_match_user.format(
        job_description=state["job_description"],
        source_document=state["source_document"],
        research_section=research_section,
    )

    raw_map: LLMEvidenceMap = structured_llm.invoke([
        SystemMessage(content=plugin.prompts.extract_and_match_system),
        HumanMessage(content=prompt_text),
    ])

    # --- Post-LLM validation: verify every source_text exists in the document ---
    validated_mappings: list[RequirementMapping] = []
    total_entries = 0
    rejected_count = 0

    for raw_mapping in raw_map.mappings:
        validated_evidence: list[EvidenceEntry] = []

        for raw_entry in raw_mapping.evidence:
            total_entries += 1
            matched_text = find_best_match(
                raw_entry.source_text,
                actual_texts,
                threshold=config.match_threshold,
            )

            if matched_text is not None:
                validated_evidence.append(EvidenceEntry(
                    source_text=matched_text,
                    section_id=raw_entry.section_id,
                    match_strength=raw_entry.match_strength,
                    relevance_note=raw_entry.relevance_note,
                ))
            else:
                rejected_count += 1
                logger.warning(
                    f"Rejected evidence entry — no matching text found: "
                    f"'{raw_entry.source_text[:80]}...'"
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
