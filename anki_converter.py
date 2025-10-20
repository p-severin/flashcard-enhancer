#!/usr/bin/env python3
"""
Anki .apkg to CSV/JSON Converter

Converts Anki flashcard deck files (.apkg) to CSV or JSON format.
.apkg files are ZIP archives containing SQLite databases.
"""

import argparse
import html
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, TypedDict

import pandas as pd

from custom_logger import log


def extract_apkg(apkg_path: str | Path) -> str:
    """Extract .apkg file and return path to collection.anki2 database."""
    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(apkg_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    collection_path = Path(temp_dir) / "collection.anki2"
    if not collection_path.exists():
        collection_path = Path(temp_dir) / "collection.anki21"

    if not collection_path.exists():
        raise FileNotFoundError("No collection database found in .apkg file")

    return str(collection_path)


def clean_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities from text."""
    text = re.sub("<.*?>", "", text)
    text = html.unescape(text)
    text = " ".join(text.split())
    return text


def extract_cards_data(db_path: str) -> List[Dict[str, Any]]:
    """Extract flashcard data from Anki database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get decks and models information from col table
    col_cursor = conn.execute("SELECT decks, models FROM col LIMIT 1")
    col_row = col_cursor.fetchone()

    if not col_row:
        raise ValueError("No collection data found in database")

    decks_json = json.loads(col_row["decks"])
    models_json = json.loads(col_row["models"])

    # Query to get cards with their notes
    query = """
    SELECT
        n.id as note_id,
        n.flds as fields,
        n.tags,
        n.mid as model_id,
        c.id as card_id,
        c.ord as card_order,
        c.type as card_type,
        c.queue as card_queue,
        c.due,
        c.ivl as interval,
        c.factor,
        c.reps as repetitions,
        c.lapses,
        c.did as deck_id
    FROM cards c
    JOIN notes n ON c.nid = n.id
    ORDER BY c.did, n.id, c.ord
    """

    cursor = conn.execute(query)
    cards = []

    for row in cursor:
        # Look up deck name
        deck_id = str(row["deck_id"])
        deck_name = decks_json.get(deck_id, {}).get("name", f"Unknown Deck ({deck_id})")

        # Look up model information
        model_id = str(row["model_id"])
        model_info = models_json.get(model_id, {})
        model_name = model_info.get("name", f"Unknown Model ({model_id})")

        # Get field names from model
        field_names = []
        if "flds" in model_info:
            field_names = [field["name"] for field in model_info["flds"]]

        # Parse note fields
        fields = row["fields"].split("\x1f")  # Anki uses ASCII Unit Separator

        # Create field dictionary
        field_dict = {}
        for i, field_name in enumerate(field_names):
            if i < len(fields):
                field_dict[field_name] = clean_html(fields[i])
            else:
                field_dict[field_name] = ""

        card_data = {
            "note_id": row["note_id"],
            "card_id": row["card_id"],
            "deck_name": deck_name,
            "model_name": model_name,
            "card_order": row["card_order"],
            "tags": row["tags"],
            "card_type": row["card_type"],
            "queue": row["card_queue"],
            "due": row["due"],
            "interval": row["interval"],
            "factor": row["factor"],
            "repetitions": row["repetitions"],
            "lapses": row["lapses"],
            **field_dict,
        }

        cards.append(card_data)

    conn.close()
    return cards


class OutArgs(TypedDict):
    apkg_path: str
    out_dir: str
    keys_to_extract: List[str]


def parse_args() -> OutArgs:
    parser = argparse.ArgumentParser(
        description="Convert Anki .apkg files to CSV or JSON"
    )
    parser.add_argument("apkg_file", help="Path to .apkg file")
    parser.add_argument(
        "-o",
        "--out_dir",
        default="output/",
        type=str,
        help="Output file path (without extension)",
    )
    parser.add_argument(
        "-k",
        "--keys",
        nargs="+",
        default=["Front", "Back", "deck_name"],
        help="Specific fields to extract from notes",
    )

    args = parser.parse_args()
    return {
        "apkg_path": args.apkg_file,
        "out_dir": args.out_dir,
        "keys_to_extract": args.keys,
    }


def main():
    # Generate output path if not provided
    args_dict: OutArgs | None = parse_args()
    file_path = Path(args_dict["apkg_path"])
    keys = args_dict["keys_to_extract"]

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        log.info(f"Extracting {file_path}...")
        db_path = extract_apkg(file_path)
        log.info("Reading flashcard data...")
        cards = extract_cards_data(db_path)

        if not cards:
            log.warning("No cards found in the deck")
            return

        log.info(
            f"Found {len(cards)} cards in {len(set(card['deck_name'] for card in cards))} deck(s)"
        )
        csv_path: Path = Path(args_dict["out_dir"]) / file_path.with_suffix(".csv").name

        df = pd.DataFrame(cards, columns=keys)
        for index, group in df.groupby("deck_name"):
            deck_name = str(index)
            deck_suffix = deck_name.split("::")[-1].strip()
            deck_csv_path = csv_path.with_stem(f"{deck_suffix}")

            log.info(f"Writing deck '{deck_name}' to {deck_csv_path}...")
            group.to_csv(deck_csv_path, index=False)

        log.info("Conversion completed successfully!")

    except Exception as e:
        log.error(f"Error: {e}")


if __name__ == "__main__":
    main()
