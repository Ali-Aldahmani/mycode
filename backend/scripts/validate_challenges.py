"""Validate every challenge in /challenges.

    python -m scripts.validate_challenges [--dir PATH]

Exit code 1 if any challenge is invalid.
"""
import argparse
import sys
from pathlib import Path

from app.challenges.validation import load_dir
from app.core.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=settings.challenges_dir)
    args = parser.parse_args()
    reports = load_dir(args.dir)
    bad = 0
    for r in reports:
        name = r.seed.slug if r.seed else r.path.name
        if r.ok:
            print(f"  ok   {r.seed.order:>3}  {name}")  # type: ignore[union-attr]
        else:
            bad += 1
            print(f"  FAIL      {name}")
            for e in r.errors:
                print(f"            - {e}")
    print(f"\n{len(reports) - bad} valid, {bad} invalid, {len(reports)} total")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
