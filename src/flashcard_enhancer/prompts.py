from dataclasses import dataclass

from flashcard_enhancer.models import RawCard

PROMPT_VERSION = "example-sentences-v1"


@dataclass(frozen=True)
class PromptSettings:
    source_language: str = "front language"
    target_language: str = "back language"
    level: str = "natural learner-appropriate"


def build_example_prompt(card: RawCard, settings: PromptSettings) -> str:
    return f"""
    Prompt version: {PROMPT_VERSION}

    Create example sentences for this flashcard.

    Front: {card.front}
    Back: {card.back}
    Deck: {card.deck_name}

    Source language: {settings.source_language}
    Target language: {settings.target_language}
    Learner level: {settings.level}

    Generate a natural example sentence in the source language that uses the
    front field value, then provide its translation in the target language.
    """
