from dataclasses import dataclass
from pathlib import Path

from flashcard_enhancer.converter import convert_apkg_to_csv
from flashcard_enhancer.enhancer import EnhancementProvider, enhance_csv


@dataclass(frozen=True)
class PipelineResult:
    converted_files: int
    planned: int
    succeeded: int
    failed: int


async def run_pipeline(
    apkg_path: str | Path,
    base_dir: str | Path,
    enhanced_dir: str | Path,
    failed_dir: str | Path,
    provider: EnhancementProvider,
    *,
    cache_dir: str | Path | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    max_retries: int = 3,
    metadata: dict[str, str] | None = None,
) -> PipelineResult:
    converted_paths = convert_apkg_to_csv(apkg_path, base_dir)
    planned = 0
    succeeded = 0
    failed = 0

    for csv_path in converted_paths:
        cache_path = Path(cache_dir) / f"{csv_path.stem}.json" if cache_dir else None
        result = await enhance_csv(
            csv_path,
            Path(enhanced_dir) / csv_path.name,
            Path(failed_dir) / f"{csv_path.stem}_failed.csv",
            provider,
            limit=limit,
            dry_run=dry_run,
            max_retries=max_retries,
            metadata=metadata,
            cache_path=cache_path,
        )
        planned += result.planned
        succeeded += result.succeeded
        failed += result.failed

    return PipelineResult(
        converted_files=len(converted_paths),
        planned=planned,
        succeeded=succeeded,
        failed=failed,
    )

