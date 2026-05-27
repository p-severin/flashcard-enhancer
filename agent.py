import sys
from pathlib import Path

from flashcard_enhancer.cli import main as cli_main
from flashcard_enhancer.logging_config import log


def main() -> int:
    exit_code = 0
    for input_file in Path("output/base").glob("*.csv"):
        log.info(f"Enhancing {input_file}")
        result = cli_main(
            [
                "enhance",
                str(input_file),
                "--output",
                str(Path("output/enhanced") / input_file.name),
                "--failed-output",
                str(Path("output/failed") / f"{input_file.stem}_failed.csv"),
                "--cache",
                str(Path("output/cache") / f"{input_file.stem}.json"),
            ]
        )
        exit_code = max(exit_code, result)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
