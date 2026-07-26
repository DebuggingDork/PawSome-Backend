# Handoff — 26 July 2026

## Goal

**Project:** PawSome — a pet matching platform (FastAPI + Neon Postgres backend, React 19 +
Vite + Tailwind v4 frontend, Cloudflare R2 for photos, Upstash Redis for pub/sub).
Owners create pet profiles, swipe to match, chat, and arrange real-world playdates.

**This session:** wipe all test data and rebuild it as realistic Hyderabad-based seed data
with every image served from our own R2 bucket, then fix the pile of UI and performance
bugs that surfaced while exercising the app against that data.

## What I Completed

### Data / seeding (the main task)

- **Emptied the environment.** 374 rows across 17 tables and all 34 R2 objects deleted.
- **Rebuilt from scratch:** 25 users across real Hyderabad localities (Boduppal, Habsiguda,
  Jubilee Hills, Vanasthalipuram, Madhapur, Gachibowli, Kondapur, Kukatpally, Banjara Hills,
  Begumpet, Uppal, Secunderabad, Miyapur, Ameerpet, LB Nagar, Nallagandla, Manikonda,
  Tarnaka, Alwal, Sainikpuri, Nizampet) with real coordinates, so distance matching returns
  believable numbers. 29 pets, 100 pet photos, 25 profile photos, 12 matches, 38 swipes,
  33 notifications, 20 chat messages, 24 chat participants, 177 achievements.
- **All images live in R2.** 125 images fetched once at seed time, downscaled, re-encoded as
  JPEG, uploaded — 8.2 MB total, ~67 KB each. Nothing in the database points at a
  third-party host any more.
- **Breed-accurate photos:** dogs from dog.ceo by breed, cats from TheCatAPI by breed id,
  faces from pravatar with a fixed id per person so runs are reproducible.
- **Removed the last Unsplash hotlinks from the frontend** (landing hero, three article
  cards, featured tiles, auth background): 2.7 MB of full-resolution originals per visit,
  now 0.6 MB from R2.

### Bugs fixed

| Bug | Root cause |
| --- | --- |
| Splash screen on **every** reload | No delay threshold; reveal blocked on two API calls; splash logo was an 842 KB PNG; fonts render-blocking |
| Back after login returned to the sign-in form | `navigate()` without `replace`, and no guard on `/auth` |
| Account tab showed a populated profile as blank | `useState(profile?.x ?? '')` ran while the query was still loading; useState ignores changed initial args |
| Navbar showed "A" instead of the photo | Navbar read the profile under `['my-profile']`; everything else uses `['users','me']`, so photo changes never invalidated it |
| Uploader always showed "upload a photo" | `PhotoUploader` could only preview a locally picked file, never a saved one |
| Typing an address → "trouble connecting" | `AbortError` from our own cancelled requests counted as a network failure; 2 keystrokes tripped the threshold |
| Modal panels wouldn't wheel-scroll | Four containers missing `lenis-prevent-scroll`, so Lenis swallowed the wheel |
| Badges stuck at 0 of 9 | Achievements are granted by routes at action time; seeded rows never triggered them |
| Notification dropdown controls dead | `NotificationBell` is mounted twice sharing one open flag; each copy saw the other's clicks as "outside" and closed on mousedown |
| Playdate calendar icon invisible | Native date inputs paint chrome from the OS colour scheme; needed `color-scheme: dark` |
| Chat stuck on "Connecting…" ~2.5 s | Three causes — see Decisions |
| Chat messages saved but never delivered | Broadcast went out via Redis pub/sub only; unhealthy subscription meant nothing arrived |

### Measured improvements

| | Before | After |
| --- | --- | --- |
| WebSocket handshake | 2.50 s | 0.06 s |
| Chat message delivery | never arrived | 0.16 s |
| Sustained typing | — | 0.63 s/msg |
| Shell images per page load | ~1.67 MB | 47 KB |
| Landing/auth imagery | 2.7 MB | 0.6 MB |

## Current State

### Working

- All 25 seeded accounts log in with password `123456789`.
- `arjun.reddy@example.com` is the demo account: 3 pets, 6 matches, unread likes to accept,
  live chat threads, 9/9 badges.
- Verified through the real API: login, `/users/me`, `/pets/me`, `/matches/my-matches`,
  `/matches/notifications`, `/matches/likes-received`, `/matches/browse`, `/chat/{id}/history`,
  `/achievements/me`, `/geocoding/search`.
- All 125 image URLs return 200; no nulls.
- Chat WebSocket: handshake 0.06 s, bidirectional delivery confirmed, bad tokens rejected at
  the handshake, unauthorised matches closed with 1008.
- Frontend builds clean; ESLint clean on every file touched.

### Broken / unverified

- **Nothing known broken.** But see the caveat below.
- **No visual verification was possible this whole session.** The Claude-in-Chrome extension
  never connected, so every UI change was verified by build + lint + reading only. The
  following were never seen rendered: the redesigned splash, the loading overlay's caption
  spacing (the `-mt-6` pull-up is tuned from a screenshot, not measured against the real
  Lottie), the profile identity header, the notifications header at your window width, and
  the playdate form.
- Pre-existing ESLint errors remain in files I didn't touch (`Chat/index.tsx` calls
  `Date.now()` during render; a few `set-state-in-effect` warnings). Not introduced here.
- `Mowgli` has 2 photos instead of 4 — dog.ceo only carries two dalmatian images upstream.
  The seeder warns when a breed can't cover what's asked.

### Blockers for the next session

1. **The Vite dev server is not running and must be restarted** before any of the frontend
   work is visible. Vite reads `.env` only at startup, and `.env` now points at `127.0.0.1`.
   Until restarted, the app still hits `localhost` and still pays the 2 s per-connection tax.
2. I restarted the backend myself mid-session (it had died — port 8000 stopped responding and
   the process was gone). It is running under `uvicorn --reload`, logging to
   `backend/_devserver.log`.

## Files Changed

### Backend (tracked directly in the parent repo)

| File | Change |
| --- | --- |
| `backend/scripts/reset_environment.py` | **New.** Wipes all DB rows + all R2 objects; dry-run by default, requires `--yes`, preserves `alembic_version` |
| `backend/scripts/seed_data.py` | **New.** The cast as pure data — 25 people, 29 pets, localities, match graph, conversations |
| `backend/scripts/seed_realistic_data.py` | **New.** Seeding pipeline: resolves breed photos, downloads, resizes, uploads to R2, writes all rows |
| `backend/scripts/backfill_achievements.py` | **New.** Derives badges from DB state; reusable standalone or from the seeder |
| `backend/scripts/upload_site_images.py` | **New.** One-off: moves the frontend's Unsplash imagery into R2, prints `siteImages.ts` |
| `backend/docs/SEEDING.md` | **New.** Documents the reset → seed → site-images workflow |
| `backend/app/api/routes/chat.py` | Accept the WebSocket before the DB/Redis setup; broadcast right after commit; cache pets per connection; merge two commits into one |
| `backend/app/api/routes/matches.py` | Accept the notifications WebSocket before the user lookup and Redis handshake |
| `backend/app/api/routes/geocoding.py` | Drop searches whose client has disconnected instead of queueing them behind the 1 req/s throttle |
| `backend/app/services/chat_manager.py` | Deliver to local sockets first, then publish; `INSTANCE_ID` so the listener skips its own echo; no longer calls `accept()` |
| `backend/app/services/notification_manager.py` | No longer calls `accept()` — the caller owns it |
| `backend/seed_database.py` | **Deleted.** Superseded; stored Unsplash URLs in the DB |
| `backend/clear_and_seed.py` | **Deleted.** Superseded |
| `backend/docs/SEEDING_README.md` | **Deleted.** Described the old San Francisco dataset |
| `backend/docs/QUICK_START_SEEDED_DATA.md` | **Deleted.** Same |

### Frontend (git submodule at `frontend/`)

| File | Change |
| --- | --- |
| `index.html` | Splash redesigned as inline SVG, held invisible 450 ms, non-blocking fonts, crossfade dismissal |
| `src/hooks/useSmoothScroll.ts` | Fade-out instead of `display:none`; 2.5 s cap so a slow backend can't pin the splash |
| `src/App.tsx` | `GuestOnlyRoute` on `/auth`; stable nav during hydration; unified profile query key; smaller logo import |
| `src/pages/Auth/index.tsx` | `navigate(..., { replace: true })` after login; R2 background image; smaller logo |
| `src/pages/Profile/index.tsx` | **New** identity header — photo, name, verified badge, occupation, address, pincode, bio |
| `src/pages/Profile/tabs/AccountTab.tsx` | Form split into `AccountForm`, mounted only once the query resolves |
| `src/components/ui/PhotoUploader.tsx` | New `currentPhotoUrl` prop; always-visible "Change photo" affordance |
| `src/components/ui/GlobalLoader.tsx` | Rewritten: blurred backdrop, tightened caption, rotating copy, bouncing ellipsis, progress rail |
| `src/components/chat/PetAvatar.tsx` | Image-failure flag now tracks *which* URL failed instead of latching forever |
| `src/components/chat/PlaydatePanel.tsx` | `color-scheme: dark` field, quick time slots, readable echo of the chosen time, `min` = now |
| `src/components/notifications/NotificationBell.tsx` | `data-notifications-root` so both copies share one notion of "inside"; header relaid out |
| `src/hooks/useOnClickOutside.ts` | Optional `ignoreSelector` for components mounted more than once |
| `src/lib/api/client.ts` | Aborts no longer count as connectivity failures; defaults point at `127.0.0.1` |
| `src/lib/siteImages.ts` | **New.** Single home for the R2 URLs of landing/auth imagery |
| `src/index.css` | Loader keyframes, `.datetime-field`, much subtler scrollbar |
| `src/assets/logo-256.png` | **New.** 47 KB, replacing an 828 KB original used at 40 px |
| `src/components/community/PetCardDialog.tsx` | `lenis-prevent-scroll` + `overscroll-contain` |
| `src/components/events/CreateEventModal.tsx` | Same |
| `src/components/ui/LocationPicker.tsx` | Same |
| `src/pages/Landing/sections/*.tsx` (5 files) | Point at `siteImages` instead of Unsplash |
| `.env.example` | Documents why `127.0.0.1` beats `localhost` here |
| `.env` | **Not committed (gitignored).** I edited your local copy to use `127.0.0.1` |

## Decisions Made

- **Images are re-hosted, not hotlinked.** Sources (dog.ceo, TheCatAPI, pravatar, Unsplash)
  are used once at seed time only. The database and frontend store R2 URLs exclusively.
- **Seed data is separated from the seeding pipeline** (`seed_data.py` vs
  `seed_realistic_data.py`) so the cast can be edited without touching the machinery. The
  relationship graph is written out explicitly rather than randomised, so every run produces
  the same demo state.
- **Emails use `@example.com`** (RFC 2606 reserved). The app sends verification and reset
  mail; plausible gmail addresses would mean mailing real strangers.
- **Achievements are derived from database state**, not from the seed script's data
  structures — so the backfill also repairs accounts broken any other way. It only ever adds
  badges, never revokes, matching how the app grants them.
- **WebSockets accept before authorisation.** The JWT check stays ahead of `accept()` because
  it is local CPU work, so bad tokens never occupy a connection. Everything requiring I/O
  happens after, closing with a policy code if it fails.
- **Chat broadcasts locally first, then publishes to Redis** for other instances, tagged with
  an `INSTANCE_ID` the listener uses to skip its own echo. Chat now works even if Redis is
  unreachable.
- **`127.0.0.1` over `localhost` in dev.** Not cosmetic: `localhost` resolves to `::1` first,
  the backend binds IPv4 only, and Windows took 2.067 s to refuse the IPv6 attempt before
  falling back (vs 0.015 s direct). This was most of the chat "Connecting…" delay.
- **Password `123456789`.** You first said "129"; I read "1 to 9" as the intent when you
  corrected it. At nine characters it also clears the API's 8-char minimum, so these accounts
  can be password-reset normally.

## Failed Attempts

- **`thispersondoesnotexist.com` for synthetic faces** — now returns HTML, not an image.
- **`source.unsplash.com` random-photo API** — returns 503; deprecated.
- **One Unsplash photo ID in the frontend was already dead** —
  `photo-1537151608804-ea6f117398e0`, behind the "Planning the Perfect First Playdate"
  article card, 404s. It had been rendering broken. Replaced with a dog.ceo photo.
- **Moving `accept()` earlier appeared not to help** (2.50 s → 2.05 s). It *had* worked; the
  residual 2 s was the IPv6 resolution tax, which I only found by timing `/health` twice and
  noticing the first call was slow and the second instant.
- **A first pass at the playdate quick-slots read the clock during render** — ESLint's purity
  rule caught it. Correct catch: the slot list would have shifted mid-form as a boundary
  passed. Clock reads now happen once on mount.
- **PowerShell here-string syntax in a Bash tool call** put a stray `@` in a commit message;
  fixed by amending with a proper heredoc.
- **Bundling scroll fixes into the profile-fix commit** — split into two commits afterwards.

## Next Steps

1. **Restart the Vite dev server** (`cd frontend && npm run dev`). Nothing else works
   correctly until this happens — `.env` changed.
2. **Walk the UI and confirm the unverified visuals** (listed under Current State): reload a
   few times to confirm the splash no longer appears; open Profile; open a chat; open the
   notifications dropdown; hit Propose on a playdate.
3. **Confirm the navbar avatar renders your photo.** The query-key fix should have settled it,
   and a later screenshot suggested it had, but I never saw it directly.
4. **Push.** Both repos are ahead of their remotes and nothing has been pushed all session.
   Push the submodule first, then the parent, or the pointer will dangle.
5. Consider: the `Mowgli` dalmatian photo shortage, if 2 photos bothers you — switch the breed
   in `seed_data.py`.
6. Consider: chat's sustained-typing latency (0.63 s/msg) is bounded by two sequential commits
   to a database in another region. Moving the post-delivery bookkeeping onto a background
   task with its own session would cut it further; I stopped short because it needs concurrency
   testing I couldn't do here.
7. Consider: the JS bundle is 1.17 MB (288 KB gzipped) and Vite warns about it. Code-splitting
   the route components would be the obvious win.

## Git Status

- **Branch:** `main` in both the parent repo and the `frontend` submodule.
- **Uncommitted changes:** none. Both working trees are clean.
- **Unpushed:** everything from this session. 8 commits in the parent
  (`7ccc62e..30b0abe`), 12 in the submodule (`f6a3a57..e089589`).
- **Note:** `frontend` is tracked as a gitlink but has no `.gitmodules` entry, so
  `git submodule status` errors. Pre-existing; not introduced here.

No commit message needed — everything is committed. To push:

```bash
cd frontend && git push origin main
cd .. && git push origin main
```
