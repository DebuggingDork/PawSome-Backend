# 🗺️ Location & Maps in PawSome

How PawSome turns "where should we meet?" into a pin, a map, and turn-by-turn
directions — plus the external-API landscape we evaluated and what we'd add next.

**Status:** Shipped — "Show in map", weather + air quality, add-to-calendar,
nearby dog parks, and distance. Everything runs on free, keyless APIs and costs
₹0. The one thing not enabled is routed drive time, which needs a card on file
([§4.5](#45-drive-times-why-were-on-straight-line)) — the code path is wired and
falls back to straight-line distance.

---

## 1. The user story

Two owners match in chat. One proposes a playdate:

1. Picks a **date & time** — quick slots ("Tomorrow evening", "Saturday morning")
   or the full `datetime-local` picker.
2. Names the place — *"KBR Park walking track"*.
3. Types an **address**; autocomplete resolves it to real coordinates + pincode.
4. **Taps "Show in map"** to confirm the pin is actually where they meant.
5. Sends. The other owner sees the same card, with the same map, and a
   **Directions** button that opens Google Maps navigation from wherever they are.

Step 4 is the piece this document is mostly about. An address string that *reads*
correctly can still geocode to the wrong side of the city, and a playdate is a
real-world meetup between strangers — being able to see the pin before you commit
is the difference between a feature and a liability.

---

## 2. What's shipped

### 2.1 The location stack today

| Layer | What it does | Provider | Cost |
|---|---|---|---|
| Address autocomplete | Free-text → suggestions with coords + pincode | **Nominatim** (OpenStreetMap), proxied by our backend | Free |
| Reverse geocoding | "Use my current location" → address + pincode | **Nominatim**, same proxy | Free |
| Map preview | Inline map with a marker | **OpenStreetMap embed** iframe | Free, no key |
| Open in map / Directions | Hand off to a real maps app | **Google Maps URLs API** | Free, no key |
| Weather + air quality | Forecast and AQI at a place and hour | **Open-Meteo**, proxied + cached | Free, no key |
| Nearby dog parks / vets | POI search around a point | **Overpass** (OpenStreetMap), proxied + cached | Free, no key |
| Distance | How far the venue is | haversine (Ola Maps wired but unkeyed, §4.5) | ₹0 |
| Add to calendar | `.ics` + Google Calendar link | none — plain text formats | ₹0 |

Only one of these can take a key, and it's optional. See
[§2.3](#23-why-no-google-maps-sdk) for why, and [§5](#5-constraints--gotchas)
for the limits that come with free tiers.

### 2.2 Files

**Maps & location**

| File | Role |
|---|---|
| `frontend/src/lib/maps.ts` | Pure URL builders — Google Maps deep links, OSM embed URL, helpers |
| `frontend/src/components/ui/ShowInMap.tsx` | The "Show in map" control: expandable preview + deep links |
| `frontend/src/components/ui/LocationPicker.tsx` | Address search, "use my location", map preview, nearby-spot chips |
| `frontend/src/lib/api/geocoding.ts` | Thin client for our geocoding proxy |
| `backend/app/api/routes/geocoding.py` | Nominatim proxy — CORS workaround, 1 req/s throttle, cancel-aware |

**Enrichment**

| File | Role |
|---|---|
| `backend/app/services/external_http.py` | Shared `Throttle`, `fetch_json`, `UpstreamUnavailable` |
| `backend/app/services/api_cache.py` | Redis TTL cache (`cached_json`, `geo_key`) |
| `backend/app/api/routes/conditions.py` | Open-Meteo weather + AQI proxy |
| `backend/app/api/routes/places.py` | Overpass POI proxy, with mirror fallback |
| `backend/app/api/routes/travel.py` | Ola Maps distance/ETA with haversine fallback |
| `frontend/src/components/conditions/ConditionsBadge.tsx` | Weather + AQI pills |
| `frontend/src/components/ui/{Badge,AddToCalendar,NearbyPlaces,DistanceBadge}.tsx` | The shared pill + three features |
| `frontend/src/lib/calendar.ts` | `.ics` builder + Google Calendar URL |
| `frontend/src/hooks/useUserLocation.ts` | Last-known position — read-only, never prompts |
| `backend/app/tests/test_enrichment_smoke.py` | End-to-end smoke test for all three endpoints |

**Cards**

| File | Role |
|---|---|
| `frontend/src/components/chat/PlaydateCard.tsx` | Map, weather/AQI, add-to-calendar when confirmed |
| `frontend/src/components/events/EventCard.tsx` | Map, weather/AQI, distance, add-to-calendar when going |

### 2.3 Why no Google Maps SDK

The obvious implementation is `@react-google-maps/api` plus a Maps JavaScript API
key. We deliberately didn't:

- **The Maps JavaScript, Embed, Static, Geocoding, and Places APIs all require a
  billable key.** Google's free tier is a monthly credit against metered usage,
  not a free plan — a key committed to a repo or shipped in a bundle is a
  standing bill with no ceiling.
- **The Maps URLs API needs no key at all.** It's a documented, versioned URL
  scheme (`?api=1` pins the version). It's free and unmetered because it isn't a
  data API — it's a hand-off.
- **The hand-off is the better product anyway.** Opening Google Maps gives the
  user turn-by-turn navigation, offline maps, saved places, share sheets, and
  their own transport preferences. Rebuilding a fraction of that in an iframe
  would be worse *and* cost money.
- **The inline preview uses OSM, not Google.** Google's Embed API is keyed; OSM's
  isn't. And since we geocode against OSM/Nominatim, the OSM preview shows the
  pin exactly where our search resolved it — a Google preview could render a
  slightly different position for the same coordinates' surroundings.

The trade-off we accept: the inline preview is a static-ish OSM frame, not a rich
interactive Google map. If we ever want a branded interactive map inside the app,
that's the point at which a key (and a budget) becomes justified — see
[§4.2](#42-tier-2--needs-a-key-or-a-budget).

### 2.4 The URL contracts

All of these are built in `frontend/src/lib/maps.ts`. Coordinates — not the
address string — are always the destination, so the pin lands exactly where the
proposer put it rather than being re-geocoded by Google into somewhere else.

```
View a pin
  https://www.google.com/maps/search/?api=1&query=<lat>,<lng>

Directions from the user's current position
  https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>&travelmode=driving

Street View at the location
  https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=<lat>,<lng>

Inline preview (keyless, OpenStreetMap)
  https://www.openstreetmap.org/export/embed.html?bbox=<w>,<s>,<e>,<n>&layer=mapnik&marker=<lat>,<lng>
```

On Android and iOS these URLs open the native Google Maps app if it's installed,
and the web version if it isn't. No platform detection needed on our side.

### 2.5 The `ShowInMap` component

```tsx
import { ShowInMap } from '@/components/ui/ShowInMap'

<ShowInMap
  point={{
    latitude: playdate.latitude,
    longitude: playdate.longitude,
    locationName: playdate.location_name,
    address: playdate.address,
  }}
/>
```

| Prop | Type | Notes |
|---|---|---|
| `point` | `MapPoint` | `latitude` + `longitude` required; `locationName` / `address` are labels only |
| `variant` | `'inline' \| 'link'` | `inline` (default) adds the expandable preview; `link` is just the two buttons |
| `className` | `string` | Passed to the wrapper |

Implementation notes worth keeping:

- **The iframe only mounts after the toggle.** A chat thread can hold ten
  playdates; ten map frames booting on render would be a real performance cost
  for a preview most people never open.
- `loading="lazy"` on top of that, for the case where one *is* open and scrolled
  past.
- The iframe has a descriptive `title` — screen readers otherwise announce it as
  an unlabelled frame — and the toggle carries `aria-expanded`.
- `hasCoordinates()` in `maps.ts` guards against rendering a map for a
  half-filled form.

### 2.6 Where it appears

| Surface | Variant | Why there |
|---|---|---|
| `LocationPicker` (playdate + event creation forms) | inline | Verify the pin **before** sending — the highest-value placement |
| `PlaydateCard` (chat) | inline | The recipient decides accept/decline partly on *where* |
| `EventCard` (events grid) | inline | "Is this near me?" is the first question about any public event |

### 2.7 Enrichment endpoints

All three are backend proxies. The browser never calls a third party directly —
that's what lets us cache in Redis, so one upstream call serves every user
looking at the same place. Routers mount at the app root (there is no
`/api/v1`).

#### `GET /conditions?lat=&lng=&at=<iso8601>`

Weather and air quality for the hour containing `at`. Optional auth (events are
browsable signed out). Cached 30 min at ~1.1 km granularity.

```json
{ "available": true, "observed_for": "2026-07-27T18:00:00+00:00",
  "temperature_c": 28.6, "precipitation_probability": 80, "weather_code": 61,
  "summary": "Light rain", "wind_speed_kmh": 12.3,
  "us_aqi": 48, "aqi_band": "good" }
```

Horizons are checked **before** any network call: weather forecasts 16 days,
air quality 7. Past either, `available` is `false` (or `us_aqi` is `null`) with
no request spent. Both feeds are fetched concurrently and fail independently —
a card can show temperature with no AQI. A result where both failed is never
cached, so a blip can't become a 30-minute outage.

#### `GET /places/nearby?lat=&lng=&radius_m=3000&kinds=dog_park,park,vet`

Named dog parks, parks, and vets from OpenStreetMap, nearest first. Requires
auth. Cached 24h — POIs barely change.

```json
{ "items": [ { "name": "bamboo park", "kind": "park",
               "latitude": 17.42, "longitude": 78.41, "distance_m": 798 } ],
  "total": 1 }
```

Matches both `node` and `way` (parks are usually mapped as areas, so querying
nodes alone finds almost nothing) and drops unnamed results — nobody can agree
to meet at "way/38472911".

#### `GET /travel/eta?from_lat=&from_lng=&to_lat=&to_lng=`

Distance, plus drive time when a routing key is configured. Optional auth.
Cached 6h.

```json
{ "distance_km": 3.6, "duration_minutes": null, "source": "straight_line" }
```

`source` is part of the contract, not an implementation detail: the UI says
"3.6 km away" for `straight_line` and "3.6 km · ~15 min drive" for `ola`.
Presenting a crow-flies number as a drive time would be wrong on any route with
a river in it.

---

## 3. Data model

Both `playdates` and `events` already carry the full shape — no migration was
needed for any of this:

| Column | Type | Notes |
|---|---|---|
| `location_name` | `varchar(255)`, required | Human name of the spot |
| `latitude` | `float`, required | Authoritative — what the map links use |
| `longitude` | `float`, required | |
| `address` | `text`, nullable | Display + search text from the geocoder |
| `pincode` | `varchar(20)`, nullable | Auto-filled; useful for coarse local filtering |

`scheduled_at` / `event_time` are `timestamptz`. Worth noting for later: we store
a UTC instant but **not the venue's timezone**. Today everything is effectively
one country so it doesn't bite. A Google/Azure Time Zone API lookup at write time
would future-proof it — see [§4.2](#42-tier-2--needs-a-key-or-a-budget).

---

## 4. 🧭 API landscape

Researched against the [APIs.io](https://apis.io) catalog (1,700+ mapping APIs,
1,683 providers) filtered for genuinely-free, open-access providers. Rating bands
below are APIs.io composite scores where available.

### 4.1 Tier 1 — free, no key, usable today

| Provider | Capability | Terms | PawSome fit |
|---|---|---|---|
| **Google Maps URLs** | Deep links: view, directions, Street View | Free, unmetered, no key | ✅ **Shipped.** The "Show in map" hand-off |
| **OpenStreetMap embed** | Keyless map iframe with marker | Free (ODbL attribution) | ✅ **Shipped.** The inline preview |
| **Nominatim** (OSM) | Forward + reverse geocoding | Free; **1 req/s**, User-Agent required | ✅ **Shipped.** Already proxied + throttled |
| **Open-Meteo** | Forecast, hourly, **air quality**, historical | No key; free for non-commercial; CC BY 4.0 data; AGPL, self-hostable | ✅ **Shipped.** Weather + AQI badges |
| **Overpass** (OSM) | Query OSM for POIs — `leisure=dog_park`, `amenity=veterinary` | Free, ODbL | ✅ **Shipped.** Nearby-spot chips |
| **Yr / MET Norway** | Forecast, nowcast, alerts, sunrise/sunset | Free, CC BY 4.0, User-Agent only | Not used. The drop-in fallback if Open-Meteo's non-commercial clause becomes a problem |

### 4.2 Tier 2 — needs a key or a budget

| Provider | Capability | Terms | Verdict |
|---|---|---|---|
| **Ola Maps** | Autocomplete, geocoding, directions, nearby search, tiles — **tuned for India** | 500K calls/month free, but **credentials require a registered credit card** (autopay), despite marketing saying otherwise | 🔌 **Wired, key deliberately unset.** `/travel/eta` falls back to haversine — see §4.5 |
| **Google Places / Autocomplete** | Best-in-class POI + autocomplete | Billable key, metered | Highest quality, highest cost. Only if Ola/Nominatim prove insufficient |
| **Google Maps Embed / Static** | Branded interactive or static map | Billable key | Only if we want a Google-branded map *inside* the app |
| **Google / Azure Time Zone** | IANA zone from coordinates | Billable key | Cheap fix for cross-timezone correctness (§3) |
| **Google Pollen / Air Quality** | Allergen + AQI by location | Billable key | Open-Meteo covers AQI free; pollen is genuinely differentiated but niche |
| **Stadia Maps / Jawg / MapQuest / Radar** | Freemium tiles + geocoding + routing | Freemium, self-serve | Viable Google alternatives if we ever need our own tiles |

### 4.3 What shipped, and why each one

#### 🌦️ Weather on the card — *Open-Meteo, free, no key*

We already stored coordinates and a timestamp; that's exactly Open-Meteo's
input. A rained-out playdate is the most common way a match dies *after* a
successful meetup proposal, so surfacing this at accept/decline time is worth
more than surfacing it on the day.

Shown for pending and accepted playdates and for upcoming events, inside the
16-day horizon. Rain probability at or above 50% flips the pill amber — below
that it's noise.

#### 🌫️ Air quality — *Open-Meteo AQI, free, no key*

Same shape, different endpoint. In Indian metros AQI genuinely determines
whether walking a dog is a good idea, and flat-faced breeds (pugs, bulldogs)
are disproportionately affected. Banded to US EPA breakpoints and colour-coded,
so "Poor air 168" reads without needing to know the scale.

Forecast horizon is 7 days versus weather's 16 — past that the pill just
doesn't appear rather than the whole badge failing.

#### 📍 Nearby spots — *Overpass, free*

`leisure=dog_park`, `leisure=park`, `amenity=veterinary` within 3 km, offered as
one-tap chips in the location picker. Same reasoning as the quick date slots:
most playdates happen at a handful of obvious places, so offer them instead of
making everyone type an address.

#### 📅 Add to calendar — *no API at all*

`.ics` download plus a Google Calendar link, on confirmed playdates and events
you're attending. Both, because neither covers everyone — the Google link is
one tap for most people here, and the `.ics` is the only thing that works for
Apple Calendar, Outlook, or anyone not signed in. The maps URL goes in the
`LOCATION` field, so the calendar entry itself is navigable.

#### 🚗 Distance & ETA — *Ola Maps when keyed, haversine otherwise*

"4.2 km away", upgrading to "4.2 km · ~15 min drive" once a key is set. Turns an
abstract address into a concrete yes/no.

The geolocation design is the part worth knowing about: prompting for location
because a card scrolled into view would be hostile — a permission dialog with no
explanation, attached to no action the user took. So `useUserLocation` **only
reads** a position captured earlier, when the user pressed "use my current
location" in the picker and knew what they were asking for. Distance simply
doesn't appear until then. An absent feature beats an unexplained prompt.

#### ⏰ Timezone correctness — *not done*

Store the IANA zone alongside the coordinates at write time. Only matters once
PawSome crosses a timezone boundary, but it's far cheaper to add at write time
than to backfill later.

#### 🐕 Breed data

Worth recording: **the APIs.io catalog has essentially no pet-domain APIs** — a
search across 1,700+ providers for dog/cat/breed data returned one insurtech with
no public API. Breed information should be treated as our own seeded data, not an
integration. That's a moat, not a gap.

### 4.4 Status

| Phase | Work | Dependency | Cost | State |
|---|---|---|---|---|
| 0 | Show in map — deep links + inline preview | none | ₹0 | ✅ Shipped |
| 1 | Weather + AQI on playdate/event cards | Open-Meteo | ₹0 | ✅ Shipped |
| 2 | Add-to-calendar (`.ics` + Google Calendar) | none | ₹0 | ✅ Shipped |
| 3 | Nearby dog parks in the location picker | Overpass | ₹0 | ✅ Shipped |
| 4 | Distance (straight-line) | none | ₹0 | ✅ Shipped |
| 4b | Drive ETA | Ola Maps key | needs a card on file | ⏸ Declined — see §4.5 |
| 5 | Timezone at write time | Google/Azure key | metered | ⏸ Not started |

Everything currently running costs nothing and involves no vendor relationship.

### 4.5 Drive times: why we're on straight-line

`/travel/eta` calls Ola Maps when `OLA_MAPS_API_KEY` is set. **It is
deliberately unset**, so cards say "4.2 km away" rather than
"4.2 km · ~15 min drive".

**Why.** As of 2026-07, Krutrim Cloud will not issue Ola Maps credentials
without registering a credit card for autopay — Ola Maps → Offerings →
Credentials opens a "Setup Autopay … Required to create and use credentials"
dialog with a ₹1 card-verification charge. Their marketing pages still claim
"no credit card required"; the console disagrees. Realistic usage would bill ₹0
against the 500K/month free tier, but attaching a live payment method to a
metered third-party API to power a decorative distance label is a bad trade.

Alternatives considered and not taken:

| Option | Blocker |
|---|---|
| **OpenRouteService** | Free key by email, likely no card — but their plans page is JS-rendered and the current terms couldn't be verified, so it may be the same wall |
| **OSRM public demo** | No key, no signup, but it's explicitly a *demo* server; the project asks people not to put production traffic on it |
| **Google Distance Matrix** | Billable key, metered — strictly worse than Ola on both cost and India coverage |

**If you do get a key later**, paste it into `backend/.env` and restart. Cards
upgrade as the 6-hour cache turns over; no code change. Purge early with
`redis-cli --scan --pattern 'eta:*' | xargs redis-cli del`.

The fallback also covers a wrong key, an expired key, or an Ola outage — those
return straight-line distance rather than an error, and the smoke test asserts
exactly that by pointing the client at a dead host.

> **Caveat on the Ola parser.** It's written against their documented
> Google-compatible Distance Matrix shape, but their API reference sits behind a
> JS app and we've never had a key to test with. It accepts both the nested
> `{value: n}` and plain-number forms and returns nothing on anything
> unrecognised — so a shape mismatch degrades to straight-line rather than
> erroring. If a key is ever added and `source` stays `straight_line`, that's
> the first thing to check.

> **Not done deliberately:** swapping address autocomplete from Nominatim to
> Ola. Ola's Indian address quality is genuinely better and it's the obvious
> next use of the same key, but it means changing a working, load-bearing path,
> so it deserves its own change rather than riding along with this one.

---

## 5. Constraints & gotchas

- **Nominatim is 1 req/s, globally, for our whole backend.** The proxy already
  serialises through a shared lock and drops requests whose client disconnected
  (see the comments in `geocoding.py` — abandoned keystroke searches were eating
  the budget). If address search starts feeling slow under load, that throttle is
  the reason, and Ola Maps is the fix.
- **Attribution.** OSM data is ODbL — the embed iframe carries OSM's own
  attribution, which satisfies it. If we ever render OSM tiles ourselves we must
  add it manually. Open-Meteo data is CC BY 4.0.
- **Open-Meteo's free tier is non-commercial.** Fine now; revisit before
  monetising. Yr/MET Norway is the drop-in fallback, or Open-Meteo's flat-rate
  paid plan.
- **Overpass sheds load.** It's volunteer-run and does real computation per
  query, so under load it returns a 429 or 504 instead of queueing — this failed
  roughly one run in two during development. `places.py` therefore tries a
  second public instance before giving up, and the 24-hour cache means we rarely
  ask at all. The UI treats a total failure as "no suggestions" and shows
  nothing, since suggestions are a convenience on top of a working address
  search.
- **Coordinates, not addresses, in map links.** Passing the address string would
  let Google re-geocode it to a different pin than the one the user picked.
- **Never commit a Maps key.** Only `/travel/eta` can use one, it lives in
  backend env config behind a server-side proxy, and it must never reach the
  frontend bundle.
- **Cache what's true, not what failed.** `cached_json` takes a `should_cache`
  predicate for exactly this: the loaders here degrade rather than raise, so
  without it one upstream blip would be cached as an empty result and served for
  the whole TTL — turning a moment's outage into half an hour of one.
- **Privacy.** Playdate coordinates are shared between two matched users only;
  event coordinates are public by design. Neither should ever leak into a
  third-party analytics payload.

---

## 6. Verifying

```bash
# Backend — hits the real upstreams; needs Redis + the dev DB running.
cd backend
PYTHONPATH=. uv run python app/tests/test_enrichment_smoke.py

# Frontend
cd frontend && npm run build && npm run lint
```

The smoke test covers the forecast horizons, the Redis cache actually being hit,
the Overpass result shape and ordering, auth on `/places/nearby`, straight-line
distance matching a hand-computed haversine, and — the one that matters most —
that an unreachable routing provider still yields a 200 with a usable answer
rather than a 5xx.

---

## 7. Related documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — overall system design
- [APP_STATES_AND_INTEGRATION.md](APP_STATES_AND_INTEGRATION.md) — frontend state
- [../backend/docs/CHAT_API.md](../backend/docs/CHAT_API.md) — chat & playdate endpoints
