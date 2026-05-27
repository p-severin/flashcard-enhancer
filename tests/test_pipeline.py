import asyncio
import csv
import tempfile
import unittest
from pathlib import Path

from flashcard_enhancer.pipeline import run_pipeline
from test_converter import write_apkg
from test_enhancer import FakeProvider


class PipelineTests(unittest.TestCase):
    def test_pipeline_converts_apkg_and_enhances_resulting_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            apkg_path = workspace / "deck.apkg"
            base_dir = workspace / "base"
            enhanced_dir = workspace / "enhanced"
            failed_dir = workspace / "failed"
            cache_dir = workspace / "cache"
            write_apkg(apkg_path)

            result = asyncio.run(
                run_pipeline(
                    apkg_path,
                    base_dir,
                    enhanced_dir,
                    failed_dir,
                    FakeProvider(),
                    cache_dir=cache_dir,
                    metadata={"prompt_version": "v1", "model": "test"},
                )
            )

            self.assertEqual(1, result.converted_files)
            self.assertEqual(1, result.succeeded)
            self.assertTrue((base_dir / "Italian.csv").exists())
            with (enhanced_dir / "Italian.csv").open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual("ciao", rows[0]["Front"])
            self.assertEqual("ciao example", rows[0]["example_sentence_front"])
            self.assertTrue((cache_dir / "Italian.json").exists())


if __name__ == "__main__":
    unittest.main()
