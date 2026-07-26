# Handoff — 26 July 2026 (location & enrichment session)

> Replaces the earlier handoff covering the seed-data/chat-performance session. That work is
> committed and pushed-pending; anything from it still relevant is carried into **Gotchas**
> below. Everything else here is new.

---

## Goal

Add a **"Show in map"** option to playdates so that when someone proposes a meetup with a date
and an address, both owners can see the pin on a real map and get directions to it — an address
string that *reads* right can still geocode to the wrong side of the city, and a playdate is a
real-world meetup between people who matched online.

Then, using the APIs.io MCP catalog, find other free APIs that make the app better with the data
we already store, and document the whole thing. Four follow-ons were approved and built: weather
+ air quality on cards, add-to-calendar, nearby dog-park suggestions, and distance to a venue.

The constraint driving nearly every design decision: **free and keyless wherever possible**, and
every enrichment must degrade to nothing rather than break a card.

---

## Current state

### Working and verified

- **Backend:** 3 new endpoints live and passing an end-to-end smoke test (8/8 assertions,
  3 consecutive green runs against real upstreams):
  - `GET /conditions?lat=&lng=&at=` — Open-Meteo weather + US AQI, Redis-cached 30 min
  - `GET /places/nearby?lat=&lng=&radius_m=&kinds=` — Overpass POIs, cached 24 h
  - `GET /travel/eta?from_lat=&from_lng=&to_lat=&to_lng=` — distance, cached 6 h
- **Frontend:** `npm run build` passes (`tsc -b` + vite). Map links, weather/AQI pills,
  add-to-calendar, nearby chips and distance are wired into `PlaydateCard`, `EventCard` and
  `LocationPicker`.
- **Lint:** unchanged at 11 problems (8 errors, 3 warnings). Verified by `git stash` →
  lint → `git stash pop`: the committed tree reports the identical count. **Zero new lint
  issues introduced.** All 11 are pre-existing, in files not touched this session
  (`Chat/index.tsx` calls `Date.now()` during render; some `set-state-in-effect` warnings).

### NOT verified — read this before claiming anything renders

**No UI was ever seen rendered this session.** No browser was opened. Every frontend change was
verified by TypeScript compile + lint + reading only. Specifically unverified:

- Whether the OSM iframe preview actually displays (CSP, X-Frame-Options, ad blockers are all
  plausible failure modes that a build cannot catch)
- Weather/AQI pill layout on a narrow card, and whether `EventCard` now overflows its grid tile
  — several badges were added to a card that was already dense
- Whether the `.ics` download works in-browser and imports with the correct local time
- Whether the nearby-place chips wrap sanely in the propose form
- That distance appears after using "use my current location"

### Half-done / deliberately incomplete

- **Drive-time ETA is not enabled.** `/travel/eta` returns straight-line haversine distance
  (`source: "straight_line"`, `duration_minutes: null`). The Ola Maps code path is written and
  wired but has no key — see Failed attempts. This was an explicit user decision, not an
  oversight.
- **The Ola response parser has never run against a real response.** See Failed attempts.

### Nothing is broken or in a bad intermediate state.

### Uncommitted

**Everything from this session is uncommitted, in both repos.** Nothing was committed or
pushed. See Changes made.

---

## Files in play

### Backend — new

| File | What / why |
|---|---|
| `backend/app/services/external_http.py` | Shared `Throttle` (per-provider rate limiting), `fetch_json`, `UpstreamUnavailable`, `unavailable()`. Extracted so weather/places/travel don't each copy `geocoding.py`'s plumbing |
| `backend/app/services/api_cache.py` | `cached_json(redis, key, ttl, loader, should_cache=None)` and `geo_key()`. Modelled on `block_cache.py` — the repo uses no cache framework |
| `backend/app/api/routes/conditions.py` | Open-Meteo proxy. Horizon guards, nearest-hour pick, concurrent forecast+AQI fetch |
| `backend/app/api/routes/places.py` | Overpass proxy with mirror fallback |
| `backend/app/api/routes/travel.py` | Ola Maps with haversine fallback |
| `backend/app/schemas/{conditions,places,travel}.py` | Flat pydantic models (no `model_config` — external passthrough, matching `schemas/geocoding.py`) |
| `backend/app/tests/test_enrichment_smoke.py` | 8-assertion smoke test. **This is the only test for any of this work** |

### Backend — modified

| File | What / why |
|---|---|
| `backend/app/main.py` | Import + `include_router` for the 3 new routers |
| `backend/app/core/config.py` | `ola_maps_api_key`, `ola_maps_base_url`, `ola_maps_configured` property. Follows the existing R2/Brevo blank-default pattern |
| `backend/.env.example` | Documented Ola block explaining why the key is blank **on purpose** |

### Frontend — new (all in the `frontend/` submodule)

| File | What / why |
|---|---|
| `src/lib/maps.ts` | Google Maps deep-link builders + keyless OSM embed URL + `hasCoordinates` guard |
| `src/lib/calendar.ts` | `.ics` (RFC 5545) builder, Google Calendar URL, `downloadIcs` |
| `src/lib/api/{conditions,places,travel}.ts` | Thin `apiFetch` wrappers |
| `src/hooks/useUserLocation.ts` | Read-only last-known position. **Never triggers a geolocation prompt** — intentional, see Gotchas |
| `src/components/ui/ShowInMap.tsx` | Expandable OSM preview + Maps/Directions links |
| `src/components/ui/Badge.tsx` | The repo's **first** shared badge component |
| `src/components/ui/AddToCalendar.tsx` | Google Calendar link + `.ics` download |
| `src/components/ui/NearbyPlaces.tsx` | Nearby-spot chips |
| `src/components/ui/DistanceBadge.tsx` | "4.2 km away" |
| `src/components/conditions/ConditionsBadge.tsx` | Weather + AQI pills |

### Frontend — modified

| File | What / why |
|---|---|
| `src/lib/api/types.ts` | Appended `Conditions`, `AqiBand`, `NearbyPlace`, `NearbyPlaceList`, `TravelEstimate`, `PlaceKind` |
| `src/components/ui/LocationPicker.tsx` | Added `ShowInMap` + `NearbyPlaces`; calls `rememberUserLocation()` on geolocation success |
| `src/components/chat/PlaydateCard.tsx` | `ShowInMap` always; `ConditionsBadge` when upcoming; `AddToCalendar` when accepted + future |
| `src/components/events/EventCard.tsx` | `ShowInMap`, `DistanceBadge`, `ConditionsBadge` when upcoming, `AddToCalendar` when going + upcoming |

### Docs

| File | What / why |
|---|---|
| `docs/LOCATION_AND_MAPS.md` | **New, ~400 lines.** The main artefact: location stack, endpoint reference, full API research, why-no-Google-SDK, why-no-Ola-key, constraints |
| `docs/DOCUMENTATION_MAP.md` | Added a row + tree entry for the above |
| `handoff.md` | This file (replaced the previous session's) |

### Not mine — pre-existing, unstaged

`git status` shows ` D API_TEST_REPORT.md`, ` D DOCUMENTATION_MAP.md`, ` D INTEGRATION_SUMMARY.md`
at the repo root with matching `?? docs/` copies. **That move predates this session** — it was in
the git status snapshot at session start. Don't attribute it here; decide separately whether to
commit it.

---

## Changes made

Chronological. **None of this is committed.**

1. Explored the playdate feature. Found `playdates` and `events` tables already store
   `latitude`, `longitude`, `address`, `pincode` — **no migration was needed for any of this
   work**, and none was written.
2. Created `frontend/src/lib/maps.ts` + `ShowInMap.tsx`; wired into `PlaydateCard`, `EventCard`,
   `LocationPicker`. Type-checked clean.
3. Researched APIs via the APIs.io MCP server (see Failed attempts for query pitfalls).
   Wrote `docs/LOCATION_AND_MAPS.md`.
4. Planned phases 1–4 with the user. **Two decisions made by the user:** Ola Maps for real drive
   ETA (over haversine-only), and build all four phases together. Plan saved at
   `C:\Users\Mani Mamidala\.claude\plans\wiggly-humming-rain.md`.
5. Built `external_http.py` + `api_cache.py`.
6. Built `/conditions`, then added `should_cache` to `cached_json` after realising a
   double-upstream-failure would be cached as an empty result for the full 30-min TTL.
7. Built `/places/nearby` and `/travel/eta`; added Ola settings to `config.py`; registered all
   three routers.
8. Verified registration: `uv run python -c "from app.main import app; ..."` printed
   `/conditions`, `/places/nearby`, `/travel/eta`.
9. Built the frontend API modules, types, `Badge`, and the four feature components; wired them
   into the three surfaces.
10. `npm run build` — pass. `npm run lint` — 11 problems; confirmed identical on the stashed
    (committed) tree, so none are new.
11. Wrote `app/tests/test_enrichment_smoke.py`. **First run failed** on Overpass (see Failed
    attempts) → added a mirror-instance fallback → green on 3 consecutive runs after.
12. Updated `docs/LOCATION_AND_MAPS.md` from "proposed" to shipped; added the endpoint
    reference and verification section.
13. Added a documented Ola block to `backend/.env.example`.
14. User hit the Ola credit-card wall (see Failed attempts). **User decided to stay on
    straight-line distance.** Corrected the "no credit card required" claim in
    `.env.example` and in 5 places in `docs/LOCATION_AND_MAPS.md`.
15. Final smoke run: 8/8 green.

**No dependencies were added** to `pyproject.toml` or `package.json`. Everything uses libraries
already present (`httpx`, `redis`, `@tanstack/react-query`, `framer-motion`, `lucide-react`).

**No schema/migration changes. No env vars are required** — `OLA_MAPS_API_KEY` is optional and
intentionally unset.

---

## Failed attempts / dead ends

### 1. Ola Maps requires a credit card — the marketing page is wrong

The biggest dead end. Their site says *"No credit card required"* and *"Setup in under 5
minutes"*, and I repeated that to the user. **It is not true.** Krutrim Cloud → Ola Maps →
Offerings → **Credentials** opens a blocking modal:

> **Setup Autopay** — Required to create and use credentials
> To create API credentials, you need to register a credit card for automatic billing.
> A ₹1 authorization charge will be made to verify your card

**Do not send the user back to Ola expecting a free key.** The user declined the card and chose
to stay on straight-line distance. This is recorded in `docs/LOCATION_AND_MAPS.md` §4.5 and in
`backend/.env.example`.

Alternatives investigated, none adopted:
- **OpenRouteService** — `openrouteservice.org/plans/` 301-redirects to
  `account.heigit.org/info/plans`, which is JS-rendered and returned no usable content via
  WebFetch. Current terms **unverified**; may have the same card requirement.
- **OSRM public demo** (`router.project-osrm.org`) — no key, no signup, but it is explicitly a
  *demo* server and the project asks people not to run production traffic on it.

### 2. Overpass fails intermittently — roughly one run in two

First smoke run died with:

```
AssertionError: {"detail":"Nearby place search is temporarily unavailable"}
```

The query itself was fine — probing `https://overpass-api.de/api/interpreter` directly returned
200 with real data. Overpass is volunteer-run and sheds load with 429/504 rather than queueing.
**Fix applied:** `places.py` now tries `overpass-api.de` then `overpass.kumi.systems` before
giving up, and the client timeout went 30 s → 40 s. Green on 3 runs since, but **if you see this
error again it is upstream, not your code.**

### 3. APIs.io: `sort=composite` silently discards relevance

`find_providers(q="maps geocoding places routing", sort="composite")` returned **Stripe,
HubSpot, Datadog, Zapier** — the sort replaces relevance ranking entirely rather than ordering
within it. Tag filtering (`tags=["maps","geocoding",...]`) is also noisy — it surfaced Salesforce
and ServiceNow as top "maps" providers.

**What works:** `apis_io_search(q=...)` with default sort, or `find_providers` with
`public=true` / `try_now=true` filters and no sort override.

### 4. Ola's API reference is unreadable, so the parser is untested

`maps.olakrutrim.com/docs/routing/distance-matrix` → **HTTP 404**. `/docs` renders a JS shell
with no endpoint detail. So `_parse_ola()` in `travel.py` is written against the *documented
Google-compatible* Distance Matrix shape and **has never run against a real response.** It
accepts both `{"distance": {"value": n}}` and `{"distance": n}`, and returns `None` on anything
unrecognised → falls back to haversine. If a key is ever added and `source` stays
`straight_line`, this is the first thing to check.

### 5. PowerShell here-strings mangle quotes in inline tool calls

Passing `@'...'@` with embedded Python to the PowerShell tool stripped the double quotes:

```
File "<string>", line 5
    print(QUERY:, q)
               ^
SyntaxError: invalid syntax
```

**Write the script to the scratchpad directory and run the file instead.** (The previous session
hit the same class of bug with a stray `@` in a commit message.)

### 6. The smoke test needs `PYTHONPATH`

Plain `uv run python app/tests/test_enrichment_smoke.py` gives
`ModuleNotFoundError: No module named 'app'`. Set `PYTHONPATH` to the backend dir — see Gotchas.

### 7. `/apis-io-mcp-server:find_api` is not callable by the assistant

The user asked me to use it twice. MCP *prompts* surface as slash commands only the user can
type. Use the server's **tools** (`apis_io_search`, `find_apis`, `find_providers`, `get_api`)
instead.

### 8. There are no pet-domain APIs

Searching the APIs.io catalog (1,700+ mapping APIs, 1,683 providers) for dog/cat/breed data
returned **one** hit: a Swedish insurtech with no public API. Don't go looking again — breed data
should be treated as PawSome's own seeded data.

---

## Next steps

### Immediate

1. **Look at the UI.** This is the top priority and the biggest gap — nothing was seen rendered.
   Start the servers (see Gotchas), then check, in order:
   - Open a chat → Playdates → does the OSM iframe in "Show in map" actually load?
   - The Events grid — several badges were added to an already-dense card; check for overflow
     and wrapping at a narrow viewport.
   - Propose a playdate → "use my current location" → do nearby chips appear and fill the form?
   - Reload Events → distance should now appear, with **no geolocation prompt**.
   - Accept a playdate → download the `.ics` → does it import at the right local time?

2. **Commit.** Nothing from this session is committed. **Submodule first, then parent**, or the
   gitlink will dangle:
   ```bash
   cd /d/PawSome/frontend
   git add -A && git commit -m "Add map links, weather, calendar export, nearby spots to cards"
   cd /d/PawSome
   git add backend docs handoff.md
   git commit -m "Add location enrichment endpoints: conditions, places, travel"
   ```
   Decide separately what to do with the three pre-existing root `.md` deletions — they are not
   part of this work.

### Backlog

3. **Push.** Parent is **20 commits ahead** of `origin/main` and the submodule **1**, all from
   *previous* sessions — nothing has been pushed in a long time. Push submodule first.
4. Consider a batch `/conditions` endpoint if a chat with many playdates feels slow. Currently
   one request per distinct (park, hour); react-query dedupes identical keys and the backend
   caches, so this may never be needed — measure before building.
5. Consider swapping address autocomplete from Nominatim to a provider with better Indian
   address quality. Deliberately excluded from this session: it changes a working, load-bearing
   path (Nominatim's 1 req/s throttle is carefully tuned) and deserves its own change.
6. Consider storing the venue's IANA timezone at write time (`docs/LOCATION_AND_MAPS.md` §4.3).
   Only matters once PawSome crosses a timezone boundary, but it is far cheaper to add at write
   time than to backfill.

### Open questions

- **None blocking.** The one decision point (Ola card) was resolved: the user declined, and
  straight-line distance is the accepted end state. Don't reopen it unprompted.

---

## Gotchas

### Running things

```bash
# Backend (needs Neon Postgres + Upstash Redis reachable)
cd /d/PawSome/backend && uv run uvicorn app.main:app --reload

# Frontend
cd /d/PawSome/frontend && npm run dev

# The smoke test — PYTHONPATH is REQUIRED
cd /d/PawSome/backend
PYTHONPATH=. uv run python app/tests/test_enrichment_smoke.py
# PowerShell: $env:PYTHONPATH="D:\PawSome\backend"; uv run python app/tests/test_enrichment_smoke.py

cd /d/PawSome/frontend && npm run build && npm run lint
```

The smoke test hits **real** Open-Meteo and Overpass and needs Redis + the DB. It is not
hermetic and it is not fast (~30 s).

### Testing reality in this repo

- **There is no frontend test framework at all.** No vitest, no jest, no `test` script.
- **The backend pytest suite does not run.** `app/tests/test_matching_system.py` references
  `db`/`client` fixtures, there is no `conftest.py` anywhere, and `pytest` is not in
  `pyproject.toml`. The working pattern is standalone `httpx.ASGITransport` scripts run via
  `uv run python` — which is what `test_enrichment_smoke.py` is.

### Things that look wrong but are intentional

- **No `/api/v1` prefix.** Routers mount at the app root, each carrying its own prefix.
- **`useUserLocation` never asks for permission.** It only *reads* a position stored by
  `LocationPicker`'s existing "use my current location" button. Distance therefore doesn't appear
  until the user has volunteered their location once. Deliberate — a permission prompt fired
  because a card scrolled into view is hostile. **Do not "fix" this by calling
  `navigator.geolocation` in the badge.**
- **`ConditionsBadge` and `DistanceBadge` render `null` while loading and on error.** No
  skeleton, no error text. They are decorative; a weather outage must be invisible.
- **`geocoding.py` was left alone** and still has its own local copy of the throttle/HTTP
  plumbing rather than using `external_http.py`. It works, it's tuned for Nominatim's 1 req/s
  policy, and its client-disconnect check exists for a real reason (abandoned autocomplete
  keystrokes were eating the whole per-second budget).
- **Map links use coordinates, never the address string.** Passing the address would let Google
  re-geocode it to a different pin than the one the user picked.
- **`cached_json` takes a `should_cache` predicate.** Loaders here degrade rather than raise, so
  without it a single upstream blip gets cached as an empty result for the whole TTL.
- **Weather horizon is 16 days, AQI is 7.** Both checked *before* any network call. A card
  10 days out legitimately shows temperature with `us_aqi: null`.
- **`/conditions` and `/travel/eta` use optional auth**; `/places/nearby` requires it. Events are
  browsable signed out, so their cards must work anonymously.

### Carried over from the previous session (still true)

- **Seeded accounts** use password `123456789`; `arjun.reddy@example.com` is the demo account
  (3 pets, 6 matches, live chats). 25 users across real Hyderabad localities — which is why the
  smoke test uses KBR Park (17.4239, 78.4138) as its fixture: real coordinates with real parks
  nearby for Overpass to find.
- **`frontend` is a gitlink with no `.gitmodules` entry**, so `git submodule status` errors.
  Pre-existing. Commit inside `frontend/` directly.
- **Use `127.0.0.1`, not `localhost`,** in dev config. `localhost` resolves to `::1` first, the
  backend binds IPv4 only, and Windows takes ~2 s to refuse the IPv6 attempt.
- **11 pre-existing lint problems.** Don't chase them thinking this session caused them.

### Windows specifics

- `Bash` tool is Git Bash; `PowerShell` tool is Windows PowerShell 5.1 (no `&&`, no ternary).
- vite's chunk-size warning gets wrapped by PowerShell as a `NativeCommandError` — the build
  still succeeded. Check for `✓ built in`.
- Scratch scripts belong in the session scratchpad, not `/tmp`.
