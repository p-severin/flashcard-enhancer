import csv
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from flashcard_enhancer.models import AdditionalFields, RawCard
from flashcard_enhancer.run_settings import EnhancementOptions

REQUIRED_INPUT_COLUMNS = ["Front", "Back", "deck_name"]
ENHANCED_FIELDNAMES = [
    "Front",
    "Back",
    "deck_name",
    "example_sentence_front",
    "example_sentence_back",
]
FAILED_FIELDNAMES = ["Front", "Back", "deck_name", "error"]


class EnhancementError(Exception):
    """Raised when a card CSV cannot be enhanced."""


@dataclass(frozen=True)
class EnhancementRunResult:
    planned: int
    succeeded: int
    failed: int


EnhancementProvider = Callable[[RawCard], Awaitable[AdditionalFields]]


async def enhance_csv(
    input_path: str | Path,
    output_path: str | Path,
    failed_path: str | Path,
    provider: EnhancementProvider,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    max_retries: int = 3,
    metadata: dict[str, str] | None = None,
    cache_path: str | Path | None = None,
    resume: bool = True,
    options: EnhancementOptions | None = None,
) -> EnhancementRunResult:
    run_options = options or EnhancementOptions(
        limit=limit,
        dry_run=dry_run,
        max_retries=max_retries,
        metadata=metadata,
        cache_path=Path(cache_path) if cache_path else None,
        resume=resume,
    )
    run_metadata = run_options.effective_metadata()
    cards = _read_cards(Path(input_path), limit=run_options.limit)
    if run_options.dry_run:
        return EnhancementRunResult(planned=len(cards), succeeded=0, failed=0)

    output = Path(output_path)
    existing_rows = _read_existing_output(output) if run_options.resume else []
    completed_cards = {
        (row.get("Front", ""), row.get("Back", ""), row.get("deck_name", ""))
        for row in existing_rows
    }
    cache = _load_cache(run_options.cache_path) if run_options.cache_path else {}
    enhanced_rows = []
    failed_rows = []
    for card in cards:
        card_identity = (card.front, card.back, card.deck_name)
        if card_identity in completed_cards:
            continue

        cache_key = _cache_key(card, run_metadata)
        if cache_key in cache:
            enhanced_rows.append(cache[cache_key])
            continue

        try:
            additional_fields = await _enhance_with_retries(
                provider, card, run_options.max_retries
            )
        except Exception as error:
            failed_rows.append(
                {
                    "Front": card.front,
                    "Back": card.back,
                    "deck_name": card.deck_name,
                    "error": str(error),
                }
            )
            continue

        enhanced_row = {
            "Front": card.front,
            "Back": card.back,
            "deck_name": card.deck_name,
            "example_sentence_front": additional_fields.example_sentence_front,
            "example_sentence_back": additional_fields.example_sentence_back,
            **run_metadata,
        }
        enhanced_rows.append(enhanced_row)
        cache[cache_key] = enhanced_row

    output_rows = existing_rows + enhanced_rows
    if output_rows:
        metadata_fieldnames = list(run_metadata.keys())
        _write_rows(
            output,
            _fieldnames_for_rows(ENHANCED_FIELDNAMES + metadata_fieldnames, output_rows),
            output_rows,
        )
    if failed_rows:
        _write_rows(Path(failed_path), FAILED_FIELDNAMES, failed_rows)
    if run_options.cache_path:
        _write_cache(run_options.cache_path, cache)

    return EnhancementRunResult(
        planned=len(cards), succeeded=len(enhanced_rows), failed=len(failed_rows)
    )


def _read_cards(input_path: Path, limit: int | None) -> list[RawCard]:
    with input_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in fieldnames]
        if missing:
            raise EnhancementError(
                f"Missing required columns: {', '.join(missing)}"
            )

        cards = [
            RawCard(
                front=row["Front"],
                back=row["Back"],
                deck_name=row["deck_name"],
            )
            for row in reader
        ]
    return cards[:limit] if limit is not None else cards


async def _enhance_with_retries(
    provider: EnhancementProvider, card: RawCard, max_retries: int
) -> AdditionalFields:
    attempts = max(1, max_retries)
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await provider(card)
        except Exception as error:
            last_error = error
    if last_error is None:
        raise EnhancementError("Enhancement failed without an error")
    raise last_error


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_existing_output(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _fieldnames_for_rows(
    preferred_fieldnames: list[str], rows: list[dict[str, str]]
) -> list[str]:
    fieldnames = list(preferred_fieldnames)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


def _load_cache(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_cache(path: Path, cache: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _cache_key(card: RawCard, metadata: dict[str, str]) -> str:
    payload = {
        "front": card.front,
        "back": card.back,
        "deck_name": card.deck_name,
        "metadata": metadata,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
