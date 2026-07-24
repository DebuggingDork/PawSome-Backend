# App-level states, auth lifecycle, and backend/frontend wiring

This documents the state-page system and connectivity/session handling added
to the frontend, plus the conventions for keeping backend and frontend wired
together going forward. See `ARCHITECTURE.md` for the broader system design.

## State pages

Six full-page states, all built on one shared layout —
`frontend/src/components/ui/StatusPage.tsx` (icon tile, title, description,
action buttons) — so they read as one consistent system instead of six
one-off screens.

| Page | Route | Triggered by |
|---|---|---|
| `pages/NotFound` | `*` (catch-all) | Any unmatched route |
| `pages/SessionExpired` | `/session-expired` | An **active** session dying mid-use (see below) |
| `pages/Offline` | full takeover, no route | `navigator.onLine` going `false` |
| `pages/ServerError` | full takeover, no route | 2+ consecutive network-level fetch failures while online |
| `components/ui/ErrorBoundary` | wraps the whole app | Any uncaught React render/lifecycle error |
| `pages/Maintenance` | `/maintenance` | Manual only — no dynamic backend flag (out of scope for now) |

Offline and ServerError are **overlays**, not routes: `App.tsx` checks
`useOnlineStatus()` / a `backendUnreachable` flag before rendering
`BrowserRouter` at all, so they take over regardless of whatever page you were
on, and clear automatically the moment connectivity is restored — no reload
needed (Offline/ServerError's "Try again" buttons are a manual escape hatch,
not the only way out).

## Auth session lifecycle

Three problems in one system, all living in `frontend/src/lib/api/client.ts`,
`tokens.ts`, and `store/useAuthStore.ts`:

1. **Proactive refresh** — `tokens.ts` decodes the access token's `exp` claim;
   `client.ts` schedules a refresh ~60s before it actually expires (rescheduled
   on every token change via `onTokensChanged`). Normal browsing essentially
   never hits the reactive 401 path.
2. **Reactive fallback** — `apiFetch` still does a silent 401→refresh→retry for
   the case a request lands right at the edge of expiry.
3. **Session-expired sync** — if the refresh token itself is dead,
   `client.ts` fires `onSessionExpired`. `useAuthStore` subscribes once at
   module init: it only sets `sessionJustExpired: true` if the user *was*
   actively authenticated (not on a fresh boot with already-dead stored
   tokens — that's just "not logged in", not a session that expired out from
   under them). `App.tsx`'s `SessionExpiryWatcher` redirects to
   `/session-expired` exactly once when that flag flips.

`hydrate()` also guards against React 18 StrictMode's double-invoked mount
effect by caching the in-flight promise on the module (not in store state,
which hasn't updated yet on the second synchronous call).

## Backend/frontend wiring conventions

- Every backend route should have a frontend `apiFetch` caller, or a clear
  reason it doesn't (internal/websocket-only). An audit pass this round found
  the wiring itself was already 1:1 everywhere — the real gaps were backend
  features with schemas defined but **no route at all** (see below), which a
  route-vs-caller diff won't surface.
- Connectivity pub/sub follows one pattern throughout `client.ts`:
  `onSessionExpired` / `onBackendUnreachable` / `onBackendReachable` /
  `onTokensChanged` are all the same shape (register a listener, fire it from
  inside `apiFetch`/`refreshAccessToken`). Reach for this pattern again before
  inventing a new one.
- `QueryClient` defaults (`main.tsx`): `staleTime: 30_000`, `retry: 1`,
  `refetchOnWindowFocus: false`. Override per-query only when you have a
  specific reason (e.g. a swipe deck that must never silently reseed from a
  background refetch — see `pages/Discover/index.tsx`'s keyed seeding).

## Backend features wired this round

Found via an endpoint-vs-caller audit — schemas/services that existed but had
no route at all:

- **Unmatch** — `POST /matches/{match_id}/unmatch` (`UnmatchRequest` /
  `UnmatchResponse` already existed). Optionally blocks the other user, which
  also sweeps every other active match between the two of you.
- **Compatibility scoring** — `services/match_scoring.calculate_match_score`
  (breed/distance/age/gender-preference, 0-100) is now used by
  `GET /matches/browse` to rank results when a `pet_id` is supplied, instead
  of plain distance sort. Surfaced on Discover cards as a "NN% match" badge.
- **Health badges** — `PetCreate`/`PetUpdate` were missing
  `is_vaccinated` / `vaccination_date` / `is_neutered` / `is_trained`
  entirely, so no owner could ever set the fields Discover's filters already
  query by. Added to both schemas plus a small editor in `PetForm.tsx`.
