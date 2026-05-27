from dataclasses import dataclass
from pathlib import Path

from flashcard_enhancer.prompts import PROMPT_VERSION, PromptSettings


@dataclass(frozen=True)
class GenerationSettings:
    model: str = "openai:gpt-5-mini"
    source_language: str = "front language"
    target_language: str = "back language"
    level: str = "natural learner-appropriate"

    def prompt_settings(self) -> PromptSettings:
        return PromptSettings(
            source_language=self.source_language,
            target_language=self.target_language,
            level=self.level,
        )

    def metadata(self) -> dict[str, str]:
        return {
            "prompt_version": PROMPT_VERSION,
            "model": self.model,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "level": self.level,
        }


@dataclass(frozen=True)
class EnhancementOptions:
    limit: int | None = None
    dry_run: bool = False
    max_retries: int = 3
    metadata: dict[str, str] | None = None
    cache_path: Path | None = None
    resume: bool = True

    def effective_metadata(self) -> dict[str, str]:
        return dict(self.metadata or {})

