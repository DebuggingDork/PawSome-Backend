"""Populate an empty environment with realistic Hyderabad users, pets and matches.

Every image is fetched once from its source, re-encoded, uploaded to our own R2
bucket, and stored in the database as an R2 URL. Nothing points at a third-party
host at runtime — that hotlinking is what made pet cards slow to paint, since
each card was waiting on a round trip to someone else's CDN.

Photo sources (fetched once, at seed time only):
  dogs  -> dog.ceo, by breed, so a beagle actually looks like a beagle
  cats  -> TheCatAPI, by breed id
  faces -> i.pravatar.cc, one fixed id per person so runs are reproducible

Pillow is only needed here, not by the app, so pull it in for the run:

    uv run --with pillow python scripts/seed_realistic_data.py

Expects an empty database — run scripts/reset_environment.py --yes first.
Flags:
    --no-images   create rows without photos (fast structural smoke test)
    --concurrency N   parallel image workers (default 8)
"""
import argparse
import asyncio
import io
import logging
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.chat_participant import ChatParticipant  # noqa: E402
from app.models.match import Match  # noqa: E402
from app.models.match_preference import MatchPreference  # noqa: E402
from app.models.message import Message  # noqa: E402
from app.models.notification import Notification, NotificationType  # noqa: E402
from app.models.pet_photo import PetPhoto  # noqa: E402
from app.models.pet_profile import PetProfile, PetSpecies  # noqa: E402
from app.models.swipe import Swipe, SwipeAction  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.r2 import _client, build_object_key, build_user_photo_key, public_url  # noqa: E402

from backfill_achievements import sync_achievements  # noqa: E402
from seed_data import (  # noqa: E402
    AREAS,
    CONVERSATIONS,
    MATCHES,
    PENDING_LIKES,
    PEOPLE,
    READ_NOTIFICATION_AGE_MINUTES,
    SKIPS,
    SUPER_LIKES,
)

# Every seeded account shares this password. Nine characters, so it also clears
# the 8-char minimum the registration endpoint enforces — these accounts could
# be re-created or password-reset through the API as-is.
SEED_PASSWORD = "123456789"

PET_PHOTO_MAX_EDGE = 1280
PROFILE_PHOTO_MAX_EDGE = 512
JPEG_QUALITY = 82
CONTENT_TYPE = "image/jpeg"

# Fixed seed so repeated runs pick the same photos for the same pets.
RNG = random.Random(20260726)

SPECIES = {"dog": PetSpecies.DOG, "cat": PetSpecies.CAT}


def _jitter() -> float:
    """Scatter pets a few hundred metres around their owner, so the deck shows a
    spread of distances instead of a stack of identical ones."""
    return RNG.uniform(-0.004, 0.004)


def log(msg: str) -> None:
    print(msg, flush=True)


# The Windows console defaults to cp1252, which can't encode the arrows and box
# rules used below (and would take the whole run down mid-print).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── Image sourcing ────────────────────────────────────────────────────────────
async def resolve_dog_urls(client: httpx.AsyncClient, breed_path: str, count: int) -> list[str]:
    """dog.ceo exposes the full list per breed, so we can sample without repeats."""
    resp = await client.get(f"https://dog.ceo/api/breed/{breed_path}/images", timeout=30)
    resp.raise_for_status()
    urls = resp.json().get("message", [])
    if not urls:
        raise RuntimeError(f"dog.ceo returned no images for {breed_path}")
    return RNG.sample(urls, min(count, len(urls)))


async def resolve_cat_urls(client: httpx.AsyncClient, breed_id: str, count: int) -> list[str]:
    """TheCatAPI caps an anonymous search at 10 results, which comfortably covers
    the few photos any one breed needs here."""
    resp = await client.get(
        "https://api.thecatapi.com/v1/images/search",
        params={"limit": 10, "breed_ids": breed_id},
        timeout=30,
    )
    resp.raise_for_status()
    urls = [item["url"] for item in resp.json()]
    if not urls:
        raise RuntimeError(f"TheCatAPI returned no images for {breed_id}")
    RNG.shuffle(urls)
    return urls[:count]


def process_image(raw: bytes, max_edge: int) -> bytes:
    """Downscale and re-encode as JPEG.

    Source photos run to several megabytes, which would just move the slowness
    from someone else's CDN onto ours. Everything lands as a right-sized JPEG.
    """
    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue()


def upload(object_key: str, payload: bytes) -> str:
    _client().put_object(
        Bucket=settings.r2_bucket_name,
        Key=object_key,
        Body=payload,
        ContentType=CONTENT_TYPE,
    )
    return public_url(object_key)


async def fetch_process_upload(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    source_url: str,
    object_key: str,
    max_edge: int,
) -> tuple[str, int]:
    """Download -> resize -> put to R2. Returns (public_url, stored_bytes)."""
    async with semaphore:
        resp = await client.get(source_url, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.content

        loop = asyncio.get_running_loop()
        payload = await loop.run_in_executor(None, process_image, raw, max_edge)
        url = await loop.run_in_executor(None, upload, object_key, payload)
        return url, len(payload)


# ── Seeding ───────────────────────────────────────────────────────────────────
def build_rows() -> tuple[list[User], list[PetProfile], list[MatchPreference], dict, dict]:
    """Materialise users and pets with client-side UUIDs, so object keys can be
    built before anything touches the database."""
    users: list[User] = []
    pets: list[PetProfile] = []
    prefs: list[MatchPreference] = []
    user_ids: dict[int, uuid.UUID] = {}
    pet_ids: dict[tuple[int, int], uuid.UUID] = {}

    password_hash = hash_password(SEED_PASSWORD)

    for pi, person in enumerate(PEOPLE):
        area = AREAS[person.area]
        user_id = uuid.uuid4()
        user_ids[pi] = user_id

        users.append(
            User(
                id=user_id,
                email=person.email,
                password_hash=password_hash,
                is_verified=True,
                full_name=person.full_name,
                occupation=person.occupation,
                bio=person.bio,
                address=f"{area.label}, Hyderabad, Telangana",
                pincode=area.pincode,
                latitude=area.lat,
                longitude=area.lng,
                preferred_match_radius_km=person.radius_km,
            )
        )

        prefs.append(
            MatchPreference(
                user_id=user_id,
                preferred_species=None,  # open to everything by default
                preferred_radius_km=person.radius_km,
            )
        )

        for qi, pet in enumerate(person.pets):
            pet_id = uuid.uuid4()
            pet_ids[(pi, qi)] = pet_id
            pets.append(
                PetProfile(
                    id=pet_id,
                    user_id=user_id,
                    name=pet.name,
                    species=SPECIES[pet.species],
                    breed=pet.breed,
                    age_months=pet.age_months,
                    gender=pet.gender,
                    bio=pet.bio,
                    lat=area.lat + _jitter(),
                    lng=area.lng + _jitter(),
                    address=f"{area.label}, Hyderabad",
                    pincode=area.pincode,
                    is_active=True,
                    is_vaccinated=pet.is_vaccinated,
                    vaccination_date=(
                        (datetime.now(timezone.utc) - timedelta(days=RNG.randint(40, 300))).date()
                        if pet.is_vaccinated
                        else None
                    ),
                    is_neutered=pet.is_neutered,
                    is_trained=pet.is_trained,
                )
            )

    return users, pets, prefs, user_ids, pet_ids


async def gather_images(
    user_ids: dict[int, uuid.UUID],
    pet_ids: dict[tuple[int, int], uuid.UUID],
    concurrency: int,
) -> tuple[dict[int, str], dict[tuple[int, int], list[tuple[str, str]]], int]:
    """Returns profile urls by person index, and [(object_key, url)] per pet."""
    semaphore = asyncio.Semaphore(concurrency)
    profile_urls: dict[int, str] = {}
    pet_photos: dict[tuple[int, int], list[tuple[str, str]]] = {}
    total_bytes = 0

    async with httpx.AsyncClient(headers={"User-Agent": "PawSome-Seeder/1.0"}) as client:
        # Resolve every breed's candidate URLs first, one API call per breed,
        # then hand them out so two pets of the same breed never collide.
        log("  resolving breed photo sources…")
        needs: dict[tuple[str, str], int] = {}
        for pi, person in enumerate(PEOPLE):
            for qi, pet in enumerate(person.pets):
                key = (pet.source.kind, pet.source.ref)
                needs[key] = needs.get(key, 0) + pet.photo_count

        pools: dict[tuple[str, str], list[str]] = {}
        for (kind, ref), count in needs.items():
            if kind == "dog":
                pools[(kind, ref)] = await resolve_dog_urls(client, ref, count)
            else:
                pools[(kind, ref)] = await resolve_cat_urls(client, ref, count)
            # Some breeds are thin upstream (dog.ceo has only two dalmatians, for
            # instance). Say so rather than silently handing a pet fewer photos
            # than seed_data.py asked for.
            got = len(pools[(kind, ref)])
            if got < count:
                log(f"    ! {ref}: wanted {count} photos, source only has {got}")

        # Build the full work list up front so everything runs in one wave.
        jobs: list[tuple] = []
        for pi, person in enumerate(PEOPLE):
            jobs.append(
                (
                    "profile",
                    pi,
                    None,
                    f"https://i.pravatar.cc/600?img={person.avatar}",
                    build_user_photo_key(user_ids[pi], CONTENT_TYPE),
                    PROFILE_PHOTO_MAX_EDGE,
                )
            )
            for qi, pet in enumerate(person.pets):
                pool = pools[(pet.source.kind, pet.source.ref)]
                for _ in range(pet.photo_count):
                    if not pool:
                        break
                    jobs.append(
                        (
                            "pet",
                            pi,
                            qi,
                            pool.pop(),
                            build_object_key(pet_ids[(pi, qi)], CONTENT_TYPE),
                            PET_PHOTO_MAX_EDGE,
                        )
                    )

        log(f"  downloading + uploading {len(jobs)} images (concurrency {concurrency})…")

        async def run(job):
            kind, pi, qi, src, key, edge = job
            url, size = await fetch_process_upload(client, semaphore, src, key, edge)
            return kind, pi, qi, key, url, size

        done = 0
        for coro in asyncio.as_completed([run(j) for j in jobs]):
            kind, pi, qi, key, url, size = await coro
            total_bytes += size
            if kind == "profile":
                profile_urls[pi] = url
            else:
                pet_photos.setdefault((pi, qi), []).append((key, url))
            done += 1
            if done % 20 == 0 or done == len(jobs):
                log(f"    {done}/{len(jobs)}")

    return profile_urls, pet_photos, total_bytes


def build_graph(
    pet_ids: dict[tuple[int, int], uuid.UUID],
    user_ids: dict[int, uuid.UUID],
    now: datetime,
):
    """Swipes, matches, notifications, chat threads."""
    swipes: list[Swipe] = []
    matches: list[Match] = []
    notifications: list[Notification] = []
    participants: list[ChatParticipant] = []
    messages: list[Message] = []

    names = {(pi, qi): PEOPLE[pi].pets[qi].name for pi, qi in pet_ids}

    # Mutual likes -> match + both notifications + chat thread
    for offset, (a, b) in enumerate(MATCHES):
        a_id, b_id = pet_ids[a], pet_ids[b]
        matched_at = now - timedelta(hours=6 * (offset + 1))

        swipes.append(Swipe(swiper_pet_id=a_id, target_pet_id=b_id,
                            action=SwipeAction.LIKE, created_at=matched_at - timedelta(minutes=30)))
        swipes.append(Swipe(swiper_pet_id=b_id, target_pet_id=a_id,
                            action=SwipeAction.LIKE, created_at=matched_at))

        pet1_id, pet2_id = sorted([a_id, b_id])
        match = Match(id=uuid.uuid4(), pet1_id=pet1_id, pet2_id=pet2_id, created_at=matched_at)
        matches.append(match)

        is_old = (now - matched_at).total_seconds() / 60 > READ_NOTIFICATION_AGE_MINUTES
        for me, them in ((a, b), (b, a)):
            notifications.append(
                Notification(
                    user_id=user_ids[me[0]],
                    notification_type=NotificationType.NEW_MATCH,
                    pet_id=pet_ids[me],
                    related_pet_id=pet_ids[them],
                    match_id=match.id,
                    message=f"It's a match! {names[me]} and {names[them]} liked each other.",
                    is_read=is_old,
                    read_at=matched_at + timedelta(minutes=5) if is_old else None,
                    created_at=matched_at,
                )
            )

        for ref in (a, b):
            participants.append(
                ChatParticipant(match_id=match.id, pet_id=pet_ids[ref], created_at=matched_at)
            )

        for who, content, minutes_ago in CONVERSATIONS.get((a, b), []):
            sender = a if who == 0 else b
            messages.append(
                Message(
                    match_id=match.id,
                    sender_pet_id=pet_ids[sender],
                    content=content,
                    created_at=now - timedelta(minutes=minutes_ago),
                )
            )

    # One-way likes -> unread, actionable NEW_LIKE notifications
    for offset, (liker, target) in enumerate(PENDING_LIKES + SUPER_LIKES):
        is_super = (liker, target) in SUPER_LIKES
        liked_at = now - timedelta(minutes=25 * (offset + 1))
        swipes.append(
            Swipe(
                swiper_pet_id=pet_ids[liker],
                target_pet_id=pet_ids[target],
                action=SwipeAction.SUPER_LIKE if is_super else SwipeAction.LIKE,
                created_at=liked_at,
            )
        )
        notifications.append(
            Notification(
                user_id=user_ids[target[0]],
                notification_type=NotificationType.NEW_LIKE,
                pet_id=pet_ids[target],
                related_pet_id=pet_ids[liker],
                match_id=None,
                message=(
                    f"🌟 {names[liker]} Super Woofed {names[target]}!"
                    if is_super
                    else f"{names[liker]} is interested in {names[target]}!"
                ),
                is_super=is_super,
                is_read=False,
                created_at=liked_at,
            )
        )

    for offset, (a, b) in enumerate(SKIPS):
        swipes.append(
            Swipe(
                swiper_pet_id=pet_ids[a],
                target_pet_id=pet_ids[b],
                action=SwipeAction.SKIP,
                created_at=now - timedelta(hours=2 * (offset + 1)),
            )
        )

    return swipes, matches, notifications, participants, messages


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-images", action="store_true", help="skip all photo work")
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()

    logging.disable(logging.INFO)
    now = datetime.now(timezone.utc)

    log("")
    log("=" * 72)
    log("  SEEDING PAWSOME")
    log("=" * 72)
    log(f"  database : {settings.app_env}")
    log(f"  bucket   : {settings.r2_bucket_name}")
    log(f"  people   : {len(PEOPLE)}   pets: {sum(len(p.pets) for p in PEOPLE)}")
    log("=" * 72)

    log("\n[1/4] Building users and pets…")
    users, pets, prefs, user_ids, pet_ids = build_rows()
    log(f"  {len(users)} users, {len(pets)} pets")

    profile_urls: dict[int, str] = {}
    pet_photos: dict[tuple[int, int], list[tuple[str, str]]] = {}
    total_bytes = 0
    if args.no_images:
        log("\n[2/4] Images skipped (--no-images)")
    else:
        log("\n[2/4] Photos → R2")
        profile_urls, pet_photos, total_bytes = await gather_images(
            user_ids, pet_ids, args.concurrency
        )
        count = len(profile_urls) + sum(len(v) for v in pet_photos.values())
        log(f"  {count} images stored, {total_bytes / 1_048_576:.1f} MB total")

    for pi, user in enumerate(users):
        user.profile_photo_url = profile_urls.get(pi)

    log("\n[3/4] Relationship graph…")
    swipes, matches, notifications, participants, messages = build_graph(pet_ids, user_ids, now)
    log(
        f"  {len(matches)} matches, {len(swipes)} swipes, "
        f"{len(notifications)} notifications, {len(messages)} messages"
    )

    log("\n[4/4] Writing to database…")
    async with AsyncSessionLocal() as session:
        session.add_all(users)
        await session.flush()
        session.add_all(prefs)
        session.add_all(pets)
        await session.flush()

        photo_rows = []
        for (pi, qi), entries in pet_photos.items():
            for order, (object_key, url) in enumerate(sorted(entries)):
                photo_rows.append(
                    PetPhoto(
                        pet_id=pet_ids[(pi, qi)],
                        object_key=object_key,
                        url=url,
                        is_primary=(order == 0),
                        sort_order=order,
                    )
                )
        session.add_all(photo_rows)

        session.add_all(swipes)
        session.add_all(matches)
        await session.flush()
        session.add_all(notifications)
        session.add_all(participants)
        session.add_all(messages)
        await session.flush()

        # Badges are normally granted by the routes as each action happens, so
        # rows written straight to the database earn nothing — seeded accounts
        # showed "0 of 9 earned" while having photos, pets, matches and messages.
        granted = await sync_achievements(session)

        await session.commit()
        log(f"  committed ({len(photo_rows)} pet photos, {granted} achievements)")

    demo = PEOPLE[0]
    log("\n" + "=" * 72)
    log("  DONE")
    log("=" * 72)
    log(f"  Demo login : {demo.email}  /  {SEED_PASSWORD}")
    log(f"  {demo.full_name} has {len(demo.pets)} pets, the most matches,")
    log("  unread likes to accept and live chat threads.")
    log(f"  All {len(PEOPLE)} accounts share the same password.")
    log("=" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
