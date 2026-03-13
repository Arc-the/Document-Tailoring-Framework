"""Runtime configuration for the document tailoring pipeline."""

from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel


@dataclass
class PipelineConfig:
    # LLM settings
    provider: str = "openai"  # "openai" or "gemini"
    model_name: str = "gpt-4o"
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
        """Create an LLM instance based on the configured provider."""
        temp = temperature if temperature is not None else self.temperature

        if self.provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=temp,
            )

        # Default: OpenAI
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=self.model_name,
            temperature=temp,
        )


# Module-level default config, overridable before pipeline runs
_config = PipelineConfig()


def get_config() -> PipelineConfig:
    return _config


def set_config(config: PipelineConfig):
    global _config
    _config = config
