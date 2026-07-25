"""Move the frontend's hard-coded Unsplash images into our own R2 bucket.

The landing page, the articles strip and the auth background were all hotlinking
full-quality Unsplash originals, so every visit waited on someone else's CDN for
the largest images on the page. This fetches each one once, downscales it, and
stores it under site/ in R2.

    uv run --with pillow python scripts/upload_site_images.py

Prints a ready-to-paste TypeScript module; the URLs live in
frontend/src/lib/siteImages.ts so there is exactly one place to update if the
bucket ever changes.
"""
import io
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.r2 import _client, public_url  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONTENT_TYPE = "image/jpeg"
QUALITY = 82

UNSPLASH = "https://images.unsplash.com/{}?auto=format&fit=crop&q=80&w=2000"

# name -> (source url, longest edge to store at)
# Widths are chosen for how each image is actually used: full-bleed backgrounds
# get 1600, cards and tiles far less.
#
# articleSocialising is not from Unsplash: the id the frontend had been pointing
# at (photo-1537151608804-ea6f117398e0) now 404s, so that article card has been
# rendering a broken image. Replaced with a dog.ceo photo, which is the same
# source the seeded pets use.
IMAGES = {
    "heroDog": (UNSPLASH.format("photo-1548199973-03cce0bbc87b"), 1600),
    "articleVaccination": (UNSPLASH.format("photo-1629909613654-28e377c37b09"), 900),
    "articleSocialising": (
        "https://images.dog.ceo/breeds/retriever-golden/z6a_3963_200731.jpg",
        900,
    ),
    "articleNutrition": (UNSPLASH.format("photo-1544568100-847a948585b9"), 900),
    "featuredDog": (UNSPLASH.format("photo-1517849845537-4d257902454a"), 1200),
    "featuredCat": (UNSPLASH.format("photo-1513360371669-4adf3dd7dff8"), 1200),
    "toggleDog": (UNSPLASH.format("photo-1583337130417-3346a1be7dee"), 600),
    "toggleCat": (UNSPLASH.format("photo-1514888286974-6c03e2ca1dba"), 600),
}


def main() -> int:
    print(f"\nUploading {len(IMAGES)} site images to {settings.r2_bucket_name}\n")
    results: dict[str, str] = {}
    total = 0

    with httpx.Client(headers={"User-Agent": "PawSome-Seeder/1.0"}) as client:
        for name, (source, max_edge) in IMAGES.items():
            resp = client.get(source, timeout=90, follow_redirects=True)
            resp.raise_for_status()

            with Image.open(io.BytesIO(resp.content)) as img:
                img = img.convert("RGB")
                img.thumbnail((max_edge, max_edge), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=QUALITY, optimize=True)
                payload = buf.getvalue()

            key = f"site/{name}.jpg"
            _client().put_object(
                Bucket=settings.r2_bucket_name,
                Key=key,
                Body=payload,
                ContentType=CONTENT_TYPE,
            )
            results[name] = public_url(key)
            total += len(payload)
            print(f"  {name:22} {len(resp.content) // 1024:>5} KB -> {len(payload) // 1024:>4} KB")

    print(f"\n  stored {total / 1_048_576:.1f} MB total\n")
    print("-" * 72)
    print("// Paste into frontend/src/lib/siteImages.ts")
    print("export const siteImages = {")
    for name, url in results.items():
        print(f"  {name}: '{url}',")
    print("} as const")
    print("-" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
