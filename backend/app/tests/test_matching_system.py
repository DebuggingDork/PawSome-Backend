"""
Tests for the matching/swiping system.
Run with: uv run pytest app/tests/test_matching_system.py -v
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.match import Match
from app.models.notification import Notification
from app.models.pet_profile import PetProfile, PetSpecies
from app.models.swipe import Swipe, SwipeAction
from app.models.user import User


@pytest.fixture
async def user_a(db: AsyncSession) -> User:
    """Create first test user."""
    user = User(
        email="user_a@test.com",
        password_hash="hashed",
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def user_b(db: AsyncSession) -> User:
    """Create second test user."""
    user = User(
        email="user_b@test.com",
        password_hash="hashed",
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def dog_buddy(db: AsyncSession, user_a: User) -> PetProfile:
    """Create first test pet (dog)."""
    pet = PetProfile(
        user_id=user_a.id,
        name="Buddy",
        species=PetSpecies.DOG,
        breed="Golden Retriever",
        age_months=24,
        gender="male",
        bio="Friendly dog",
        lat=40.7128,
        lng=-74.0060,
        is_active=True,
    )
    db.add(pet)
    await db.commit()
    await db.refresh(pet)
    return pet


@pytest.fixture
async def dog_max(db: AsyncSession, user_b: User) -> PetProfile:
    """Create second test pet (dog)."""
    pet = PetProfile(
        user_id=user_b.id,
        name="Max",
        species=PetSpecies.DOG,
        breed="Labrador",
        age_months=30,
        gender="male",
        bio="Playful pup",
        lat=40.7128,
        lng=-74.0060,
        is_active=True,
    )
    db.add(pet)
    await db.commit()
    await db.refresh(pet)
    return pet


@pytest.fixture
async def cat_whiskers(db: AsyncSession, user_b: User) -> PetProfile:
    """Create a cat for species mismatch testing."""
    pet = PetProfile(
        user_id=user_b.id,
        name="Whiskers",
        species=PetSpecies.CAT,
        breed="Persian",
        age_months=18,
        gender="female",
        bio="Sleepy cat",
        lat=40.7128,
        lng=-74.0060,
        is_active=True,
    )
    db.add(pet)
    await db.commit()
    await db.refresh(pet)
    return pet


class TestSwipeEndpoint:
    """Tests for POST /matches/swipe endpoint."""

    async def test_swipe_like_no_match(
        self,
        client: AsyncClient,
        db: AsyncSession,
        user_a: User,
        dog_buddy: PetProfile,
        dog_max: PetProfile,
    ):
        """Test swiping right when target hasn't swiped back yet."""
        token = create_access_token(user_a.id)
        
        response = await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["swiper_pet_id"] == str(dog_buddy.id)
        assert data["target_pet_id"] == str(dog_max.id)
        assert data["action"] == "like"
        assert data["is_match"] is False
        assert data["match_id"] is None
        
        # Verify swipe was recorded
        result = await db.execute(
            select(Swipe).where(
                Swipe.swiper_pet_id == dog_buddy.id,
                Swipe.target_pet_id == dog_max.id,
            )
        )
        swipe = result.scalar_one_or_none()
        assert swipe is not None
        assert swipe.action == SwipeAction.LIKE

    async def test_swipe_creates_match(
        self,
        client: AsyncClient,
        db: AsyncSession,
        user_a: User,
        user_b: User,
        dog_buddy: PetProfile,
        dog_max: PetProfile,
    ):
        """Test that mutual likes create a match."""
        # User A swipes right on Max
        token_a = create_access_token(user_a.id)
        await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        
        # User B swipes right on Buddy - should create match
        token_b = create_access_token(user_b.id)
        response = await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_max.id),
                "target_pet_id": str(dog_buddy.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_b}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_match"] is True
        assert data["match_id"] is not None
        
        # Verify match was created
        result = await db.execute(select(Match))
        matches = result.scalars().all()
        assert len(matches) == 1
        
        # Verify both users got notifications
        result = await db.execute(
            select(Notification).where(
                Notification.user_id.in_([user_a.id, user_b.id])
            )
        )
        notifications = result.scalars().all()
        assert len(notifications) == 2

    async def test_swipe_species_mismatch(
        self,
        client: AsyncClient,
        user_a: User,
        dog_buddy: PetProfile,
        cat_whiskers: PetProfile,
    ):
        """Test that dogs can't swipe on cats."""
        token = create_access_token(user_a.id)
        
        response = await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(cat_whiskers.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 400
        assert "species mismatch" in response.json()["detail"].lower()

    async def test_swipe_own_pet(
        self,
        client: AsyncClient,
        user_a: User,
        dog_buddy: PetProfile,
    ):
        """Test that you can't swipe on your own pet."""
        token = create_access_token(user_a.id)
        
        response = await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_buddy.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 400
        assert "own pet" in response.json()["detail"].lower()

    async def test_swipe_duplicate(
        self,
        client: AsyncClient,
        user_a: User,
        dog_buddy: PetProfile,
        dog_max: PetProfile,
    ):
        """Test that you can't swipe on the same pet twice."""
        token = create_access_token(user_a.id)
        
        # First swipe - should succeed
        response = await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        
        # Second swipe - should fail
        response = await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "already swiped" in response.json()["detail"].lower()

    async def test_swipe_skip(
        self,
        client: AsyncClient,
        db: AsyncSession,
        user_a: User,
        dog_buddy: PetProfile,
        dog_max: PetProfile,
    ):
        """Test left swipe (skip) - should not create match."""
        token = create_access_token(user_a.id)
        
        response = await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "skip",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "skip"
        assert data["is_match"] is False
        
        # Verify swipe was recorded as SKIP
        result = await db.execute(
            select(Swipe).where(
                Swipe.swiper_pet_id == dog_buddy.id,
                Swipe.target_pet_id == dog_max.id,
            )
        )
        swipe = result.scalar_one_or_none()
        assert swipe is not None
        assert swipe.action == SwipeAction.SKIP


class TestMatchesEndpoint:
    """Tests for GET /matches/my-matches endpoint."""

    async def test_get_matches_empty(
        self,
        client: AsyncClient,
        user_a: User,
        dog_buddy: PetProfile,
    ):
        """Test getting matches when there are none."""
        token = create_access_token(user_a.id)
        
        response = await client.get(
            "/matches/my-matches",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_matches_after_match(
        self,
        client: AsyncClient,
        db: AsyncSession,
        user_a: User,
        user_b: User,
        dog_buddy: PetProfile,
        dog_max: PetProfile,
    ):
        """Test getting matches after creating one."""
        # Create mutual likes
        token_a = create_access_token(user_a.id)
        token_b = create_access_token(user_b.id)
        
        await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        
        await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_max.id),
                "target_pet_id": str(dog_buddy.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_b}"},
        )
        
        # User A checks matches
        response = await client.get(
            "/matches/my-matches",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        
        assert response.status_code == 200
        matches = response.json()
        assert len(matches) == 1
        assert str(dog_buddy.id) in [matches[0]["pet1_id"], matches[0]["pet2_id"]]
        assert str(dog_max.id) in [matches[0]["pet1_id"], matches[0]["pet2_id"]]


class TestNotificationsEndpoint:
    """Tests for notification endpoints."""

    async def test_get_notifications_after_match(
        self,
        client: AsyncClient,
        user_a: User,
        user_b: User,
        dog_buddy: PetProfile,
        dog_max: PetProfile,
    ):
        """Test getting notifications after a match is created."""
        # Create match
        token_a = create_access_token(user_a.id)
        token_b = create_access_token(user_b.id)
        
        await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        
        await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_max.id),
                "target_pet_id": str(dog_buddy.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_b}"},
        )
        
        # User A checks notifications
        response = await client.get(
            "/matches/notifications",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        
        assert response.status_code == 200
        notifications = response.json()
        assert len(notifications) == 1
        assert notifications[0]["notification_type"] == "new_match"
        assert notifications[0]["is_read"] is False
        assert "match" in notifications[0]["message"].lower()

    async def test_mark_notifications_read(
        self,
        client: AsyncClient,
        db: AsyncSession,
        user_a: User,
        user_b: User,
        dog_buddy: PetProfile,
        dog_max: PetProfile,
    ):
        """Test marking notifications as read."""
        # Create match
        token_a = create_access_token(user_a.id)
        token_b = create_access_token(user_b.id)
        
        await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_buddy.id),
                "target_pet_id": str(dog_max.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        
        await client.post(
            "/matches/swipe",
            json={
                "pet_id": str(dog_max.id),
                "target_pet_id": str(dog_buddy.id),
                "action": "like",
            },
            headers={"Authorization": f"Bearer {token_b}"},
        )
        
        # Get notifications
        response = await client.get(
            "/matches/notifications",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        notifications = response.json()
        notif_id = notifications[0]["id"]
        
        # Mark as read
        response = await client.patch(
            "/matches/notifications/read",
            json={"notification_ids": [notif_id]},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        
        assert response.status_code == 204
        
        # Verify it's marked as read
        result = await db.execute(
            select(Notification).where(Notification.id == uuid.UUID(notif_id))
        )
        notif = result.scalar_one()
        assert notif.is_read is True
        assert notif.read_at is not None
