"""Smoke test for the location-enrichment endpoints (/conditions, /places, /travel).

Run: uv run python app/tests/test_enrichment_smoke.py

Hits the real upstreams (Open-Meteo, Overpass) and needs Redis + the dev DB, so
it is a smoke test rather than a unit test — same shape as the other scripts in
this folder. The assertions that matter most are the degradation ones: a card
must survive a provider being slow, absent, or down.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.core.redis import redis_client
from app.main import app
from app.utils.distance import haversine_distance

# KBR Park, Hyderabad — a real place with real parks around it, so the Overpass
# assertions have something to find.
LAT, LNG = 17.4239, 78.4138


def iso_in(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        # Start from a clean cache so the timing comparison below is meaningful.
        for key in await redis_client.keys("cond:*"):
            await redis_client.delete(key)

        # --- 1. Conditions for tomorrow evening -----------------------------
        started = time.monotonic()
        r = await client.get("/conditions", params={"lat": LAT, "lng": LNG, "at": iso_in(1)})
        cold_ms = (time.monotonic() - started) * 1000
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["available"], f"expected a forecast for tomorrow: {data}"
        assert data["temperature_c"] is not None, data
        assert -60 < data["temperature_c"] < 60, f"implausible temperature: {data}"
        assert data["us_aqi"] is not None, f"AQI should exist one day out: {data}"
        assert data["aqi_band"] is not None, data
        print(f"PASS: /conditions tomorrow — {data['temperature_c']}C, "
              f"{data['summary']}, AQI {data['us_aqi']} ({data['aqi_band']})")

        # --- 2. Second identical call is served from Redis -------------------
        started = time.monotonic()
        r2 = await client.get("/conditions", params={"lat": LAT, "lng": LNG, "at": iso_in(1)})
        warm_ms = (time.monotonic() - started) * 1000
        assert r2.status_code == 200, r2.text
        assert await redis_client.keys("cond:*"), "nothing was cached"
        assert warm_ms < cold_ms, f"cache hit ({warm_ms:.0f}ms) not faster than miss ({cold_ms:.0f}ms)"
        print(f"PASS: /conditions cached — {cold_ms:.0f}ms cold vs {warm_ms:.0f}ms warm")

        # --- 3. Beyond the forecast horizon: answered without a network call -
        started = time.monotonic()
        r = await client.get("/conditions", params={"lat": LAT, "lng": LNG, "at": iso_in(30)})
        horizon_ms = (time.monotonic() - started) * 1000
        assert r.status_code == 200, r.text
        assert r.json()["available"] is False, r.text
        # No upstream request could have completed this fast — this is the
        # assertion that the horizon guard short-circuits rather than trying.
        assert horizon_ms < 50, f"30-days-out took {horizon_ms:.0f}ms; guard may not be short-circuiting"
        print(f"PASS: /conditions 30 days out — available=false in {horizon_ms:.0f}ms, no upstream call")

        # --- 4. Past the AQI horizon but inside the weather one --------------
        r = await client.get("/conditions", params={"lat": LAT, "lng": LNG, "at": iso_in(10)})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["available"], data
        assert data["us_aqi"] is None, f"AQI only forecasts 7 days; got {data['us_aqi']}"
        print("PASS: /conditions 10 days out — weather present, AQI null")

        # --- 5. Past dates ---------------------------------------------------
        r = await client.get("/conditions", params={"lat": LAT, "lng": LNG, "at": iso_in(-2)})
        assert r.status_code == 200 and r.json()["available"] is False, r.text
        print("PASS: /conditions for a past date — available=false")

        # --- 6. Nearby places (needs auth) -----------------------------------
        email = f"smoke-{uuid.uuid4().hex[:8]}@test.com"
        r = await client.post("/auth/register", json={"email": email, "password": "password123"})
        assert r.status_code in (200, 201), r.text
        auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.get("/places/nearby", params={"lat": LAT, "lng": LNG}, headers=auth)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert items, "expected at least one named park near KBR Park"
        assert all(p["name"].strip() for p in items), "unnamed place leaked through"
        distances = [p["distance_m"] for p in items]
        assert distances == sorted(distances), "results are not nearest-first"
        print(f"PASS: /places/nearby — {len(items)} spots, nearest '{items[0]['name']}' "
              f"at {items[0]['distance_m']}m")

        # Auth is required.
        r = await client.get("/places/nearby", params={"lat": LAT, "lng": LNG})
        assert r.status_code in (401, 403), f"expected auth challenge, got {r.status_code}"
        print("PASS: /places/nearby requires auth")

        # --- 7. Travel estimate ----------------------------------------------
        to_lat, to_lng = 17.4483, 78.3915  # Hitec City
        r = await client.get(
            "/travel/eta",
            params={"from_lat": LAT, "from_lng": LNG, "to_lat": to_lat, "to_lng": to_lng},
        )
        assert r.status_code == 200, r.text
        estimate = r.json()

        expected_km = round(haversine_distance(LAT, LNG, to_lat, to_lng), 1)
        if settings.ola_maps_configured:
            # With a key we may get either — Ola when it answers, straight-line
            # when it doesn't. Both are valid; only a 5xx would be a failure.
            print(f"PASS: /travel/eta — {estimate['distance_km']}km via {estimate['source']}, "
                  f"{estimate['duration_minutes']} min")
        else:
            assert estimate["source"] == "straight_line", estimate
            assert estimate["duration_minutes"] is None, estimate
            assert estimate["distance_km"] == expected_km, f"{estimate} != haversine {expected_km}"
            print(f"PASS: /travel/eta with no key — {estimate['distance_km']}km straight-line "
                  f"(matches haversine), no drive time claimed")

        # --- 8. A dead routing provider must not break the card --------------
        # The important one: pretend Ola is configured but unreachable, and
        # confirm we still answer rather than 5xx-ing a decorative badge.
        original_key, original_base = settings.ola_maps_api_key, settings.ola_maps_base_url
        settings.ola_maps_api_key = "smoke-test-not-a-real-key"
        settings.ola_maps_base_url = "https://ola-maps.invalid"
        try:
            r = await client.get(
                "/travel/eta",
                params={"from_lat": LAT, "from_lng": LNG, "to_lat": to_lat, "to_lng": to_lng},
            )
            assert r.status_code == 200, f"vendor outage returned {r.status_code}: {r.text}"
            assert r.json()["source"] == "straight_line", r.text
            print("PASS: /travel/eta with an unreachable provider — falls back, no error")
        finally:
            settings.ola_maps_api_key, settings.ola_maps_base_url = original_key, original_base

    await redis_client.aclose()
    print("\nALL SMOKE TESTS PASSED")


asyncio.run(main())
