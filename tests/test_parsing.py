"""Tests for resume parsing."""

import pytest
from resume_tailor.parsers.resume_parser import parse_resume


SAMPLE_RESUME = """Summary
Results-driven software engineer with 5 years of experience.

Experience

Acme Corp — Senior Software Engineer — Jan 2022 - Present
- Architected a microservices platform handling 10M+ daily requests
- Reduced API response times by 35% through query optimization
- Led migration from monolithic architecture to event-driven microservices

TechStart Inc — Software Engineer — Jun 2019 - Dec 2021
- Built real-time data processing pipeline using Apache Spark
- Developed RESTful APIs serving 50+ clients with 99.9% uptime

Education

State University — B.S. Computer Science — 2015-2019
- Relevant coursework: Distributed Systems, Database Design

Skills
Python, JavaScript, Go, SQL, FastAPI, Docker, Kubernetes, AWS
"""


class TestParseResume:
    def test_parses_summary(self):
        parsed = parse_resume(SAMPLE_RESUME)
        assert "software engineer" in parsed.summary.lower()

    def test_finds_experience_blocks(self):
        parsed = parse_resume(SAMPLE_RESUME)
        # Should find at least the two main experience entries
        exp_blocks = [b for b in parsed.experience_blocks if b.section == "experience"]
        assert len(exp_blocks) >= 2

    def test_parses_bullets(self):
        parsed = parse_resume(SAMPLE_RESUME)
        all_bullets = parsed.all_bullets()
        assert len(all_bullets) >= 5
        # Check a known bullet exists
        bullet_texts = [b.text for b in all_bullets]
        assert any("microservices" in b.lower() for b in bullet_texts)

    def test_parses_skills(self):
        parsed = parse_resume(SAMPLE_RESUME)
        assert "Python" in parsed.skills
        assert "Docker" in parsed.skills

    def test_experience_ids_are_unique(self):
        parsed = parse_resume(SAMPLE_RESUME)
        ids = [b.experience_id for b in parsed.experience_blocks]
        assert len(ids) == len(set(ids))

    def test_bullets_have_experience_ids(self):
        parsed = parse_resume(SAMPLE_RESUME)
        for bullet in parsed.all_bullets():
            assert bullet.experience_id, f"Bullet missing experience_id: {bullet.text}"

    def test_get_bullet_text_set(self):
        parsed = parse_resume(SAMPLE_RESUME)
        bullet_set = parsed.get_bullet_text_set()
        assert isinstance(bullet_set, set)
        assert len(bullet_set) > 0

    def test_empty_resume(self):
        parsed = parse_resume("")
        assert parsed.raw_text == ""
        assert len(parsed.experience_blocks) == 0

    def test_preserves_raw_text(self):
        parsed = parse_resume(SAMPLE_RESUME)
        assert parsed.raw_text == SAMPLE_RESUME


class TestParseResumeEdgeCases:
    def test_no_section_headers(self):
        text = """John Doe — Software Engineer — 2020 - Present
- Built APIs
- Managed databases"""
        parsed = parse_resume(text)
        assert len(parsed.all_bullets()) == 2

    def test_bullet_variants(self):
        text = """Experience

Company A — Engineer — 2020
• Built APIs using Python
* Managed cloud infrastructure
– Deployed microservices"""
        parsed = parse_resume(text)
        assert len(parsed.all_bullets()) == 3
