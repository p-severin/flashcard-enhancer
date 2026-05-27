import csv
import html
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any

DEFAULT_KEYS = ["Front", "Back", "deck_name"]


class ConversionError(Exception):
    """Raised when an Anki archive cannot be converted."""


def clean_html(text: str) -> str:
    text = re.sub("<.*?>", "", text)
    text = html.unescape(text)
    return " ".join(text.split())


def extract_cards_data(db_path: str | Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        col_cursor = conn.execute("SELECT decks, models FROM col LIMIT 1")
        col_row = col_cursor.fetchone()
        if not col_row:
            raise ConversionError("No collection data found in database")

        decks_json = json.loads(col_row["decks"])
        models_json = json.loads(col_row["models"])
        cursor = conn.execute(
            """
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
        )

        cards = []
        for row in cursor:
            deck_id = str(row["deck_id"])
            deck_name = decks_json.get(deck_id, {}).get(
                "name", f"Unknown Deck ({deck_id})"
            )
            model_id = str(row["model_id"])
            model_info = models_json.get(model_id, {})
            model_name = model_info.get("name", f"Unknown Model ({model_id})")
            field_names = [field["name"] for field in model_info.get("flds", [])]
            fields = row["fields"].split("\x1f")
            field_dict = {
                field_name: clean_html(fields[index]) if index < len(fields) else ""
                for index, field_name in enumerate(field_names)
            }
            cards.append(
                {
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
            )
        return cards


def convert_apkg_to_csv(
    apkg_path: str | Path,
    out_dir: str | Path,
    keys: list[str] | None = None,
) -> list[Path]:
    apkg = Path(apkg_path)
    if not apkg.exists():
        raise FileNotFoundError(f"File not found: {apkg}")

    selected_keys = keys or DEFAULT_KEYS
    destination = Path(out_dir)
    with tempfile.TemporaryDirectory() as temp_dir:
        collection_path = _extract_collection(apkg, Path(temp_dir))
        cards = extract_cards_data(collection_path)

    if not cards:
        return []

    destination.mkdir(parents=True, exist_ok=True)
    grouped_cards: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        grouped_cards.setdefault(str(card["deck_name"]), []).append(card)

    output_paths = []
    for deck_name, deck_cards in grouped_cards.items():
        deck_suffix = deck_name.split("::")[-1].strip() or "deck"
        output_path = destination / f"{_safe_filename(deck_suffix)}.csv"
        with output_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=selected_keys)
            writer.writeheader()
            for card in deck_cards:
                writer.writerow({key: card.get(key, "") for key in selected_keys})
        output_paths.append(output_path)

    return output_paths


def _extract_collection(apkg_path: Path, temp_dir: Path) -> Path:
    try:
        with zipfile.ZipFile(apkg_path, "r") as archive:
            _safe_extract_all(archive, temp_dir)
    except zipfile.BadZipFile as error:
        raise ConversionError(f"Invalid Anki archive: {apkg_path}") from error

    for collection_name in ("collection.anki2", "collection.anki21"):
        collection_path = temp_dir / collection_name
        if collection_path.exists():
            return collection_path
    raise ConversionError("No collection database found in .apkg file")


def _safe_extract_all(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (root / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ConversionError(f"Unsafe archive path: {member.filename}")
    archive.extractall(root)


def _safe_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip()
    return sanitized or "deck"

