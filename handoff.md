# Handoff — 27 July 2026 (landing page redesign)

> Replaces the handoff for the location & enrichment session. That work is committed; anything
> from it still relevant — including its outstanding UI verification list — is carried into
> **Next steps** and **Gotchas** below. Everything else here is new.

---

## Goal

Rebuild the marketing home page (`/`) so it shows the pets that are actually in the database
instead of stock photography and invented copy, and raise the visual craft to the standard the
About page already sets.

The *why*: the page was advertising a product PawSome does not have. Three identical stock Golden
Retrievers stood in for "pets near you", a pinned strip featured two pets who do not exist, an
articles section headed three pieces nobody wrote, and the hero claimed **10K+ Happy Pets / 8K+
Pet Parents / 100% Verified** against a database of about thirty animals — while `/about`
promises, in as many words, not to pad the numbers. The user's brief: fill the cards with the
real information we have, keep the sliding/scroll animations exactly as they are, make it look
like a person built it rather than an AI template, and commit once.

---

## Current state

**Done and verified.** The landing page renders real pets end to end. `tsc -b` and `npm run build`
are clean. Lint sits at 10 pre-existing problems, none in any file this session touched.
Screenshotted over the Chrome DevTools Protocol at 390 / 768 / 1280 / 1920 px with zero
horizontal overflow at any width.

**Committed.** Two commits, because `frontend` is a submodule — one inside it, one in the parent
moving the gitlink. **Nothing is pushed.**

**Known problems that are NOT code bugs:**

1. **A pet photo in the database carries an iStock watermark.** `Mouli` (Shih Tzu, 9mo, the only
   non-seeded pet, id `34d7f4f9-3637-4801-82e2-ae34e285efb8`) has a primary photo with a visible
   `iStock / Credit: elenasendler` watermark burned in. Because `/pets` returns newest-first,
   Mouli leads every list, so this appears on the homepage. That is a licensing problem as much
   as a visual one. **Fix it in the data** — replace or delete the photo — rather than
   special-casing it in the frontend. The landing grid no longer *leads* with Mouli (the widest
   card picks whoever has the longest bio, currently Sheru), but Mouli still appears in the
   portrait row and in the how-it-works artwork.
2. **Zero events in the database.** `GET /events` returns `total: 0`. An events section was
   considered for the landing page and dropped for that reason. Worth revisiting if events get
   seeded.

**Untouched:** every other page. `/about`, `/faq`, `/community`, `/discover`, `/events`, `/chat`,
`/profile` are exactly as they were. The only non-landing files changed are `Auth/index.tsx` (one
copy line, one image rename), `PawsomeFooter.tsx` (wordmark colour) and shared animation
primitives.

---

## Files in play

Frontend paths are relative to `D:\PawSome\frontend\`.

### Created

| File | What and why |
| --- | --- |
| `src/pages/Landing/useLandingPets.ts` | One React Query hook feeding every section. Deliberately a bare `fetch` against `API_BASE_URL`, **not** `browsePets()` from `lib/api` — see Gotchas, this is load-bearing. Also exports `nameRollCall()`. |
| `src/components/landing/PetSpotlightCard.tsx` | The real-pet card. Two layouts (`tall`, `wide`). Reuses `activeHealthTags`, `formatAge`, `GenderBadge`, `speciesEmoji` so the landing cannot drift from Community. |
| `src/pages/Landing/sections/HowItWorksSection.tsx` | Replaces `ArticlesSection`. Provides the `#how-it-works` anchor the hero had always linked to and which never existed. Illustrations are real pets arranged to mean something per step (one profile / a browse grid / a matched pair). |
| `src/pages/Landing/sections/TrustSection.tsx` | Replaces `ProofPointsSection`. Editorial list, not a card grid. Copy quotes the FAQ rather than contradicting it. |
| `src/pages/Landing/sections/FeaturedPetsSection.tsx` | Replaces `FeaturedProductsSection`. **Same GSAP pin, same scrub, same panel dimensions** — only the contents changed. |
| `src/pages/Landing/sections/ClosingSection.tsx` | Replaces `ProductBannerSection`. Keeps the scroll-driven expand; drops the two inert app-store buttons. |

### Deleted

| File | Why |
| --- | --- |
| `src/pages/Landing/sections/ArticlesSection.tsx` | Three articles that were never written. |
| `src/pages/Landing/sections/ProofPointsSection.tsx` | Three identical icon+heading+text cards. |
| `src/pages/Landing/sections/FeaturedProductsSection.tsx` | Featured two pets who do not exist. |
| `src/pages/Landing/sections/ProductBannerSection.tsx` | App Store / Play Store buttons for an app that does not exist. |
| `src/components/animations/HoverZoomImage.tsx` | Only consumer was `ArticlesSection`; its premise (scaling an `<img>` on hover) is the pattern being moved away from. |
| `src/components/animations/HoverCard.tsx` | Only consumers were the two replaced sections. Verified unused before deleting. |

### Modified

| File | What changed |
| --- | --- |
| `src/pages/Landing/index.tsx` | New section order: hero → how it works → pets → pinned strip → trust → closing → footer. |
| `src/pages/Landing/sections/HeroSection.tsx` | New photo; five-stop inline-style scrim; fake stat tiles replaced by a live name roll-call; `clamp()` max 6.5rem → 5.5rem. Keeps sticky scale, parallax, entrance stagger, hand-drawn heart SVG. |
| `src/pages/Landing/sections/PetToggleSection.tsx` | Real dogs/cats. **Keeps** the shared-`layoutId` pill and the `AnimatedToggle` height transition. Pill recoloured pink/violet → brand orange. |
| `src/components/animations/ScrollPinnedSlider.tsx` | Added `contentKey` (rebuilds the pin when panels arrive async) and a reduced-motion fallback to a plain horizontal scroller. |
| `src/components/animations/{ScrollReveal,StaggerReveal,HeroEntrance,ParallaxImage,AnimatedToggle}.tsx` | `useReducedMotion` support. Default behaviour unchanged for anyone not asking for reduced motion. `ParallaxImage` also gained `priority` for the LCP image. |
| `src/index.css` | Added `--ease-out-quart` / `--ease-out-expo` and the `hoverable` custom variant. |
| `src/lib/siteImages.ts` | Eight entries → two (`heroPets`, `duskRun`). |
| `src/pages/Auth/index.tsx` | `siteImages.heroDog` → `siteImages.duskRun`; removed "Join 10,000+ pet parents". |
| `src/components/ui/PawsomeFooter.tsx` | Gradient-clipped wordmark → solid `#ff6b35`. |
| `backend/scripts/upload_site_images.py` | Image set cut to two; documents the Unsplash 403 workaround. |

---

## Changes made

1. Located the project — the session opened in `D:\ShineBack` (an unrelated Flutter app).
   PawSome is at **`D:\PawSome`**.
2. Read the landing sections, animation primitives, `seed_data.py`, About/FAQ (the tonal
   reference), and confirmed `GET /pets` is public and unauthenticated.
3. Started backend + Vite (ports in Gotchas) and confirmed live data: **30 pets, 22 dogs, 8 cats,
   25 breeds, all with photos and bios; 0 events.**
4. Added `useLandingPets`, `PetSpotlightCard`, then rewrote every section.
5. Added reduced-motion support and the easing/hover tokens.
6. Sourced a new hero photo (Unsplash `h5dS6qKpbNU`), uploaded it and the existing dusk photo to
   R2 via `upload_site_images.py`. **This mutated the bucket** — `site/heroPets.jpg` and
   `site/duskRun.jpg` are new objects. The six old objects (`heroDog.jpg`, `article*.jpg`,
   `featured*.jpg`, `toggle*.jpg`) remain in the bucket, now unreferenced.
7. Screenshotted every section over CDP and fixed three real defects found that way (below).
8. Committed:
   - `frontend` — `8f0f213 Rebuild the landing page around the pets that actually exist`
   - parent — bumps the gitlink and carries the backend script + this file.

**Not pushed.** The parent was already ~24 commits ahead of `origin/main` before this session.
Pushing is outward-facing and was never authorised.

---

## Failed attempts / dead ends

Read this before re-treading any of it.

### The Chrome extension is not connected — drive CDP directly

`mcp__claude-in-chrome__*` fails with:

> Browser extension is not connected. Please ensure the Claude browser extension is installed and running

Do not burn time on it. **Chrome itself is installed** at
`C:\Program Files\Google\Chrome\Application\chrome.exe` and driving it over CDP works. Node 22 has
a native `WebSocket`, so **no puppeteer is needed** — CDP is JSON over one socket. Two scratchpad
scripts were written and are worth recreating: `shoot.mjs` (scroll to a Y, screenshot) and
`overflow.mjs` (horizontal-overflow check across widths).

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --hide-scrollbars --remote-debugging-port=9222 --user-data-dir=<scratch>/chrome-profile about:blank &
```

Wait for `#root.ready` before capturing — `useSmoothScroll` adds that class and `#root` is
`visibility: hidden` until it does.

### `--headless=old --screenshot` produces a WRONG layout

It composites `position: fixed` and `sticky` at their document offset rather than their painted
position. The fixed navbar rendered ~700 px down the image and the hero appeared to have a huge
black gap above it. **Nothing was actually broken.** Use `--headless=new` + CDP
`Page.captureScreenshot` after a real scroll. Trust content from old-headless shots, never layout.

### Unsplash's download endpoint 403s the upload script

```
httpx.HTTPStatusError: Client error '403 Forbidden' for url
'https://unsplash.com/photos/h5dS6qKpbNU/download?w=2400'
```

It rejects the script's `PawSome-Seeder/1.0` User-Agent, though plain `curl` is fine. Do not add a
fake browser UA. Resolve the stable CDN slug once and paste it into `IMAGES`:

```bash
curl -sL -o /dev/null -w "%{url_effective}\n" "https://unsplash.com/photos/<shortId>/download?w=2400"
# -> https://images.unsplash.com/photo-1711832740932-f7f3fe63cdd5?...
```

### A JSX comment directly inside a `&&` expression is a parse error

`{cond && (` followed by `{/* comment */}` then the element fails:

```
[PARSE_ERROR] Expected `,` or `)` but found `Identifier`
src/components/landing/PetSpotlightCard.tsx:96:14
```

`{/* */}` is only valid where JSX *children* are expected. Put the comment above the `{cond &&`
line. The symptom misleads: the dev server serves a stale module, `document.scrollHeight`
collapses to one viewport, and it looks like a runtime bug rather than a syntax error.

### The first hero scrim was far too heavy

The initial `from-neutral-950 via-neutral-950/85 to-transparent` reproduced the exact fault being
fixed — a black rectangle with a dog in the corner. It was caught by simulating the scrim over
candidate photos in PIL *before* writing any CSS, which is far faster than iterating in a browser.
Lesson: **pick the photograph for its composition first.** The scrim only works because the chosen
image already has its subject and light in the right third and shadow on the left.

### The wide card cannot share a grid row with a portrait card

CSS grid stretches every item in a row to the tallest, so the wide lead card inherited a 670 px
portrait's height and rendered as a photo beside a large black void. It now sits on its own row
with a fixed `sm:h-[22rem]`.

Related: the lead card must **not** be `pets[0]`. The newest pet has a four-word bio, which left
the widest slot on the page nearly empty. The lead is now whoever has the longest bio.

### Considered and rejected

- **An events section** — `GET /events` returns `total: 0`.
- **Owner names on landing cards** — `/pets` deliberately nulls `owner` for anonymous callers. Do
  not "fix" this by requiring auth on the landing page.
- **A geography claim ("across Hyderabad")** — the seed data is Hyderabad, but the public `/pets`
  response exposes no locality and the frontend claims a city nowhere else. Copy says "nearby".

---

## Next steps

### Immediate

1. **Look at it in a real browser.** Everything was verified in headless Chrome. Two things
   headless cannot confirm: **emoji rendering** (the species glyph in the card badges — it uses
   the same `speciesEmoji` helper Community already uses, so it should be fine, but it is
   unverified on real Windows Chrome), and the **feel of the scroll animations**, which is
   precisely what the user asked to preserve. Scroll the pinned strip and the species toggle.
2. **Replace Mouli's watermarked photo** (see *Current state*). Data fix, not a code fix.
3. **Decide whether to keep it.** The user said they would review and either push or revert. The
   frontend commit is `8f0f213`; `git revert` it and reset the parent gitlink to undo cleanly.

### Backlog

4. **Still unverified from the previous session** — none of this was retested here, and all of it
   is on pages this session did not touch:
   - whether the OSM iframe preview in playdates actually displays (framing is permitted at the
     protocol level: the embed URL returns 200 with no `X-Frame-Options` and no CSP; ad blockers
     and whether tiles paint are still untested)
   - weather/AQI pill layout on a narrow card, and whether `EventCard` overflows its grid tile
   - whether the `.ics` download imports at the correct local time
   - whether nearby-place chips wrap sanely in the propose form
   - that distance appears after "use my current location", with **no** geolocation prompt
5. **Push** — parent ~24 commits ahead, submodule now 3. **Push the submodule first** or the
   parent's gitlink points at a commit nobody can fetch. Never authorised; do not do it unprompted.
6. Delete the six now-unreferenced `site/*.jpg` objects from R2 if bucket tidiness matters. They
   cost nothing and nothing points at them.
7. The JS bundle is 1.29 MB (326 kB gzipped) and vite warns about it. Pre-existing, but the
   landing page is the one route where it costs a first-time visitor most.

### Open questions

- **None blocking.** One judgement call worth flagging: the Auth page's "Join 10,000+ pet parents"
  line was rewritten even though the brief said "home page". It was changed because the home page
  now states the real, much smaller number one click away, so leaving it would have been a visible
  contradiction. Revert that single line if you disagree.

---

## Gotchas

### Running things

```bash
# Backend (needs Neon Postgres + Upstash Redis reachable)
cd /d/PawSome/backend && uv run uvicorn app.main:app --reload

# Frontend — NOTE: the dev server comes up on 5174, not 5173, and CORS_ORIGINS
# in backend/.env is set to http://localhost:5174 to match.
cd /d/PawSome/frontend && npm run dev

cd /d/PawSome/frontend && npm run build && npm run lint

# The enrichment smoke test — PYTHONPATH is REQUIRED. Hits real Open-Meteo and
# Overpass, needs Redis + the DB, takes ~30 s. Not hermetic.
cd /d/PawSome/backend && PYTHONPATH=. uv run python app/tests/test_enrichment_smoke.py
```

`uv` is the only working Python entry point — `backend/.venv/Scripts/python.exe` has **no pip and
no Pillow**. For anything needing Pillow: `uv run --with pillow python <script>`.

### Things that look wrong but are intentional

- **`useLandingPets` bypasses `lib/api/client`.** `apiFetch` counts network-level failures and
  after two hands the whole app to `ServerErrorPage`. Right for `/discover`, wrong for the one
  page a stranger sees first — a backend outage should still leave the pitch and a working Sign
  In. Every landing section degrades on its own instead. **Do not tidy this into `browsePets()`.**
- **The hero scrim is inline `style`, not Tailwind classes.** It needs five colour stops;
  `from/via/to` gives three.
- **`FeaturedPetsSection` returns `null` when there are no pets** — otherwise the pin reserves a
  screen-height hole in the page.
- **`ScrollPinnedSlider` takes `contentKey`.** The pin distance is measured from `scrollWidth`
  once; panels arriving from the API later would leave the pin ending in the wrong place. If you
  change what renders inside it, keep feeding it a key that changes with the content.
- **`PetSpotlightCard`'s wide layout has a hard-coded `sm:h-[22rem]`** — its own content cannot
  give it a sensible height. See *Failed attempts*.
- **Health-tag colours (emerald/sky/violet) and gender colours (pink/sky) are NOT brand drift.**
  They are functional tokens from `lib/petBadges.ts`, shared with Community and the swipe deck.
  Only the *marketing* accent was unified to `#ff6b35`.
- **`hoverable:` is a custom variant defined in `index.css`**, not a Tailwind built-in.
- **No `/api/v1` prefix.** Routers mount at the app root, each carrying its own prefix.
- **`useUserLocation` never asks for permission** — it only reads a position `LocationPicker`
  stored. Distance therefore does not appear until the user has volunteered it once. Deliberate.
  **Do not "fix" this by calling `navigator.geolocation`.**
- **`ConditionsBadge` and `DistanceBadge` render `null` while loading and on error.** They are
  decorative; a weather outage must be invisible.
- **Map links use coordinates, never the address string** — passing the address would let Google
  re-geocode it to a different pin than the one the user picked.

### Carried over from previous sessions (still true)

- **Seeded accounts** use password `123456789`; `arjun.reddy@example.com` is the demo account
  (3 pets, 6 matches, live chats). 25 users across real Hyderabad localities.
- **`frontend` is a gitlink with no `.gitmodules` entry**, so `git submodule status` errors.
  Pre-existing. Commit inside `frontend/` directly, then commit the gitlink in the parent.
- **Use `127.0.0.1`, not `localhost`,** in dev config. `localhost` resolves to `::1` first, the
  backend binds IPv4 only, and Windows takes ~2 s to refuse the IPv6 attempt.
- **10 pre-existing lint problems**, in `Chat/index.tsx`, `ChatSearchPanel.tsx`,
  `NotificationToast.tsx`, `DotLottieLoader.tsx`, `LocationPicker.tsx`, `useSmoothScroll.ts`.
  Don't chase them thinking this session caused them.
- **There is no frontend test framework.** No vitest, no jest, no `test` script. `tsc`, `vite
  build`, `eslint` and screenshots are the whole safety net.
- **The backend pytest suite does not run** — no `conftest.py`, pytest is not in `pyproject.toml`.
  The working pattern is standalone `httpx.ASGITransport` scripts run via `uv run python`.

### Windows specifics

- `Bash` tool is Git Bash; `PowerShell` tool is Windows PowerShell 5.1 (no `&&`, no ternary).
- Git warns `LF will be replaced by CRLF` on nearly every file. Pre-existing, harmless.
- vite's chunk-size warning gets wrapped by PowerShell as a `NativeCommandError` — the build still
  succeeded. Check for `✓ built in`.
- Scratch scripts belong in the session scratchpad, not `/tmp`.
