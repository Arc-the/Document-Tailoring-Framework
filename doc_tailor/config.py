"""Runtime configuration for the document tailoring pipeline."""

import os
from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel


@dataclass
class PipelineConfig:
    # LLM settings — all models routed via OpenRouter (OpenAI-compatible gateway)
    model_name: str = "google/gemma-4-31b-it"
    temperature: float = 0.2
    generation_temperature: float = 0.4

    # Evaluation thresholds
    min_passing_score: float = 7.0
    max_iterations: int = 3

    # Validation settings
    match_threshold: float = 0.85  # SequenceMatcher ratio for fuzzy matching

    # Research settings
    enable_research: bool = False
    max_search_results: int = 5

    # Constraints defaults
    default_constraints: dict = field(default_factory=dict)

    # Plugin-specific config (merged from plugin defaults + user overrides)
    plugin_config: dict = field(default_factory=dict)

    def get_llm(self, temperature: float | None = None) -> BaseChatModel:
        """Create an LLM instance routed through OpenRouter."""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model_name,
            temperature=temperature if temperature is not None else self.temperature,
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "https://github.com/doc-tailor",
                "X-Title": "doc-tailor",
            },
        )


# Module-level default config, overridable before pipeline runs
_config = PipelineConfig()


def get_config() -> PipelineConfig:
    return _config


def set_config(config: PipelineConfig):
    global _config
    _config = config
