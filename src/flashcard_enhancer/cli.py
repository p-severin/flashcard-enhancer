import asyncio
import argparse
from pathlib import Path

from flashcard_enhancer.ai_provider import PydanticAiEnhancementProvider
from flashcard_enhancer.converter import ConversionError, convert_apkg_to_csv
from flashcard_enhancer.enhancer import EnhancementError, enhance_csv
from flashcard_enhancer.logging_config import log
from flashcard_enhancer.pipeline import run_pipeline
from flashcard_enhancer.prompts import PROMPT_VERSION, PromptSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flashcard-enhancer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser("convert", help="Convert Anki .apkg to deck CSV files")
    convert.add_argument("apkg_file", help="Path to .apkg file")
    convert.add_argument(
        "-o",
        "--out-dir",
        default="output/base",
        help="Directory for generated CSV files",
    )
    convert.add_argument(
        "-k",
        "--keys",
        nargs="+",
        default=None,
        help="Fields to write to CSV",
    )

    enhance = subparsers.add_parser("enhance", help="Enhance a card CSV with AI fields")
    enhance.add_argument("input_csv", help="CSV with Front, Back and deck_name columns")
    enhance.add_argument("--output", required=True, help="Path for enhanced CSV output")
    enhance.add_argument(
        "--failed-output",
        required=True,
        help="Path for cards that failed enhancement",
    )
    enhance.add_argument(
        "--cache",
        default=None,
        help="Optional JSON cache path for generated cards",
    )
    enhance.add_argument(
        "--model",
        default="openai:gpt-5-mini",
        help="Pydantic AI model name",
    )
    enhance.add_argument("--limit", type=int, default=None, help="Only process N cards")
    enhance.add_argument(
        "--source-language",
        default="front language",
        help="Language used by the Front field",
    )
    enhance.add_argument(
        "--target-language",
        default="back language",
        help="Language used by the Back field",
    )
    enhance.add_argument(
        "--level",
        default="natural learner-appropriate",
        help="Desired learner level for generated examples",
    )
    enhance.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Attempts per card before recording failure",
    )
    enhance.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input and planned work without calling AI or writing outputs",
    )

    pipeline = subparsers.add_parser(
        "pipeline", help="Convert an Anki .apkg and enhance the generated CSV files"
    )
    pipeline.add_argument("apkg_file", help="Path to .apkg file")
    pipeline.add_argument("--base-dir", default="output/base")
    pipeline.add_argument("--enhanced-dir", default="output/enhanced")
    pipeline.add_argument("--failed-dir", default="output/failed")
    pipeline.add_argument("--cache-dir", default="output/cache")
    pipeline.add_argument("--model", default="openai:gpt-5-mini")
    pipeline.add_argument("--limit", type=int, default=None)
    pipeline.add_argument("--source-language", default="front language")
    pipeline.add_argument("--target-language", default="back language")
    pipeline.add_argument("--level", default="natural learner-appropriate")
    pipeline.add_argument("--max-retries", type=int, default=3)
    pipeline.add_argument(
        "--dry-run",
        action="store_true",
        help="Convert and validate generated CSVs without calling AI",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "convert":
            output_paths = convert_apkg_to_csv(
                Path(args.apkg_file), Path(args.out_dir), keys=args.keys
            )
            for output_path in output_paths:
                log.info(f"Wrote {output_path}")
            return 0
        if args.command == "enhance":
            prompt_settings = PromptSettings(
                source_language=args.source_language,
                target_language=args.target_language,
                level=args.level,
            )
            provider = (
                _dry_run_provider
                if args.dry_run
                else PydanticAiEnhancementProvider(args.model, prompt_settings)
            )
            result = asyncio.run(
                enhance_csv(
                    Path(args.input_csv),
                    Path(args.output),
                    Path(args.failed_output),
                    provider,
                    limit=args.limit,
                    dry_run=args.dry_run,
                    max_retries=args.max_retries,
                    metadata={
                        "prompt_version": PROMPT_VERSION,
                        "model": args.model,
                        "source_language": args.source_language,
                        "target_language": args.target_language,
                        "level": args.level,
                    },
                    cache_path=Path(args.cache) if args.cache else None,
                )
            )
            log.info(
                f"Planned {result.planned}, succeeded {result.succeeded}, failed {result.failed}"
            )
            return 0
        if args.command == "pipeline":
            prompt_settings = PromptSettings(
                source_language=args.source_language,
                target_language=args.target_language,
                level=args.level,
            )
            provider = (
                _dry_run_provider
                if args.dry_run
                else PydanticAiEnhancementProvider(args.model, prompt_settings)
            )
            result = asyncio.run(
                run_pipeline(
                    Path(args.apkg_file),
                    Path(args.base_dir),
                    Path(args.enhanced_dir),
                    Path(args.failed_dir),
                    provider,
                    cache_dir=Path(args.cache_dir),
                    limit=args.limit,
                    dry_run=args.dry_run,
                    max_retries=args.max_retries,
                    metadata={
                        "prompt_version": PROMPT_VERSION,
                        "model": args.model,
                        "source_language": args.source_language,
                        "target_language": args.target_language,
                        "level": args.level,
                    },
                )
            )
            log.info(
                f"Converted {result.converted_files}, planned {result.planned}, "
                f"succeeded {result.succeeded}, failed {result.failed}"
            )
            return 0
    except (ConversionError, EnhancementError, FileNotFoundError) as error:
        log.error(str(error))
        return 1

    parser.print_help()
    return 1


async def _dry_run_provider(card):
    raise RuntimeError("Dry run provider should not be called")


if __name__ == "__main__":
    raise SystemExit(main())
