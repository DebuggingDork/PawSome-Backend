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
from typing import NamedTuple

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.r2 import _client, public_url  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUALITY = 82

CONTENT_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

UNSPLASH = "https://images.unsplash.com/{}?auto=format&fit=crop&q=80&w=2000"


class SiteImage(NamedTuple):
    """One object in the bucket.

    `key` is spelled out rather than derived from the dict key because it is not
    always `site/<name>.jpg`: the hero is a PNG under a different name, and
    guessing the key is how this script came to write `site/heroPets.jpg` — an
    object nothing has ever referenced — while the hero the site actually loads
    sat untouched beside it. Deriving the key made a full run look like it had
    republished everything when it had in fact quietly missed the largest image
    on the site.

    `max_edge` of None stores the source bytes exactly as they arrived, with no
    downscale, re-encode or grade. `gamma` above 1.0 lifts midtones on the way
    through; it only applies when the image is being re-encoded anyway.
    """

    source: str
    key: str
    max_edge: int | None = None
    gamma: float = 1.0


# name -> SiteImage
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
#   duskRun   the landing's closing band. Was the Auth background too until the
#             cats took that slot; still renamed from heroDog.
#   porchCats the Auth background. Two cats resting on a garden ledge behind
#             bougainvillea. Sits under the same two scrims duskRun did, and
#             those scrims are unchanged, so the brightness has to come out of
#             the file itself — see the gamma field on SiteImage.
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
IMAGES = {
    # Supplied by the project owner, replacing the Unsplash frame that was here
    # (photo-1711832740932-f7f3fe63cdd5). Stored byte for byte as the PNG it
    # arrived as, which is why it carries no max_edge: the hero is the whole
    # first viewport and re-encoding it to an 82-quality JPEG was visible.
    #
    # The source path no longer exists — the file was cleared out of Downloads
    # after it was uploaded, so the object in the bucket is now the only copy.
    # A run that includes this entry prints SKIPPED and moves on, which is the
    # intended behaviour: there is nothing to re-derive it from, and the live
    # object is correct. Point this at a real file again before expecting it to
    # republish.
    "heroPets": SiteImage(
        r"C:\Users\Mani Mamidala\Downloads\Untitled - July 27, 2026 at 20.07.50 (2).png",
        "site/final-home-page-image.png",
    ),
    "duskRun": SiteImage(
        UNSPLASH.format("photo-1548199973-03cce0bbc87b"),
        "site/duskRun.jpg",
        1600,
    ),
    # Auth background. Replaced nappingCats (site/nappingCats.jpg, two tabbies
    # asleep on a wall) the same day it went up; that object is still in the
    # bucket and nothing references it now.
    #
    # A new key rather than a rewrite of the old one on purpose: r2.dev caches,
    # and an overwrite behind the same URL can keep serving the previous image
    # for as long as it feels like. A new key is the only way to be certain the
    # swap is actually visible.
    "porchCats": SiteImage(
        r"D:\prasad-bhalerao-NKPXEz7MNlk-unsplash.jpg",
        "site/porchCats.jpg",
        1600,
        1.18,
    ),
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
        for name, spec in selected.items():
            source, key, max_edge, gamma = spec
            content_type = CONTENT_TYPES.get(Path(key).suffix.lower())
            if content_type is None:
                print(f"  {name:22} SKIPPED — unsupported extension in key: {key}")
                continue

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

            if max_edge is None:
                # Byte for byte. Anything stored this way is displayed at a size
                # where the re-encode below was visible, so the only safe
                # transform is none at all.
                payload = raw
            else:
                with Image.open(io.BytesIO(raw)) as img:
                    # JPEG has no alpha, and converting RGBA straight to RGB
                    # composites transparency onto black — flatten onto white
                    # first.
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

            _client().put_object(
                Bucket=settings.r2_bucket_name,
                Key=key,
                Body=payload,
                ContentType=content_type,
            )
            results[name] = public_url(key)
            total += len(payload)
            note = "" if max_edge else "  (stored as-is)"
            print(
                f"  {name:22} {len(raw) // 1024:>5} KB -> {len(payload) // 1024:>4} KB"
                f"  {key}{note}"
            )

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
