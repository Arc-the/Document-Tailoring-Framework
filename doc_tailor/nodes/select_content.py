"""Select Content node — decides editorial strategy before any rewriting.

Deterministic suppressions are delegated to the plugin.
The LLM-driven emphasis plan uses plugin prompts.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from doc_tailor.config import get_config
from doc_tailor.models import EmphasisPlan
from doc_tailor.plugin import get_plugin
from doc_tailor.state import TailoringState

logger = logging.getLogger(__name__)


def select_content_node(state: TailoringState) -> dict:
    """Decide suppressions and emphasis plan."""
    config = get_config()
    plugin = get_plugin(state.get("doc_type", "resume"))

    evidence_map = state["evidence_map"]
    parsed_source = state["parsed_source"]

    # Step 1: Plugin-driven deterministic suppressions
    suppressions = plugin.compute_suppressions(evidence_map, parsed_source, config)
    logger.info(f"Total suppressions: {len(suppressions)} items")

    # Step 2: LLM-driven emphasis plan
    evidence_map_json = json.dumps(
        [m.model_dump() for m in evidence_map], indent=2
    )
    constraints_json = json.dumps(state.get("constraints", {}), indent=2)
    research_json = json.dumps(state.get("research_context", {}), indent=2)

    llm = config.get_llm()
    structured_llm = llm.with_structured_output(EmphasisPlan)

    prompt_text = plugin.prompts.select_content_user.format(
        evidence_map_json=evidence_map_json,
        source_document=state["source_document"],
        constraints_json=constraints_json,
        research_context_json=research_json,
    )

    emphasis_plan: EmphasisPlan = structured_llm.invoke([
        SystemMessage(content=plugin.prompts.select_content_system),
        HumanMessage(content=prompt_text),
    ])

    return {
        "suppressions": suppressions,
        "emphasis_plan": emphasis_plan,
    }
