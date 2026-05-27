from pydantic_ai import Agent

from flashcard_enhancer.models import AdditionalFields, RawCard
from flashcard_enhancer.prompts import PromptSettings, build_example_prompt


class PydanticAiEnhancementProvider:
    def __init__(self, model: str, prompt_settings: PromptSettings) -> None:
        self.prompt_settings = prompt_settings
        self.agent = Agent(
            model=model,
            output_type=AdditionalFields,
            instructions=(
                "You are a language learning assistant. Generate natural, "
                "contextually appropriate example sentences for flashcards."
            ),
        )

    async def __call__(self, card: RawCard) -> AdditionalFields:
        prompt = build_example_prompt(card, self.prompt_settings)
        result = await self.agent.run(prompt)
        return result.output
