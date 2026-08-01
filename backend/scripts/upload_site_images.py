"""Move the frontend's hard-coded Unsplash images into our own R2 bucket.

The landing page, the articles strip and the auth background were all hotlinking
full-quality Unsplash originals, so every visit waited on someone else's CDN for
the largest images on the page. This fetches each one once, downscales it, and
stores it under site/ in R2.

    uv run --with pillow python scripts/upload_site_images.py            # all
    uv run --with pillow python scripts/upload_site_images.py nappingCats  # one

Naming images uploads only those and leaves every other object in the bucket
untouched — worth doing when only one background changed, since a full run
re-fetches and re-encodes the others for no reason.

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
#
# This list got much shorter. Seven of the nine entries existed to dress the
# landing page's card sections with stock photography: three article headers for
# articles that were never written, two "featured pet" backdrops for pets who do
# not exist, and one dog and one cat tile repeated three times each behind
# invented captions. Those sections now render the real pets out of /pets, with
# the photos their owners actually uploaded, so the stock imagery has nothing
# left to do. The old objects are still in the bucket; nothing references them.
#
# What remains is the two places a photograph is genuinely doing a background's
# job rather than standing in for content:
#
#   heroPets  the landing hero. Chosen for its composition as much as its
#             subject: the light and both animals sit in the right half, and the
#             left falls away into shadow on its own, so the headline column has
#             somewhere dark to live without a scrim heavy enough to flatten the
#             photo. The previous hero was centre-weighted, which is why it
#             needed a near-opaque black wash over the left and ended up looking
#             like a dark rectangle with text on it.
#   duskRun   the landing's closing band. Was the Auth background too until
#             nappingCats took that slot; still renamed from heroDog.
#   nappingCats  the Auth background. Two tabbies asleep against a sunlit wall,
#             supplied by the project owner. Sits under the same two scrims as
#             duskRun did, and those scrims are unchanged, so the brightness has
#             to come out of the file itself — see the gamma column below.
#
# The Unsplash entries are CDN slugs, not the short /photos/<id> links you get
# from the website. unsplash.com/photos/<id>/download answers 403 to any client
# whose User-Agent it does not like — including this script's — so resolve the
# slug once with `curl -sL -o /dev/null -w '%{url_effective}'` and paste it here.
# A source is either an http(s) URL or a path to a local file — anything not
# starting with http is read off disk, so an image supplied directly still goes
# through the same downscale and re-encode as the stock ones instead of being
# dropped into the bucket at whatever size it arrived.
#
# name -> (source, longest edge, gamma)
#
# gamma is a midtone lift applied before the re-encode: 1.0 leaves the file
# alone, above 1.0 brightens. It is a gamma curve rather than a flat brightness
# multiply because a multiply pushes anything already near white straight past
# 255 — and the one photo that needs lifting here is a pale stucco wall that is
# most of the frame. A gamma curve pins 0 and 255 in place and opens up the
# middle, so the cats come forward without the wall clipping to a flat sheet.
IMAGES = {
    # Supplied by the project owner, replacing the Unsplash frame that was here
    # (photo-1711832740932-f7f3fe63cdd5).
    "heroPets": (
        r"C:\Users\Mani Mamidala\Downloads\Untitled - July 27, 2026 at 20.07.50 (2).png",
        1800,
        1.0,
    ),
    "duskRun": (UNSPLASH.format("photo-1548199973-03cce0bbc87b"), 1600, 1.0),
    "nappingCats": (r"D:\img38.jpg", 1600, 1.18),
}


def _apply_gamma(img: "Image.Image", gamma: float) -> "Image.Image":
    """Lift midtones without moving the endpoints. gamma <= 1.0 is a no-op."""
    if gamma <= 1.0:
        return img
    inv = 1.0 / gamma
    lut = [round(255 * ((i / 255) ** inv)) for i in range(256)]
    return img.point(lut * len(img.getbands()))


def main(argv: list[str]) -> int:
    # Naming images on the command line uploads only those, which is the usual
    # case: one background gets replaced and the others should keep the exact
    # bytes already in the bucket rather than being re-fetched and re-encoded.
    unknown = [name for name in argv if name not in IMAGES]
    if unknown:
        print(f"unknown image name(s): {', '.join(unknown)}")
        print(f"known: {', '.join(IMAGES)}")
        return 1
    selected = {name: IMAGES[name] for name in argv} if argv else dict(IMAGES)

    print(f"\nUploading {len(selected)} site images to {settings.r2_bucket_name}\n")
    results: dict[str, str] = {}
    total = 0

    with httpx.Client(headers={"User-Agent": "PawSome-Seeder/1.0"}) as client:
        for name, (source, max_edge, gamma) in selected.items():
            if source.lower().startswith("http"):
                resp = client.get(source, timeout=90, follow_redirects=True)
                resp.raise_for_status()
                raw = resp.content
            else:
                path = Path(source)
                if not path.is_file():
                    print(f"  {name:22} SKIPPED — no such file: {path}")
                    continue
                raw = path.read_bytes()

            with Image.open(io.BytesIO(raw)) as img:
                # JPEG has no alpha, and converting RGBA straight to RGB
                # composites transparency onto black — flatten onto white first.
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                    flat = Image.new("RGB", img.size, (255, 255, 255))
                    flat.paste(img, mask=img.split()[-1])
                    img = flat
                img = img.convert("RGB")
                img.thumbnail((max_edge, max_edge), Image.LANCZOS)
                img = _apply_gamma(img, gamma)
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
            print(f"  {name:22} {len(raw) // 1024:>5} KB -> {len(payload) // 1024:>4} KB")

    print(f"\n  stored {total / 1_048_576:.1f} MB total\n")
    print("-" * 72)
    if argv:
        # A subset run only knows about the keys it uploaded, so pasting the
        # whole object would silently drop the ones it skipped.
        print("// Merge these entries into frontend/src/lib/siteImages.ts")
    else:
        print("// Paste into frontend/src/lib/siteImages.ts")
        print("export const siteImages = {")
    for name, url in results.items():
        print(f"  {name}: '{url}',")
    if not argv:
        print("} as const")
    print("-" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
