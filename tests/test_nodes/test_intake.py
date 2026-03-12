"""Tests for the intake node."""

import pytest
from resume_tailor.nodes.intake import intake_node


def test_intake_basic():
    state = {
        "job_description": "We need a Python developer",
        "baseline_resume": "Experience\n\nAcme — Engineer — 2020\n- Built Python APIs",
        "company_name": "TestCo",
        "target_role": "Python Developer",
    }
    result = intake_node(state)
    assert result["parsed_resume"] is not None
    assert result["iteration_count"] == 0
    assert result["research_context"] == {}
    assert result["company_name"] == "TestCo"


def test_intake_strips_whitespace():
    state = {
        "job_description": "  We need a developer  ",
        "baseline_resume": "  Experience\n\nAcme — Dev — 2020\n- Built stuff  ",
    }
    result = intake_node(state)
    assert result["job_description"] == "We need a developer"
    assert not result["baseline_resume"].startswith(" ")


def test_intake_missing_jd():
    with pytest.raises(ValueError, match="job_description"):
        intake_node({"job_description": "", "baseline_resume": "some resume"})


def test_intake_missing_resume():
    with pytest.raises(ValueError, match="baseline_resume"):
        intake_node({"job_description": "some jd", "baseline_resume": ""})


def test_intake_default_constraints():
    state = {
        "job_description": "Need developer",
        "baseline_resume": "Experience\n\nAcme — Dev — 2020\n- Built stuff",
    }
    result = intake_node(state)
    assert result["constraints"] == {}
