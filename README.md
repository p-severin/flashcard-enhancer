# Flashcard Enhancer

Python CLI for converting Anki `.apkg` exports into deck CSV files and enhancing
those CSV files with AI-generated learning fields.

## Setup

Set your model provider credentials before live enhancement runs. For OpenAI via
Pydantic AI:

```bash
export OPENAI_API_KEY="..."
```

Dry runs and tests do not call the AI provider.

## Convert an Anki deck

```bash
uv run flashcard-enhancer convert path/to/deck.apkg --out-dir output/base
```

Default CSV fields:

- `Front`
- `Back`
- `deck_name`

## Enhance a CSV

```bash
uv run flashcard-enhancer enhance output/base/Italian.csv \
  --output output/enhanced/Italian.csv \
  --failed-output output/failed/Italian_failed.csv \
  --cache output/cache/Italian.json \
  --source-language Italian \
  --target-language English \
  --level A1 \
  --limit 10 \
  --dry-run
```

Remove `--dry-run` to call the configured AI model.

## Run the full pipeline

```bash
uv run flashcard-enhancer pipeline path/to/deck.apkg \
  --base-dir output/base \
  --enhanced-dir output/enhanced \
  --failed-dir output/failed \
  --cache-dir output/cache \
  --source-language Italian \
  --target-language English \
  --level A1 \
  --limit 10 \
  --dry-run
```

The pipeline converts the `.apkg` into deck CSV files, then enhances each CSV.
With `--dry-run`, it validates the generated CSVs without AI calls or enhanced
output writes.

## Verify

```bash
uv run python -m unittest discover -s tests
```
