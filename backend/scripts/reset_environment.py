"""Empty the database and the R2 bucket.

This deletes every row of application data and every stored photo. It is
destructive and there is no undo, so it refuses to do anything without --yes
and prints exactly which database and bucket it is pointed at first.

    uv run python scripts/reset_environment.py           # dry run, shows counts
    uv run python scripts/reset_environment.py --yes     # actually wipe
    uv run python scripts/reset_environment.py --yes --keep-bucket
    uv run python scripts/reset_environment.py --yes --keep-db

Pair with scripts/seed_realistic_data.py to get back to a populated state.
"""
import argparse
import asyncio
import logging
import re
import sys

from sqlalchemy import text

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.services.r2 import _client  # noqa: E402

# The Windows console defaults to cp1252 and can't encode the box rules below.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Alembic's bookkeeping is schema state, not application data — wiping it would
# strand the database at an unknown migration revision.
PRESERVED_TABLES = {"alembic_version"}

# S3 DeleteObjects caps out at 1000 keys per call.
DELETE_BATCH_SIZE = 1000


def describe_database() -> str:
    """Host + database name, with any credentials stripped out."""
    match = re.search(r"@([^/]+)/([^?\s]+)", settings.database_url)
    if not match:
        return "(could not parse DATABASE_URL)"
    return f"{match.group(2)} @ {match.group(1)}"


async def fetch_table_counts() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
        )
        tables = [row[0] for row in result if row[0] not in PRESERVED_TABLES]

        counts: dict[str, int] = {}
        for table in tables:
            count = await session.execute(text(f'SELECT count(*) FROM "{table}"'))
            counts[table] = count.scalar_one()
        return counts


async def wipe_database(tables: list[str]) -> None:
    """One TRUNCATE across every table at once: CASCADE resolves the foreign-key
    ordering for us, so this can't fail halfway through and leave the data in a
    partially-deleted state the way a sequence of DELETEs can."""
    if not tables:
        print("  nothing to truncate")
        return

    quoted = ", ".join(f'"{t}"' for t in tables)
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
        await session.commit()
    print(f"  truncated {len(tables)} tables")


def list_bucket_keys() -> list[str]:
    paginator = _client().get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=settings.r2_bucket_name):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


def wipe_bucket(keys: list[str]) -> None:
    if not keys:
        print("  bucket already empty")
        return

    deleted = 0
    for start in range(0, len(keys), DELETE_BATCH_SIZE):
        batch = keys[start : start + DELETE_BATCH_SIZE]
        response = _client().delete_objects(
            Bucket=settings.r2_bucket_name,
            Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
        )
        errors = response.get("Errors") or []
        for err in errors:
            print(f"  ! failed {err.get('Key')}: {err.get('Message')}")
        deleted += len(batch) - len(errors)
    print(f"  deleted {deleted} objects")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="actually perform the wipe")
    parser.add_argument("--keep-db", action="store_true", help="leave database rows alone")
    parser.add_argument("--keep-bucket", action="store_true", help="leave R2 objects alone")
    args = parser.parse_args()

    logging.disable(logging.INFO)

    print()
    print("=" * 72)
    print("  DESTRUCTIVE RESET")
    print("=" * 72)
    print(f"  environment : {settings.app_env}")
    print(f"  database    : {describe_database()}")
    print(f"  bucket      : {settings.r2_bucket_name}")
    print("=" * 72)

    counts = {} if args.keep_db else await fetch_table_counts()
    keys = [] if args.keep_bucket else list_bucket_keys()

    print("\nDatabase rows to delete:")
    if args.keep_db:
        print("  (skipped: --keep-db)")
    else:
        populated = {t: c for t, c in counts.items() if c}
        for table, count in sorted(populated.items(), key=lambda kv: -kv[1]):
            print(f"  {table:24} {count:>6}")
        print(f"  {'TOTAL':24} {sum(counts.values()):>6} rows across {len(counts)} tables")

    print("\nBucket objects to delete:")
    print("  (skipped: --keep-bucket)" if args.keep_bucket else f"  {len(keys)} objects")

    if not args.yes:
        print("\nDry run — nothing was changed. Re-run with --yes to apply.\n")
        return 0

    print("\nWiping…")
    if not args.keep_db:
        await wipe_database(list(counts))
    if not args.keep_bucket:
        wipe_bucket(keys)

    print("\nDone. The environment is empty.")
    print("Next: uv run --with pillow python scripts/seed_realistic_data.py\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
