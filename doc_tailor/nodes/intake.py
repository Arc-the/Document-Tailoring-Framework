"""Intake node — validation, normalization, and source document parsing.

No LLM call needed. This is purely deterministic.
"""

from doc_tailor.plugin import get_plugin
from doc_tailor.state import TailoringState
from doc_tailor.utils.validation import clean_input_text


def intake_node(state: TailoringState) -> dict:
    """Validate inputs, clean text, and parse the source document."""
    plugin = get_plugin(state.get("doc_type", "resume"))

    # Validate required fields
    job_description = state.get("job_description", "")
    source_document = state.get("source_document", "")

    if not job_description.strip():
        raise ValueError("job_description is required and cannot be empty")
    if not source_document.strip():
        raise ValueError("source_document is required and cannot be empty")

    # Clean raw input text
    job_description = clean_input_text(job_description)
    source_document = clean_input_text(source_document)

    # Parse source document using plugin
    parsed = plugin.parse_source(source_document)

    # Set defaults
    constraints = state.get("constraints") or {}
    company_name = state.get("company_name", "")
    target_role = state.get("target_role", "")

    return {
        "job_description": job_description,
        "source_document": source_document,
        "parsed_source": parsed,
        "company_name": company_name.strip(),
        "target_role": target_role.strip(),
        "constraints": constraints,
        "research_context": {},
        "iteration_count": 0,
    }
