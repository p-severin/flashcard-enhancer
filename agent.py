import asyncio
import csv
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from custom_logger import log

load_dotenv()

# Configuration for parallel processing
BATCH_SIZE = 10  # Process 10 cards concurrently (adjust based on API rate limits)
MAX_RETRIES = 3  # Number of retries for failed requests


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
    agent: Agent[None, AdditionalFields], raw_card: RawCard, retry_count: int = 0
) -> EnhancedCard:
    """
    Process a single card by generating additional fields using the AI agent.

    Args:
        agent: The Pydantic AI agent configured to generate AdditionalFields
        raw_card: The original card data from CSV
        retry_count: Current retry attempt (for error handling)

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

    try:
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
    except Exception as e:
        if retry_count < MAX_RETRIES:
            log.warning(
                f"Error processing card '{raw_card.front}' (attempt {retry_count + 1}/{MAX_RETRIES}): {e}"
            )
            await asyncio.sleep(2**retry_count)  # Exponential backoff
            return await process_card(agent, raw_card, retry_count + 1)
        else:
            log.error(
                f"Failed to process card '{raw_card.front}' after {MAX_RETRIES} attempts: {e}"
            )
            raise


async def process_batch(
    agent: Agent[None, AdditionalFields], cards: list[RawCard]
) -> list[EnhancedCard]:
    """
    Process a batch of cards concurrently.

    Args:
        agent: The Pydantic AI agent
        cards: List of cards to process

    Returns:
        List of enhanced cards
    """
    tasks = [process_card(agent, card) for card in cards]
    return await asyncio.gather(*tasks)


async def process_csv_file(
    input_path: Path,
    output_path: Path,
    limit: int | None = None,
    batch_size: int = BATCH_SIZE,
):
    """
    Process an entire CSV file, generating additional fields for each card.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output CSV file
        limit: Optional limit on number of cards to process (useful for testing)
        batch_size: Number of cards to process concurrently in each batch
    """
    agent = Agent(
        model="openai:gpt-5-mini",
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

    log.info(f"Processing {len(cards_to_process)} cards in batches of {batch_size}...")

    # Process cards in batches
    enhanced_cards = []
    for i in range(0, len(cards_to_process), batch_size):
        batch = cards_to_process[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(cards_to_process) + batch_size - 1) // batch_size

        log.info(
            f"Processing batch {batch_num}/{total_batches} "
            f"({len(batch)} cards: {batch[0].front}...)"
        )

        try:
            batch_results = await process_batch(agent, batch)
            enhanced_cards.extend(batch_results)
            log.info(
                f"  Completed batch {batch_num}/{total_batches} "
                f"({len(enhanced_cards)}/{len(cards_to_process)} total)"
            )
        except Exception as e:
            log.error(f"Error processing batch {batch_num}: {e}")
            # Continue with next batch instead of failing completely
            continue

    # Write output CSV
    log.info(f"Writing {len(enhanced_cards)} enhanced cards to: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        # Get field names from the EnhancedCard model
        fieldnames = list(EnhancedCard.model_fields.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        for card in enhanced_cards:
            writer.writerow(card.model_dump())

    log.info(
        f"Successfully processed {len(enhanced_cards)}/{len(cards_to_process)} cards!"
    )


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
