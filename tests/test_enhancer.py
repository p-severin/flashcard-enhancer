import asyncio
import csv
import tempfile
import unittest
from pathlib import Path

from flashcard_enhancer.enhancer import (
    AdditionalFields,
    EnhancementError,
    RawCard,
    enhance_csv,
)


def write_cards_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Front", "Back", "deck_name"])
        writer.writeheader()
        writer.writerows(rows)


class FakeProvider:
    def __init__(self, failures_before_success: dict[str, int] | None = None) -> None:
        self.calls: list[RawCard] = []
        self.failures_before_success = failures_before_success or {}

    async def __call__(self, card: RawCard) -> AdditionalFields:
        self.calls.append(card)
        remaining_failures = self.failures_before_success.get(card.front, 0)
        if remaining_failures:
            self.failures_before_success[card.front] = remaining_failures - 1
            raise RuntimeError(f"temporary failure for {card.front}")
        return AdditionalFields(
            example_sentence_front=f"{card.front} example",
            example_sentence_back=f"{card.back} example",
        )


class EnhanceCsvTests(unittest.TestCase):
    def test_writes_enhanced_csv_with_original_fields_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            output_path = workspace / "enhanced.csv"
            failed_path = workspace / "failed.csv"
            write_cards_csv(
                input_path,
                [{"Front": "ciao", "Back": "hello", "deck_name": "Italian"}],
            )
            provider = FakeProvider()

            result = asyncio.run(
                enhance_csv(input_path, output_path, failed_path, provider)
            )

            self.assertEqual(1, result.succeeded)
            self.assertEqual(0, result.failed)
            with output_path.open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(
                [
                    {
                        "Front": "ciao",
                        "Back": "hello",
                        "deck_name": "Italian",
                        "example_sentence_front": "ciao example",
                        "example_sentence_back": "hello example",
                    }
                ],
                rows,
            )
            self.assertFalse(failed_path.exists())

    def test_missing_required_columns_raise_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            with input_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["Front", "deck_name"])
                writer.writeheader()

            with self.assertRaisesRegex(EnhancementError, "Missing required columns"):
                asyncio.run(
                    enhance_csv(
                        input_path,
                        workspace / "enhanced.csv",
                        workspace / "failed.csv",
                        FakeProvider(),
                    )
                )

    def test_records_failed_card_without_losing_successful_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            output_path = workspace / "enhanced.csv"
            failed_path = workspace / "failed.csv"
            write_cards_csv(
                input_path,
                [
                    {"Front": "ciao", "Back": "hello", "deck_name": "Italian"},
                    {"Front": "fail", "Back": "break", "deck_name": "Italian"},
                ],
            )
            provider = FakeProvider({"fail": 10})

            result = asyncio.run(
                enhance_csv(
                    input_path,
                    output_path,
                    failed_path,
                    provider,
                    max_retries=1,
                )
            )

            self.assertEqual(1, result.succeeded)
            self.assertEqual(1, result.failed)
            with output_path.open(newline="", encoding="utf-8") as file:
                self.assertEqual("ciao", list(csv.DictReader(file))[0]["Front"])
            with failed_path.open(newline="", encoding="utf-8") as file:
                failed_rows = list(csv.DictReader(file))
            self.assertEqual("fail", failed_rows[0]["Front"])
            self.assertIn("temporary failure", failed_rows[0]["error"])

    def test_retries_per_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            write_cards_csv(
                input_path,
                [{"Front": "ciao", "Back": "hello", "deck_name": "Italian"}],
            )
            provider = FakeProvider({"ciao": 1})

            result = asyncio.run(
                enhance_csv(
                    input_path,
                    workspace / "enhanced.csv",
                    workspace / "failed.csv",
                    provider,
                    max_retries=2,
                )
            )

            self.assertEqual(1, result.succeeded)
            self.assertEqual(2, len(provider.calls))

    def test_limit_processes_only_first_n_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            write_cards_csv(
                input_path,
                [
                    {"Front": "one", "Back": "jeden", "deck_name": "Polish"},
                    {"Front": "two", "Back": "dwa", "deck_name": "Polish"},
                ],
            )
            provider = FakeProvider()

            result = asyncio.run(
                enhance_csv(
                    input_path,
                    workspace / "enhanced.csv",
                    workspace / "failed.csv",
                    provider,
                    limit=1,
                )
            )

            self.assertEqual(1, result.succeeded)
            self.assertEqual(["one"], [card.front for card in provider.calls])

    def test_dry_run_validates_input_without_calling_provider_or_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            output_path = workspace / "enhanced.csv"
            failed_path = workspace / "failed.csv"
            write_cards_csv(
                input_path,
                [{"Front": "ciao", "Back": "hello", "deck_name": "Italian"}],
            )
            provider = FakeProvider()

            result = asyncio.run(
                enhance_csv(
                    input_path,
                    output_path,
                    failed_path,
                    provider,
                    dry_run=True,
                )
            )

            self.assertEqual(1, result.planned)
            self.assertEqual([], provider.calls)
            self.assertFalse(output_path.exists())
            self.assertFalse(failed_path.exists())

    def test_writes_run_metadata_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            output_path = workspace / "enhanced.csv"
            write_cards_csv(
                input_path,
                [{"Front": "ciao", "Back": "hello", "deck_name": "Italian"}],
            )

            asyncio.run(
                enhance_csv(
                    input_path,
                    output_path,
                    workspace / "failed.csv",
                    FakeProvider(),
                    metadata={
                        "prompt_version": "example-v1",
                        "model": "test-model",
                        "source_language": "Italian",
                        "target_language": "English",
                        "level": "A1",
                    },
                )
            )

            with output_path.open(newline="", encoding="utf-8") as file:
                row = list(csv.DictReader(file))[0]
            self.assertEqual("example-v1", row["prompt_version"])
            self.assertEqual("test-model", row["model"])
            self.assertEqual("Italian", row["source_language"])
            self.assertEqual("English", row["target_language"])
            self.assertEqual("A1", row["level"])

    def test_resume_skips_cards_already_in_successful_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            output_path = workspace / "enhanced.csv"
            write_cards_csv(
                input_path,
                [
                    {"Front": "one", "Back": "jeden", "deck_name": "Polish"},
                    {"Front": "two", "Back": "dwa", "deck_name": "Polish"},
                ],
            )
            with output_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=[
                    "Front",
                    "Back",
                    "deck_name",
                    "example_sentence_front",
                    "example_sentence_back",
                ])
                writer.writeheader()
                writer.writerow(
                    {
                        "Front": "one",
                        "Back": "jeden",
                        "deck_name": "Polish",
                        "example_sentence_front": "existing",
                        "example_sentence_back": "existing",
                    }
                )
            provider = FakeProvider()

            result = asyncio.run(
                enhance_csv(input_path, output_path, workspace / "failed.csv", provider)
            )

            self.assertEqual(["two"], [card.front for card in provider.calls])
            self.assertEqual(1, result.succeeded)
            with output_path.open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(["one", "two"], [row["Front"] for row in rows])

    def test_cache_avoids_provider_call_on_repeated_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            cache_path = workspace / "cache.json"
            write_cards_csv(
                input_path,
                [{"Front": "ciao", "Back": "hello", "deck_name": "Italian"}],
            )

            asyncio.run(
                enhance_csv(
                    input_path,
                    workspace / "first.csv",
                    workspace / "failed.csv",
                    FakeProvider(),
                    cache_path=cache_path,
                    metadata={"prompt_version": "v1", "model": "test"},
                )
            )
            second_provider = FakeProvider()
            asyncio.run(
                enhance_csv(
                    input_path,
                    workspace / "second.csv",
                    workspace / "failed.csv",
                    second_provider,
                    cache_path=cache_path,
                    metadata={"prompt_version": "v1", "model": "test"},
                )
            )

            self.assertEqual([], second_provider.calls)

    def test_changed_metadata_invalidates_cache_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            cache_path = workspace / "cache.json"
            write_cards_csv(
                input_path,
                [{"Front": "ciao", "Back": "hello", "deck_name": "Italian"}],
            )

            asyncio.run(
                enhance_csv(
                    input_path,
                    workspace / "first.csv",
                    workspace / "failed.csv",
                    FakeProvider(),
                    cache_path=cache_path,
                    metadata={"prompt_version": "v1", "model": "test"},
                )
            )
            second_provider = FakeProvider()
            asyncio.run(
                enhance_csv(
                    input_path,
                    workspace / "second.csv",
                    workspace / "failed.csv",
                    second_provider,
                    cache_path=cache_path,
                    metadata={"prompt_version": "v2", "model": "test"},
                )
            )

            self.assertEqual(["ciao"], [card.front for card in second_provider.calls])


if __name__ == "__main__":
    unittest.main()
