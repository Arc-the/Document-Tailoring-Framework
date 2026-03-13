"""Resume-specific domain models."""

from pydantic import BaseModel, Field


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
    section: str = "experience"


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
        """Return all text segments the LLM might cite as evidence."""
        texts = self.get_bullet_text_set()

        if self.summary:
            texts.add(self.summary)
            for sentence in self.summary.split(". "):
                s = sentence.strip().rstrip(".")
                if len(s) > 20:
                    texts.add(s)

        for skill in self.skills:
            if len(skill) > 10:
                texts.add(skill)

        for block in self.experience_blocks:
            header_parts = [block.company, block.title, block.dates]
            header = " ".join(p for p in header_parts if p)
            if header:
                texts.add(header)

        return texts


class SourceAnnotation(BaseModel):
    """Links an output bullet to its source in the baseline resume."""
    output_bullet: str
    source_bullet: str
    experience_id: str = ""
