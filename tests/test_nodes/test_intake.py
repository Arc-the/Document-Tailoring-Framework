"""Tests for the intake node."""

import pytest
from doc_tailor.nodes.intake import intake_node


def test_intake_basic():
    state = {
        "doc_type": "resume",
        "job_description": "We need a Python developer",
        "source_document": "Experience\n\nAcme — Engineer — 2020\n- Built Python APIs",
        "company_name": "TestCo",
        "target_role": "Python Developer",
    }
    result = intake_node(state)
    assert result["parsed_source"] is not None
    assert result["iteration_count"] == 0
    assert result["research_context"] == {}
    assert result["company_name"] == "TestCo"


def test_intake_strips_whitespace():
    state = {
        "doc_type": "resume",
        "job_description": "  We need a developer  ",
        "source_document": "  Experience\n\nAcme — Dev — 2020\n- Built stuff  ",
    }
    result = intake_node(state)
    assert result["job_description"] == "We need a developer"
    assert not result["source_document"].startswith(" ")


def test_intake_missing_jd():
    with pytest.raises(ValueError, match="job_description"):
        intake_node({"doc_type": "resume", "job_description": "", "source_document": "some doc"})


def test_intake_missing_source():
    with pytest.raises(ValueError, match="source_document"):
        intake_node({"doc_type": "resume", "job_description": "some jd", "source_document": ""})


def test_intake_default_constraints():
    state = {
        "doc_type": "resume",
        "job_description": "Need developer",
        "source_document": "Experience\n\nAcme — Dev — 2020\n- Built stuff",
    }
    result = intake_node(state)
    assert result["constraints"] == {}
