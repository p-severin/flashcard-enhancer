import csv
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from flashcard_enhancer.converter import ConversionError, convert_apkg_to_csv


def write_minimal_collection(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE col (decks TEXT, models TEXT)")
        conn.execute(
            "CREATE TABLE notes (id INTEGER, flds TEXT, tags TEXT, mid INTEGER)"
        )
        conn.execute(
            """
            CREATE TABLE cards (
                id INTEGER,
                nid INTEGER,
                ord INTEGER,
                type INTEGER,
                queue INTEGER,
                due INTEGER,
                ivl INTEGER,
                factor INTEGER,
                reps INTEGER,
                lapses INTEGER,
                did INTEGER
            )
            """
        )
        decks = {"1": {"name": "Languages::Italian"}}
        models = {
            "10": {
                "name": "Basic",
                "flds": [{"name": "Front"}, {"name": "Back"}],
            }
        }
        conn.execute("INSERT INTO col VALUES (?, ?)", (json.dumps(decks), json.dumps(models)))
        conn.execute(
            "INSERT INTO notes VALUES (?, ?, ?, ?)",
            (100, "<b>ciao</b>\x1fhello", "", 10),
        )
        conn.execute(
            "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (200, 100, 0, 0, 0, 0, 0, 0, 0, 0, 1),
        )
        conn.commit()
    finally:
        conn.close()


def write_apkg(apkg_path: Path, collection_name: str = "collection.anki2") -> None:
    with tempfile.TemporaryDirectory() as tmp:
        collection_path = Path(tmp) / collection_name
        write_minimal_collection(collection_path)
        with zipfile.ZipFile(apkg_path, "w") as archive:
            archive.write(collection_path, collection_name)


class ConvertApkgToCsvTests(unittest.TestCase):
    def test_converts_apkg_to_deck_csv_and_creates_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            apkg_path = workspace / "deck.apkg"
            out_dir = workspace / "missing" / "csv"
            write_apkg(apkg_path)

            output_paths = convert_apkg_to_csv(apkg_path, out_dir)

            self.assertEqual([out_dir / "Italian.csv"], output_paths)
            self.assertTrue(out_dir.is_dir())
            with output_paths[0].open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(
                [
                    {
                        "Front": "ciao",
                        "Back": "hello",
                        "deck_name": "Languages::Italian",
                    }
                ],
                rows,
            )

    def test_rejects_archive_without_collection_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            apkg_path = Path(tmp) / "empty.apkg"
            with zipfile.ZipFile(apkg_path, "w") as archive:
                archive.writestr("notes.txt", "not an Anki database")

            with self.assertRaisesRegex(ConversionError, "collection database"):
                convert_apkg_to_csv(apkg_path, Path(tmp) / "out")

    def test_rejects_archive_paths_that_escape_extraction_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            apkg_path = Path(tmp) / "unsafe.apkg"
            with zipfile.ZipFile(apkg_path, "w") as archive:
                archive.writestr("../collection.anki2", "escape")

            with self.assertRaisesRegex(ConversionError, "Unsafe archive path"):
                convert_apkg_to_csv(apkg_path, Path(tmp) / "out")


if __name__ == "__main__":
    unittest.main()
