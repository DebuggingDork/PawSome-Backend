"""Throwaway smoke test for the pets API. Run: uv run python smoke_test.py"""
import asyncio
import uuid
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from app.api.deps import require_active_pet
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.user import User
async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        email_a = f"smoke-{uuid.uuid4().hex[:8]}@test.com"
        email_b = f"smoke-{uuid.uuid4().hex[:8]}@test.com"
        # Register two users: A owns a pet, B has none (browse-only user)
        r = await client.post("/auth/register", json={"email": email_a, "password": "password123"})
        tok_a = r.json()["access_token"]
        r = await client.post("/auth/register", json={"email": email_b, "password": "password123"})
        tok_b = r.json()["access_token"]
        ha = {"Authorization": f"Bearer {tok_a}"}
        hb = {"Authorization": f"Bearer {tok_b}"}
        r = await client.get("/pets/me", headers=ha)
        assert r.status_code == 200 and r.json() == [], r.text
        print("PASS: GET /pets/me empty before onboarding")
