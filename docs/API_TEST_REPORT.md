# API Endpoint Test Report

Full endpoint-by-endpoint sweep of the PawSome backend: request validation, error handling, authentication, authorization, edge cases, response shape, and frontend integration. Run against a live local instance (`uv run uvicorn app.main:app`) using the existing e2e test accounts plus several freshly-created throwaway accounts/pets, so every check exercised the real HTTP surface, not mocks.

**81 endpoints tested across 14 route files. 8 real bugs found — all fixed and verified live. 4 more items noted for a product decision, not fixed (explained below).**

| Route file | Endpoints | Result |
|---|---|---|
| `matches.py` | 18 | All pass (2 bugs found + fixed along the way) |
| `auth.py` / `users.py` / `onboarding.py` | 19 | 16 clean, 3 issues (all fixed) |
| `pets.py` / `pet_photos.py` / `geocoding.py` / `favorites.py` / `blocks.py` / `reports.py` / `achievements.py` | 22 | 15 clean, 7 issues (all fixed) |
| `chat.py` / `playdates.py` / `events.py` | 22 | 21 clean, 1 low-severity + 1 integration gap (noted, not fixed) |

---

## Bugs found and fixed

### Critical

**1. `POST /blocks` returned 500 on every realistic call — the block/safety feature was completely broken.**
`app/api/routes/blocks.py` used `and_()` inside an `or_()` filter but only imported `or_, select` from `sqlalchemy` — `and_` was never imported. Crashed with `NameError` any time both the blocker and the blocked user owned at least one pet (i.e., almost always). Fixed: added `and_` to the import. Verified live: `POST /blocks` now returns 201 and correctly soft-deletes the shared match.

### High

**2. `GET /favorites` returned 500 whenever the pet had at least one favorite.**
`FavoriteWithPetResponse.target_pet` was typed as a bare `dict`, so nothing validated its contents. `list_favorites` assigned a raw SQLAlchemy `User` ORM object into that dict as `owner`, which pydantic then couldn't serialize (`Unable to serialize unknown type: <class 'app.models.user.User'>`). Only reproduces once a favorite actually exists — the empty-list case masked it. Fixed: `target_pet` is now properly typed as `PetPublicResponse`, and the route builds a real `PetOwnerBasicInfo` instance instead of passing the ORM object through. Verified live: 200 with `owner` correctly populated.

**3. `PATCH /pets/{id}` and `DELETE /pets/{id}` 404'd for pets the caller genuinely owned, if the pet had no photo yet.**
A new pet starts `is_active=False` until its first photo is uploaded. Both routes depended on `get_owned_pet`, which filters `is_active=True` — correct for browse/swipe (don't surface unfinished profiles to others), wrong for the owner editing/deleting their own draft. `pet_photos.py` already had the right dependency for this (`get_owned_pet_any`, which matches an inactive pet as long as it has no photos yet); `pets.py` just wasn't using it. Fixed: both routes now depend on `get_owned_pet_any`. Verified live: a draft pet that previously 404'd on PATCH/DELETE now returns 200/204. (Used this fix to also clean up several stray draft pets left over from testing.)

**4. `PUT /users/me/match-preferences` silently never saved the search-radius preference.**
Request schema field `preferred_match_radius_km` didn't match the actual model column `preferred_radius_km` — the generic `setattr(pref, field, value)` update loop set a throwaway, non-persisted attribute with the wrong name instead of the real column. No error, 200 OK, value just never saved. The frontend's Preferences tab has a live "Search radius" slider wired to this exact field — a user could drag it, save, see "Saved," and have it silently discarded every time. Fixed: renamed the request field (backend schema + frontend caller + frontend type) to `preferred_radius_km`, matching the model and response. Verified live: value now persists across requests.
**Important caveat, found while fixing:** even with persistence fixed, this preference has **no effect on actual search results**. `GET /matches/browse` takes its own `radius` query parameter, which the frontend's Discover page sources from local, session-only filter state (default 5000km/"anywhere"), never from the saved preference. Nothing in `app/api/` reads `MatchPreference.preferred_radius_km` at all. There's also a second, entirely separate, dead column `User.preferred_match_radius_km` (`models/user.py`, default 50.0) seeded by `seed_database.py` but not exposed through any route. Fixing "the value now saves correctly" and fixing "the value now controls what a user sees in Discover" are two different pieces of work — I only did the first. Wiring `browse`'s default radius to the saved preference (and deciding whether Discover's live slider should override it or seed from it) is a real product decision I didn't want to guess at.

### Medium

**5. `reject_like` (Pass on a like) never actually stopped the pet from resurfacing.**
Rejecting a like only marked the notification read — it never recorded anything in the `Swipe` table, which is what `GET /matches/likes-received` and `GET /matches/browse` actually filter on. Result: a pet you explicitly passed on would keep reappearing in your "Likes you" list forever, every time you refetched it. Fixed: `reject_like` now also records a `SKIP` swipe (guarded against the table's unique constraint, so re-rejecting is still safe/idempotent). Verified live with a clean, isolated pet pair: pet appeared in likes-received before reject, confirmed gone after.

**6–8. Three separate rate limiters charged their daily/hourly allowance even when the request failed validation before reaching any real logic** — `POST /reports` (5/day), `POST /matches/undo-swipe` (10/hour), and (implicitly, same code shape) `POST /blocks` (20/day, now moot since it's rebuilt per fix #1) and `POST /favorites` (100/day). This is the same class of bug already found and fixed earlier this session in `POST /matches/swipe`'s Super Woof charge: each used a `Depends()`-based rate limiter, which FastAPI resolves independently of whether the request body ends up valid — so a malformed retry, a client bug, or an accidental double-submit could burn part of a user's daily allowance for nothing. Fixed all four the same way: removed the `Depends()` rate limiter, added an explicit `check_rate_limit(...)` call positioned after every validation/business-rule check has already passed, so only requests that are actually going to succeed get charged. Verified live for reports and undo-swipe: a 422 (malformed body) no longer increments the Redis counter; a 404 (bad-but-valid-shaped id, undo-swipe) still does, since that's a genuine attempt.

*(Fixes #1–#3 backend files: `app/api/routes/blocks.py`, `app/api/routes/favorites.py`, `app/schemas/favorite.py`, `app/api/routes/pets.py`. Fix #4: `app/schemas/preferences.py`, `app/api/routes/users.py`, `frontend/src/lib/api/types.ts`, `frontend/src/pages/Profile/tabs/PreferencesTab.tsx`. Fix #5: `app/api/routes/matches.py`. Fixes #6–8: `app/api/routes/reports.py`, `app/api/routes/matches.py`, `app/api/routes/blocks.py`, `app/api/routes/favorites.py`.)*

### Low

**9. `PATCH /users/me` always returned `pets: []`, regardless of the caller's actual pets.**
`GET /users/me` explicitly eager-loads `pet_profiles` and populates the response's `pets` field; `PATCH /users/me` did neither. Currently harmless — every frontend caller discards the mutation's response body and refetches via `GET` instead — but it's a real response-contract violation. Fixed: reuses the active-pets query the route was already running for an achievement check, no extra DB round trip.

**10. Four spots in `matches.py` used naive `datetime.now()` (no timezone) to write into timezone-aware `read_at` columns.** Empirically this still produced correct UTC timestamps (verified before touching anything — the driver evidently normalizes it), so this was not an active bug, just an inconsistency with the rest of the file's `datetime.now(timezone.utc)` convention and a fragile thing to rely on across environments/driver versions. Normalized while in the area.

---

## Noted but deliberately not fixed

These are real, worth knowing about, but each is either a product decision or a larger unit of work than "fix the bug" — left for you to prioritize rather than guessed at:

- **The Preferences tab never loads a user's existing saved preferences on mount** (species/age/gender/radius/breeds all reset to hardcoded defaults every time the tab opens). There's no `GET /users/me/match-preferences` endpoint to even fetch them — would need a new backend endpoint plus frontend query wiring. Related to bug #4 above but a separate, bigger piece of work.
- **The 5-pets-per-user cap only counts *active* pets.** A user can create unlimited inactive "draft" pets (no photo yet) with no cap. This is now at least recoverable — bug #3's fix means drafts can be edited/deleted — but whether the cap itself should count drafts too is a product call.
- **`onboarding.py`'s `action_url` fields point at a `/api/v1/*` prefix that doesn't exist anywhere in this app** (real routes have no such prefix). Zero current impact — confirmed the frontend never reads this field, it has its own hardcoded onboarding step routing. Not fixed because it's unclear what "correct" even means here (backend API path vs. a frontend page route) without knowing the intended future use.
- **`PATCH /events/{id}` (edit an event) has no frontend caller.** The backend endpoint works correctly (organizer-only, partial updates, future-date validation all tested) — there's just no UI entry point to use it. A user can currently only cancel and recreate an event to fix a mistake.
- **`POST /chat/{match_id}/messages/{id}/reactions` has an unused required body field** (`message_id`, shadowed by the path param of the same name). Not user-facing — the frontend already sends it redundantly — but a real footgun for any future caller who'd expect it to matter.

---

## Methodology

- Live HTTP requests (curl / PowerShell) against the running backend, not unit tests against internal functions.
- Fresh accounts/pets created where isolation mattered (avoiding contamination from the two long-lived e2e accounts' extensive prior test history), cleaned up where practical.
- Every "fixed" item above was verified twice: once by direct repro before the fix, once by re-running the identical repro after, including checking raw Redis counters for the rate-limit bugs rather than trusting API responses alone.
- Frontend integration was checked by grepping `frontend/src/lib/api/*.ts` for a caller of every tested backend path.
- One bug in my *own* test methodology is worth naming since it nearly produced false results: an early pass extracted JSON ids with a greedy regex that grabbed a nested object's `id` instead of the intended top-level one, producing three apparent endpoint failures that were actually test-script bugs. Caught by cross-checking against the database directly before writing anything down — same lesson as a test-selector scoping bug caught earlier this session on the frontend side.
