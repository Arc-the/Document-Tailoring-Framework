"""Tests for the evaluate node's deterministic components."""

import pytest
from resume_tailor.graph import route_after_eval
from resume_tailor.models import EvaluationResult


def _make_state(passed: bool, failure_level: str = "", iteration_count: int = 1):
    return {
        "evaluation": EvaluationResult(
            passed=passed,
            scores={"relevance": 8.0},
            critique="test",
            failure_level=failure_level,
        ),
        "iteration_count": iteration_count,
    }


class TestRouteAfterEval:
    def test_pass_routes_to_end(self):
        state = _make_state(passed=True)
        assert route_after_eval(state) == "pass"

    def test_max_retries_routes_to_fail(self):
        state = _make_state(passed=False, failure_level="surface", iteration_count=3)
        assert route_after_eval(state) == "fail"

    def test_evidence_failure_routes_to_retry_evidence(self):
        state = _make_state(passed=False, failure_level="evidence", iteration_count=1)
        assert route_after_eval(state) == "retry_evidence"

    def test_surface_failure_routes_to_retry_generation(self):
        state = _make_state(passed=False, failure_level="surface", iteration_count=1)
        assert route_after_eval(state) == "retry_generation"

    def test_max_retries_overrides_failure_level(self):
        state = _make_state(passed=False, failure_level="evidence", iteration_count=3)
        assert route_after_eval(state) == "fail"
