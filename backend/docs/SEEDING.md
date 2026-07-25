# Resetting and seeding an environment

Two scripts in `backend/scripts/` take an environment from whatever state it is
in to a clean, fully populated one.

Everything they create lives in **our own R2 bucket**. No image in the database
points at a third-party host — hotlinking Unsplash and other CDNs was what made
pet cards slow to paint, because every card waited on a round trip to someone
else's server before it could show anything.

## 1. Wipe

```bash
cd backend
uv run python scripts/reset_environment.py            # dry run, prints counts
uv run python scripts/reset_environment.py --yes      # actually wipe
```

Deletes every row of application data and every object in the R2 bucket.
`alembic_version` is preserved so the schema stays at its current revision.

It prints the database host and bucket name before doing anything, and refuses
to act without `--yes`. Flags: `--keep-db`, `--keep-bucket`.

## 2. Seed

```bash
uv run --with pillow python scripts/seed_realistic_data.py
```

Pillow is only needed for this script, so it is pulled in for the run rather
than added to the app's dependencies.

Creates 25 users across real Hyderabad localities (Boduppal, Habsiguda, Jubilee
Hills, Vanasthalipuram, Madhapur, Gachibowli and more), with real coordinates so
distance-based matching returns believable numbers. Between them they have 29
pets, ~100 photos, 12 matches, pending likes, Super Woofs, skips, and chat
threads.

**Every account uses the password `123456789`.** Nine characters, so it also
clears the 8-char minimum the registration endpoint enforces.

Sign in as **`arjun.reddy@example.com`** to see the fullest state: three pets,
six matches, unread likes waiting to be accepted, and live chat threads.

Emails deliberately use `@example.com` (RFC 2606 reserved). The app sends
verification and password-reset mail, and pointing seed accounts at plausible
gmail.com addresses would mean mailing strangers.

Flags: `--no-images` (fast structural test, no photo work), `--concurrency N`.

### Where the photos come from

Fetched once at seed time, downscaled, re-encoded as JPEG, and uploaded to R2:

| Subject | Source | Why |
| --- | --- | --- |
| Dogs | dog.ceo, by breed | A beagle actually looks like a beagle |
| Cats | TheCatAPI, by breed id | Same, for the eight cat breeds used |
| Faces | i.pravatar.cc, fixed id per person | Stable across runs |

Some breeds are thin upstream — dog.ceo carries only two dalmatian photos, for
example. The script warns when a breed can't cover what `seed_data.py` asked for
rather than failing or silently under-filling.

## 3. Site imagery

The landing and auth pages had their own hardcoded Unsplash URLs, separate from
the database. Those are handled once by:

```bash
uv run --with pillow python scripts/upload_site_images.py
```

It stores them under `site/` in the bucket and prints the exact contents of
`frontend/src/lib/siteImages.ts`, which is the single place those URLs live.
Only re-run this if the images change or the bucket moves.

## Editing the cast

`scripts/seed_data.py` holds all the people, pets, conversations and the
relationship graph as plain data — no logic. Add or change entries there; the
pipeline in `seed_realistic_data.py` does not need touching.

The relationship graph (`MATCHES`, `PENDING_LIKES`, `SUPER_LIKES`, `SKIPS`,
`CONVERSATIONS`) is written out explicitly rather than randomised, so every run
produces the same demo state.
