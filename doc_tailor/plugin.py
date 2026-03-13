"""Plugin system for document type extensibility.

Each document type (resume, cover letter, proposal, etc.) provides a plugin
that tells the generic pipeline how to parse, select content, generate, and evaluate.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from doc_tailor.models import RequirementMapping, SuppressionEntry


@dataclass
class DocumentPrompts:
    """All prompt templates needed by the pipeline for a given document type."""
    baseline_truth_rule: str
    formatting_rules: str
    tone_guidance: str

    extract_and_match_system: str
    extract_and_match_user: str  # template with {job_description}, {source_document}, {research_section}

    select_content_system: str
    select_content_user: str  # template with {evidence_map_json}, {source_document}, {constraints_json}, {research_context_json}

    generate_system: str
    generate_user: str  # template with {source_document}, {evidence_map_json}, {suppressions_json}, {emphasis_plan_json}, {constraints_json}
    generate_retry_user: str

    evaluate_system: str
    evaluate_user: str  # template with {tailored_output}, {annotations_json}, {evidence_map_json}, {source_document}, {job_description}, {constraints_json}


@dataclass
class DocumentTypePlugin:
    """Everything the generic pipeline needs from a specific document type."""
    name: str

    # Parsing: raw text → structured model
    parse_source: Callable[[str], BaseModel]

    # Returns all citable text segments from the parsed source
    get_matchable_text: Callable[[BaseModel], set[str]]

    # All prompt templates for this document type
    prompts: DocumentPrompts

    # Deterministic content selection (suppressions)
    compute_suppressions: Callable[
        [list[RequirementMapping], BaseModel, Any],  # evidence_map, parsed_source, config
        list[SuppressionEntry],
    ]

    # Parse LLM generation output into (tailored_text, annotations_list)
    parse_output: Callable[[str], tuple[str, list[BaseModel]]]

    # Plugin-specific sanity checks for evaluation
    sanity_checks: Callable[[dict], dict[str, bool]]

    # Default config values for this document type
    default_plugin_config: dict = field(default_factory=dict)


# --- Plugin Registry ---

_PLUGINS: dict[str, DocumentTypePlugin] = {}


def register_plugin(plugin: DocumentTypePlugin):
    """Register a document type plugin."""
    _PLUGINS[plugin.name] = plugin


def get_plugin(name: str) -> DocumentTypePlugin:
    """Look up a registered plugin by name."""
    if name not in _PLUGINS:
        available = ", ".join(_PLUGINS.keys()) or "(none)"
        raise ValueError(
            f"Unknown document type: '{name}'. Available: {available}"
        )
    return _PLUGINS[name]


def list_plugins() -> list[str]:
    """Return names of all registered plugins."""
    return list(_PLUGINS.keys())
