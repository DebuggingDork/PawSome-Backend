"""Replace or clear the profile photo for a fixed set of named seeded users.

REPLACEMENTS entries get a specific local image as their new profile_photo_url
instead of the i.pravatar.cc image seed_realistic_data.py originally assigned
them. REMOVALS entries get profile_photo_url set back to NULL, so the UI falls
back to its default letter-avatar. Everything else about each account (email,
bio, pets, matches...) is untouched.

Deliberately does NOT reuse the deterministic users/{id}/profile.jpg key
seed_realistic_data.py writes to. r2.dev caches aggressively and an overwrite
behind the same URL can keep serving the previous bytes indefinitely (see the
same note on porchCats in upload_site_images.py) — a first run of this script
did exactly that: the DB and the origin object were both correct, but cards
kept showing the old face because the CDN never re-fetched. Each run instead
mints a fresh key (users/{id}/profile-{8 hex}.jpg), so the URL itself changes
and there is nothing to be stale.

    uv run --with pillow python scripts/update_named_user_photos.py            # dry run, no writes
    uv run --with pillow python scripts/update_named_user_photos.py --apply    # upload + commit
"""
import argparse
import asyncio
import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402

# User declares relationships to these by name, so they must be imported before
# SQLAlchemy configures its mappers (same requirement as backfill_achievements.py).
from app.models.match_preference import MatchPreference  # noqa: E402,F401
from app.models.pet_profile import PetProfile  # noqa: E402,F401
from app.models.user import User  # noqa: E402
from app.services.r2 import _client, public_url  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Matches seed_realistic_data.py's profile-photo treatment exactly, so a
# replaced photo looks consistent with the ones still on the pravatar default.
PROFILE_PHOTO_MAX_EDGE = 512
JPEG_QUALITY = 82
CONTENT_TYPE = "image/jpeg"

SCREENSHOT_DIR = Path(r"C:\Users\Mani Mamidala\OneDrive\Pictures\Screenshots 1")

# full_name (as stored in seed_data.py's PEOPLE list) -> source image on disk.
REPLACEMENTS: dict[str, Path] = {}

# full_name -> profile_photo_url reverted to NULL, so the UI falls back to its
# default letter-avatar instead of any photo.
REMOVALS = ["Zoya Begum", "Aditya Bose", "Kavya Srinivasan"]


def process_image(raw: bytes) -> bytes:
    with Image.open(io.BytesIO(raw)) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            flat = Image.new("RGB", img.size, (255, 255, 255))
            flat.paste(img, mask=img.split()[-1])
            img = flat
        img = img.convert("RGB")
        img.thumbnail((PROFILE_PHOTO_MAX_EDGE, PROFILE_PHOTO_MAX_EDGE), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue()


async def main(apply: bool) -> int:
    missing = [name for name, path in REPLACEMENTS.items() if not path.is_file()]
    if missing:
        print("Missing source file(s), aborting:")
        for name in missing:
            print(f"  {name}: {REPLACEMENTS[name]}")
        return 1

    all_names = list(REPLACEMENTS.keys()) + REMOVALS
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.full_name.in_(all_names)))
        users = {u.full_name: u for u in result.scalars().all()}

        not_found = [name for name in all_names if name not in users]
        if not_found:
            print("No matching user row for:")
            for name in not_found:
                print(f"  {name}")

        print(f"\n{'Uploading' if apply else 'Would upload'} {len(REPLACEMENTS)} profile photo(s)\n")

        for name, path in REPLACEMENTS.items():
            user = users.get(name)
            if user is None:
                continue

            raw = path.read_bytes()
            payload = process_image(raw)
            key = f"users/{user.id}/profile-{uuid.uuid4().hex[:8]}.jpg"
            new_url = public_url(key)

            print(
                f"  {name:20} {user.id}  {len(raw) // 1024:>4} KB -> {len(payload) // 1024:>4} KB"
                f"  old={user.profile_photo_url}"
            )
            print(f"  {'':20} new={new_url}")

            if apply:
                _client().put_object(
                    Bucket=settings.r2_bucket_name,
                    Key=key,
                    Body=payload,
                    ContentType=CONTENT_TYPE,
                )
                user.profile_photo_url = new_url

        print(f"\n{'Clearing' if apply else 'Would clear'} {len(REMOVALS)} profile photo(s)\n")

        for name in REMOVALS:
            user = users.get(name)
            if user is None:
                continue
            print(f"  {name:20} {user.id}  old={user.profile_photo_url}  new=None")
            if apply:
                user.profile_photo_url = None

        if apply:
            await session.commit()
            print("\nCommitted.")
        else:
            print("\nDry run only — re-run with --apply to upload and save.")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually upload and commit")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
