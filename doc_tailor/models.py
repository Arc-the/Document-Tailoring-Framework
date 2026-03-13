"""Generic domain models for the document tailoring pipeline.

These models define the structured artifacts that flow through the pipeline.
The evidence map is the central artifact — everything downstream depends on it.

Field naming uses generic terms (source_text, section_id) rather than
resume-specific ones (source_bullet, experience_id).
"""

from enum import Enum
from pydantic import BaseModel, Field


# --- Enums ---

class MatchStrength(str, Enum):
    STRONG = "strong"
    WEAK = "weak"
    NONE = "none"


class PriorityTier(str, Enum):
    MUST_HAVE = "must_have"
    STRONG_PREFERENCE = "strong_preference"
    NICE_TO_HAVE = "nice_to_have"


# --- Evidence Map (central artifact) ---

class EvidenceEntry(BaseModel):
    """Maps a source document segment to a target requirement."""
    source_text: str = Field(description="Exact text from the source document")
    section_id: str = Field(description="Which section/block it belongs to")
    match_strength: MatchStrength
    relevance_note: str = Field(description="Short justification for the mapping")


class RequirementMapping(BaseModel):
    """A single requirement and its evidence from the source document."""
    requirement: str
    priority: PriorityTier
    evidence: list[EvidenceEntry] = Field(default_factory=list)


class EvidenceMap(BaseModel):
    """The complete evidence map — spine of the pipeline."""
    mappings: list[RequirementMapping] = Field(default_factory=list)

    def requirements_by_priority(self, priority: PriorityTier) -> list[RequirementMapping]:
        return [m for m in self.mappings if m.priority == priority]

    def unmatched_requirements(self) -> list[RequirementMapping]:
        """Requirements with no strong evidence."""
        return [
            m for m in self.mappings
            if not any(e.match_strength == MatchStrength.STRONG for e in m.evidence)
        ]


# --- Content Selection ---

class SuppressionEntry(BaseModel):
    """A content segment being suppressed from the output."""
    source_text: str
    section_id: str
    reason: str


class EmphasisPlan(BaseModel):
    """Editorial strategy for the tailored document."""
    lead_section_ids: list[str] = Field(
        default_factory=list,
        description="Sections to position first",
    )
    items_to_expand: list[str] = Field(
        default_factory=list,
        description="Source text items to expand or reword",
    )
    summary_direction: str = Field(
        default="",
        description="Framing direction for the summary/objective",
    )
    keyword_themes: list[str] = Field(
        default_factory=list,
        description="Technical keyword themes to weave in",
    )
    research_references: list[str] = Field(
        default_factory=list,
        description="Company/industry terms worth referencing",
    )


# --- Evaluation ---

class EvaluationResult(BaseModel):
    """Result of the evaluation node."""
    passed: bool
    scores: dict[str, float] = Field(
        default_factory=dict,
        description="Rubric dimension → 0-10 score",
    )
    sanity_checks: dict[str, bool] = Field(
        default_factory=dict,
        description="Check name → pass/fail",
    )
    critique: str = Field(
        default="",
        description="Specific actionable feedback if failed",
    )
    failure_level: str = Field(
        default="",
        description="'surface' or 'evidence'",
    )
