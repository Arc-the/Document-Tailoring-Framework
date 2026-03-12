"""Tests for deterministic validation utilities."""

import pytest
from resume_tailor.utils.validation import (
    normalize_text,
    fuzzy_match_score,
    find_best_bullet_match,
    check_duplicate_bullets,
    check_verb_tense_consistency,
    estimate_page_count,
)


class TestNormalizeText:
    def test_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self):
        assert normalize_text("hello   world") == "hello world"

    def test_normalizes_smart_quotes(self):
        assert normalize_text("\u201chello\u201d") == '"hello"'
        assert normalize_text("\u2018hello\u2019") == "'hello'"

    def test_normalizes_dashes(self):
        assert normalize_text("2020\u20132023") == "2020-2023"
        assert normalize_text("foo\u2014bar") == "foo-bar"


class TestFuzzyMatchScore:
    def test_identical_strings(self):
        assert fuzzy_match_score("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert fuzzy_match_score("abc", "xyz") < 0.5

    def test_similar_strings(self):
        score = fuzzy_match_score(
            "Reduced API response times by 35%",
            "Reduced API response times by 35% through optimization",
        )
        assert score > 0.7


class TestFindBestBulletMatch:
    def test_exact_match(self):
        bullets = {"Built a REST API", "Managed a team of 5"}
        result = find_best_bullet_match("Built a REST API", bullets)
        assert result == "Built a REST API"

    def test_exact_match_after_normalization(self):
        bullets = {"Built a REST API"}
        result = find_best_bullet_match("Built  a  REST  API", bullets)
        assert result == "Built a REST API"

    def test_fuzzy_match_above_threshold(self):
        bullets = {"Reduced API response times by 35% through query optimization and Redis caching"}
        result = find_best_bullet_match(
            "Reduced API response times by 35% through query optimization and Redis caching layer",
            bullets,
            threshold=0.85,
        )
        assert result is not None

    def test_no_match_below_threshold(self):
        bullets = {"Built a machine learning model"}
        result = find_best_bullet_match(
            "Managed a large distributed database",
            bullets,
            threshold=0.85,
        )
        assert result is None

    def test_empty_bullets(self):
        result = find_best_bullet_match("anything", set())
        assert result is None


class TestCheckDuplicateBullets:
    def test_no_duplicates(self):
        text = """- Built a REST API using FastAPI
- Reduced deployment time by 50%
- Mentored 3 junior engineers"""
        assert check_duplicate_bullets(text) == []

    def test_detects_duplicates(self):
        text = """- Built a REST API using FastAPI and Python
- Constructed a REST API with FastAPI and Python
- Reduced deployment time by 50%"""
        duplicates = check_duplicate_bullets(text)
        assert len(duplicates) > 0

    def test_ignores_short_bullets(self):
        text = """- Led team
- Led team
- Built a comprehensive data pipeline"""
        # Short bullets (< 20 chars) are ignored
        duplicates = check_duplicate_bullets(text)
        assert len(duplicates) == 0


class TestCheckVerbTenseConsistency:
    def test_consistent_past_tense(self):
        text = """- Built a REST API
- Reduced response times
- Implemented CI/CD pipeline
- Mentored junior engineers
- Designed database schemas"""
        assert check_verb_tense_consistency(text) is True

    def test_consistent_present_tense(self):
        text = """- Build REST APIs
- Reduce response times
- Implement CI/CD pipelines
- Mentor junior engineers
- Design database schemas"""
        assert check_verb_tense_consistency(text) is True

    def test_empty_text(self):
        assert check_verb_tense_consistency("") is True


class TestEstimatePageCount:
    def test_short_resume(self):
        text = "x" * 2000
        assert estimate_page_count(text) == 1

    def test_two_page_resume(self):
        text = "x" * 5000
        assert estimate_page_count(text) == 2

    def test_empty(self):
        assert estimate_page_count("") == 1
