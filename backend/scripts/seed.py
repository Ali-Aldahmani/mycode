"""Seed the database: the default user and every *valid* challenge.

    python -m scripts.seed [--dir PATH] [--create-tables]

Invalid challenges are reported and skipped; they never reach the database.
`--create-tables` is for quick local runs without Alembic (e.g. SQLite).
"""
import argparse
import sys
from pathlib import Path

from app.challenges.service import upsert
from app.challenges.validation import load_dir, valid_seeds
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.core import models  # noqa: F401  (register tables)
from app.users.service import get_or_create_default_user


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=settings.challenges_dir)
    parser.add_argument("--create-tables", action="store_true")
    args = parser.parse_args()
    if args.create_tables:
        Base.metadata.create_all(engine)

    reports = load_dir(args.dir)
    for r in reports:
        if not r.ok:
            print(f"skip {r.path.name}:")
            for e in r.errors:
                print(f"   - {e}")
    seeds = valid_seeds(reports)
    with SessionLocal() as db:
        user = get_or_create_default_user(db)
        created, updated = upsert(db, seeds)
    print(f"user {user.username!r} ready; challenges: {created} created, {updated} updated, "
          f"{len(reports) - len(seeds)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
