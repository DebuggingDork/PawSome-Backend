"""Throwaway smoke test for browse + logout. Run: uv run python smoke_test2.py"""
import asyncio
import uuid
import httpx
from app.main import app
async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"smoke-{uuid.uuid4().hex[:8]}@test.com"
        r = await client.post("/auth/register", json={"email": email, "password": "password123"})
        tokens = r.json()
        ha = {"Authorization": f"Bearer {tokens['access_token']}"}
        pet_name = f"Browse-{uuid.uuid4().hex[:6]}"
        r = await client.post("/pets", json={
            "name": pet_name, "species": "dog", "breed": "Beagle", "age_months": 12,
            "gender": "female", "lat": 17.4, "lng": 78.5,
        }, headers=ha)
        assert r.status_code == 201, r.text
        pet_id = r.json()["id"]
        # --- Public browse: NO auth header at all ---
        r = await client.get("/pets", params={"limit": 50})
        assert r.status_code == 200, r.text
        pets = r.json()
        assert any(p["id"] == pet_id for p in pets), "created pet not in public list"
        assert all("lat" not in p for p in pets), "coords leaked in public list"
        print("PASS: GET /pets public list works without auth, hides coords")

        # --- Refresh rotation: old refresh token is single-use ---
        old_refresh = tokens["refresh_token"]
        r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 200, r.text
        new_tokens = r.json()
        r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 401, f"reused rotated token should be 401, got {r.status_code}: {r.text}"
        print("PASS: refresh rotation — old refresh token rejected after use")
        # --- Logout revokes the current refresh token ---
        r = await client.post("/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
        assert r.status_code == 204, r.text
        r = await client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
        assert r.status_code == 401, f"refresh after logout should be 401, got {r.status_code}: {r.text}"
        print("PASS: POST /auth/logout revokes refresh token (Redis denylist)")
        # Logout is idempotent / tolerant of garbage
        r = await client.post("/auth/logout", json={"refresh_token": "garbage"})
        assert r.status_code == 204, r.text
        print("PASS: logout idempotent with invalid token")
        # Cleanup: deactivate the browse pet so it doesn't pollute the catalog
        r = await client.post("/auth/login", json={"email": email, "password": "password123"})
        ha2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.delete(f"/pets/{pet_id}", headers=ha2)
        assert r.status_code == 204, r.text
        print("PASS: cleanup done")
        print("\nALL SMOKE TESTS PASSED")
asyncio.run(main())