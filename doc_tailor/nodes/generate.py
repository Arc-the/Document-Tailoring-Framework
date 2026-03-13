"""Generate node — produces the tailored document.

Enforces baseline truth via source annotations. On retry, addresses
only the specific feedback from evaluation.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from doc_tailor.config import get_config
from doc_tailor.plugin import get_plugin
from doc_tailor.state import TailoringState

logger = logging.getLogger(__name__)


def generate_node(state: TailoringState) -> dict:
    """Generate the tailored document with source annotations."""
    config = get_config()
    plugin = get_plugin(state.get("doc_type", "resume"))

    is_retry = state.get("iteration_count", 0) > 0
    evaluation = state.get("evaluation")

    evidence_map_json = json.dumps(
        [m.model_dump() for m in state["evidence_map"]], indent=2
    )
    suppressions_json = json.dumps(
        [s.model_dump() for s in state.get("suppressions", [])], indent=2
    )
    emphasis_plan = state.get("emphasis_plan")
    emphasis_plan_json = json.dumps(
        emphasis_plan.model_dump() if emphasis_plan else {}, indent=2
    )
    constraints_json = json.dumps(state.get("constraints", {}), indent=2)

    llm = config.get_llm(temperature=config.generation_temperature)

    if is_retry and evaluation:
        prompt_text = plugin.prompts.generate_retry_user.format(
            previous_output=state.get("tailored_output", ""),
            critique=evaluation.critique,
            source_document=state["source_document"],
            evidence_map_json=evidence_map_json,
            suppressions_json=suppressions_json,
            emphasis_plan_json=emphasis_plan_json,
            constraints_json=constraints_json,
        )
    else:
        prompt_text = plugin.prompts.generate_user.format(
            source_document=state["source_document"],
            evidence_map_json=evidence_map_json,
            suppressions_json=suppressions_json,
            emphasis_plan_json=emphasis_plan_json,
            constraints_json=constraints_json,
        )

    response = llm.invoke([
        SystemMessage(content=plugin.prompts.generate_system),
        HumanMessage(content=prompt_text),
    ])

    full_output = response.content

    # Parse output using plugin
    tailored_output, source_annotations = plugin.parse_output(full_output)

    iteration = state.get("iteration_count", 0) + 1
    logger.info(
        f"Generation complete (iteration {iteration}), "
        f"{len(source_annotations)} annotations parsed"
    )

    return {
        "tailored_output": tailored_output,
        "source_annotations": source_annotations,
        "iteration_count": iteration,
    }
