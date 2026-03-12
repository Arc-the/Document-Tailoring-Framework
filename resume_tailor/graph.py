"""Graph wiring and compilation for the resume tailoring pipeline.

intake → research → extract_and_match → select_content → generate → evaluate
                            ↑                                         |
                            |_____ evidence failure __________________|
                                                                      |
                            generate ←── surface failure ─────────────┘
                                                                      |
                            END ←── pass or max retries ──────────────┘
"""

from langgraph.graph import StateGraph, END

from resume_tailor.config import PipelineConfig
from resume_tailor.nodes import (
    evaluate_node,
    extract_and_match_node,
    generate_node,
    intake_node,
    research_node,
    select_content_node,
)
from resume_tailor.state import ResumeState


def route_after_eval(state: ResumeState) -> str:
    """Conditional routing after evaluation.

    - pass: all scores meet threshold → END
    - retry_evidence: truthfulness/evidence failure → back to extract_and_match
    - retry_generation: surface issues → back to generate
    - fail: max retries reached → END with best attempt
    """
    config = PipelineConfig()
    ev = state["evaluation"]

    if ev.passed:
        return "pass"

    if state.get("iteration_count", 0) >= config.max_iterations:
        return "fail"

    if ev.failure_level == "evidence":
        return "retry_evidence"

    return "retry_generation"


def build_graph() -> StateGraph:
    """Build and compile the resume tailoring graph."""
    graph = StateGraph(ResumeState)

    # Add nodes
    graph.add_node("intake", intake_node)
    graph.add_node("research", research_node)
    graph.add_node("extract_and_match", extract_and_match_node)
    graph.add_node("select_content", select_content_node)
    graph.add_node("generate", generate_node)
    graph.add_node("evaluate", evaluate_node)

    # Linear edges
    graph.set_entry_point("intake")
    graph.add_edge("intake", "research")
    graph.add_edge("research", "extract_and_match")
    graph.add_edge("extract_and_match", "select_content")
    graph.add_edge("select_content", "generate")
    graph.add_edge("generate", "evaluate")

    # Conditional loopback from evaluate
    graph.add_conditional_edges("evaluate", route_after_eval, {
        "pass": END,
        "retry_generation": "generate",
        "retry_evidence": "extract_and_match",
        "fail": END,
    })

    return graph.compile()
