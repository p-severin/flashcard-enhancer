import tempfile
import unittest
from pathlib import Path

from flashcard_enhancer.cli import main
from test_converter import write_apkg


class CliTests(unittest.TestCase):
    def test_convert_command_returns_success_for_valid_apkg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            apkg_path = workspace / "deck.apkg"
            out_dir = workspace / "csv"
            write_apkg(apkg_path)

            exit_code = main(["convert", str(apkg_path), "--out-dir", str(out_dir)])

            self.assertEqual(0, exit_code)
            self.assertTrue((out_dir / "Italian.csv").exists())

    def test_convert_command_returns_failure_for_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exit_code = main(
                ["convert", str(Path(tmp) / "missing.apkg"), "--out-dir", str(Path(tmp) / "csv")]
            )

            self.assertEqual(1, exit_code)

    def test_enhance_command_can_validate_input_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            input_path.write_text("Front,Back,deck_name\nciao,hello,Italian\n")

            exit_code = main(
                [
                    "enhance",
                    str(input_path),
                    "--output",
                    str(workspace / "enhanced.csv"),
                    "--failed-output",
                    str(workspace / "failed.csv"),
                    "--source-language",
                    "Italian",
                    "--target-language",
                    "English",
                    "--level",
                    "A1",
                    "--dry-run",
                ]
            )

            self.assertEqual(0, exit_code)

    def test_enhance_command_returns_failure_for_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_path = workspace / "cards.csv"
            input_path.write_text("Front,deck_name\nciao,Italian\n")

            exit_code = main(
                [
                    "enhance",
                    str(input_path),
                    "--output",
                    str(workspace / "enhanced.csv"),
                    "--failed-output",
                    str(workspace / "failed.csv"),
                    "--dry-run",
                ]
            )

            self.assertEqual(1, exit_code)

    def test_pipeline_command_can_convert_and_validate_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            apkg_path = workspace / "deck.apkg"
            write_apkg(apkg_path)

            exit_code = main(
                [
                    "pipeline",
                    str(apkg_path),
                    "--base-dir",
                    str(workspace / "base"),
                    "--enhanced-dir",
                    str(workspace / "enhanced"),
                    "--failed-dir",
                    str(workspace / "failed"),
                    "--dry-run",
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertTrue((workspace / "base" / "Italian.csv").exists())
            self.assertFalse((workspace / "enhanced" / "Italian.csv").exists())


if __name__ == "__main__":
    unittest.main()
