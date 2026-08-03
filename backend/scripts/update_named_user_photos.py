"""Replace the profile photo for a fixed set of named seeded users.

Six of the pre-seeded demo accounts (see PEOPLE in seed_data.py) get a specific
local image as their new profile_photo_url instead of the i.pravatar.cc image
seed_realistic_data.py originally assigned them. Everything else about the
account (email, bio, pets, matches...) is untouched.

The object key is the same deterministic one seed_realistic_data.py uses
(build_user_photo_key -> users/{user_id}/profile.jpg), so uploading here
overwrites the previous object in place. No separate delete step is needed.

    uv run --with pillow python scripts/update_named_user_photos.py            # dry run, no writes
    uv run --with pillow python scripts/update_named_user_photos.py --apply    # upload + commit
"""
import argparse
import asyncio
import io
import sys
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
from app.services.r2 import _client, build_user_photo_key, public_url  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Matches seed_realistic_data.py's profile-photo treatment exactly, so a
# replaced photo looks consistent with the ones still on the pravatar default.
PROFILE_PHOTO_MAX_EDGE = 512
JPEG_QUALITY = 82
CONTENT_TYPE = "image/jpeg"

SCREENSHOT_DIR = Path(r"C:\Users\Mani Mamidala\OneDrive\Pictures\Screenshots 1")

# full_name (as stored in seed_data.py's PEOPLE list) -> source image on disk.
REPLACEMENTS = {
    "Arjun Reddy": SCREENSHOT_DIR / "Screenshot 2026-08-04 003815.png",
    "Rahul Verma": SCREENSHOT_DIR / "Screenshot 2026-08-04 004008.png",
    "Vikram Choudhary": SCREENSHOT_DIR / "Screenshot 2026-08-04 004104.png",
    "Rohit Kulkarni": SCREENSHOT_DIR / "Screenshot 2026-08-04 004301.png",
    "Meera Nair": SCREENSHOT_DIR / "Screenshot 2026-08-04 004512.png",
    "Divya Menon": SCREENSHOT_DIR / "Screenshot 2026-08-04 004530.png",
}


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

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.full_name.in_(REPLACEMENTS.keys()))
        )
        users = {u.full_name: u for u in result.scalars().all()}

        not_found = [name for name in REPLACEMENTS if name not in users]
        if not_found:
            print("No matching user row for:")
            for name in not_found:
                print(f"  {name}")

        print(f"\n{'Uploading' if apply else 'Would upload'} {len(users)} profile photo(s)\n")

        for name, path in REPLACEMENTS.items():
            user = users.get(name)
            if user is None:
                continue

            raw = path.read_bytes()
            payload = process_image(raw)
            key = build_user_photo_key(user.id, CONTENT_TYPE)
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
