"""Domain models for the resume tailoring pipeline.

These Pydantic models define the structured artifacts that flow through the pipeline.
The evidence map models are the central artifact — everything downstream depends on them.
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


# --- Resume Structure ---

class ResumeBullet(BaseModel):
    """A single bullet point from the baseline resume."""
    text: str
    experience_id: str


class ExperienceBlock(BaseModel):
    """A parsed experience entry from the baseline resume."""
    experience_id: str
    company: str = ""
    title: str = ""
    dates: str = ""
    bullets: list[ResumeBullet] = Field(default_factory=list)
    section: str = "experience"  # experience, education, projects, etc.


class ParsedResume(BaseModel):
    """Structured representation of the baseline resume."""
    summary: str = ""
    experience_blocks: list[ExperienceBlock] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    raw_text: str = ""

    def all_bullets(self) -> list[ResumeBullet]:
        """Return all bullets across all experience blocks."""
        bullets = []
        for block in self.experience_blocks:
            bullets.extend(block.bullets)
        return bullets

    def get_bullet_text_set(self) -> set[str]:
        """Return set of all bullet texts for validation."""
        return {b.text for b in self.all_bullets()}

    def get_all_matchable_text(self) -> set[str]:
        """Return all text segments the LLM might cite as evidence.

        Includes bullets, summary, skills, experience headers, and
        education entries — anything the LLM sees in the raw resume
        and might quote back.
        """
        texts = self.get_bullet_text_set()

        # Summary text (may be multi-sentence)
        if self.summary:
            texts.add(self.summary)
            # Also add individual sentences from summary
            for sentence in self.summary.split(". "):
                s = sentence.strip().rstrip(".")
                if len(s) > 20:
                    texts.add(s)

        # Skills
        for skill in self.skills:
            if len(skill) > 10:
                texts.add(skill)

        # Experience headers (company + title + dates)
        for block in self.experience_blocks:
            header_parts = [block.company, block.title, block.dates]
            header = " ".join(p for p in header_parts if p)
            if header:
                texts.add(header)

        return texts


# --- Evidence Map (central artifact) ---

class EvidenceEntry(BaseModel):
    """Maps a resume bullet to a job requirement."""
    source_bullet: str = Field(description="Exact text from baseline resume")
    experience_id: str = Field(description="Which experience block it belongs to")
    match_strength: MatchStrength
    relevance_note: str = Field(description="Short justification for the mapping")


class RequirementMapping(BaseModel):
    """A single job requirement and its evidence from the resume."""
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
    """A bullet or experience being suppressed from the output."""
    source_bullet: str
    experience_id: str
    reason: str  # "no requirement match", "outdated tool", "duplicate evidence", etc.


class EmphasisPlan(BaseModel):
    """Editorial strategy for the tailored resume."""
    lead_experience_ids: list[str] = Field(
        default_factory=list,
        description="Experience blocks to position first",
    )
    bullets_to_expand: list[str] = Field(
        default_factory=list,
        description="Source bullet texts to expand or reword",
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


# --- Generation ---

class SourceAnnotation(BaseModel):
    """Links an output bullet to its source in the baseline resume."""
    output_bullet: str
    source_bullet: str
    experience_id: str = ""


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
