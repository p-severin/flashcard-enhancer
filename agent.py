import asyncio
import csv
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from custom_logger import log

load_dotenv()


class RawCard(BaseModel):
    """Original flashcard data from CSV"""

    front: str
    back: str
    deck_name: str


class AdditionalFields(BaseModel):
    """AI-generated additional fields for the flashcard"""

    example_sentence_front: str = Field(
        description="An example sentence using the word/phrase from 'front', in the front language"
    )
    example_sentence_back: str = Field(
        description="Translation of the example sentence in the back language"
    )


class EnhancedCard(BaseModel):
    """Complete flashcard with original and AI-generated fields"""

    front: str
    back: str
    deck_name: str
    example_sentence_front: str
    example_sentence_back: str


async def process_card(
    agent: Agent[None, AdditionalFields], raw_card: RawCard
) -> EnhancedCard:
    """
    Process a single card by generating additional fields using the AI agent.

    Args:
        agent: The Pydantic AI agent configured to generate AdditionalFields
        raw_card: The original card data from CSV

    Returns:
        EnhancedCard with both original and AI-generated fields
    """
    # Create a prompt for the agent
    prompt = f"""
    Create example sentences for this flashcard:

    Front (question): {raw_card.front}
    Back (answer): {raw_card.back}

    The front is in one language and the back is in another (Italian based on context).
    Generate a natural example sentence in the front language that uses the concept,
    and its translation in the back language.
    """

    # Run the agent to get additional fields
    result = await agent.run(prompt)
    additional_fields = result.output

    # Combine original and generated fields
    enhanced_card = EnhancedCard(
        front=raw_card.front,
        back=raw_card.back,
        deck_name=raw_card.deck_name,
        example_sentence_front=additional_fields.example_sentence_front,
        example_sentence_back=additional_fields.example_sentence_back,
    )

    return enhanced_card


async def process_csv_file(
    input_path: Path, output_path: Path, limit: int | None = None
):
    """
    Process an entire CSV file, generating additional fields for each card.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output CSV file
        limit: Optional limit on number of cards to process (useful for testing)
    """
    agent = Agent(
        model="openai:gpt-5",
        output_type=AdditionalFields,
        instructions=(
            "You are a language learning assistant. Generate natural, contextually "
            "appropriate example sentences for flashcard vocabulary and phrases."
        ),
    )

    # Read input CSV
    log.info(f"Reading cards from: {input_path}")
    cards_to_process = []

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_card = RawCard(
                front=row["Front"], back=row["Back"], deck_name=row["deck_name"]
            )
            cards_to_process.append(raw_card)

            if limit and len(cards_to_process) >= limit:
                break

    log.info(f"Processing {len(cards_to_process)} cards...")

    # Process each card
    enhanced_cards = []
    for i, raw_card in enumerate(cards_to_process, 1):
        log.info(f"Processing card {i}/{len(cards_to_process)}: {raw_card.front}")
        enhanced_card = await process_card(agent, raw_card)
        enhanced_cards.append(enhanced_card)
        log.info(f"  Generated example: {enhanced_card.example_sentence_front}")

    # Write output CSV
    log.info(f"Writing enhanced cards to: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        # Get field names from the EnhancedCard model
        fieldnames = list(EnhancedCard.model_fields.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        for card in enhanced_cards:
            writer.writerow(card.model_dump())

    log.info(f"Successfully processed {len(enhanced_cards)} cards!")


async def main():
    """Main entry point for the flashcard enhancer"""
    # Example: process a single file with a limit for testing
    input_files = Path("output/base").glob("*.csv")
    for file in input_files:
        log.info(f"Processing file: {file}")
        output_file = Path("output/enhanced") / file.name
        limit = None  # Set to None to process all cards
        await process_csv_file(file, output_file, limit=limit)


if __name__ == "__main__":
    asyncio.run(main())
