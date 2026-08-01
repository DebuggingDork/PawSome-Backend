"""
Focused runtime tests for Redis presence functionality.

Tests the new sorted-set based presence tracking that distinguishes:
1. Generic presence (pet is online somewhere)
2. Active-match presence (pet is viewing a specific conversation)

These tests require a running Redis instance (configured via .env).
"""
import asyncio
import time
import uuid
from redis.asyncio import Redis

# Make the backend root importable so `app.*` resolves when this file is run
# directly as a script from anywhere.
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.config import settings
from app.services.chat_manager import (
    ConnectionManager,
    PRESENCE_STALE_AFTER,
    _presence_key,
    _match_presence_key,
)


async def test_presence_multi_connection():
    """Two connections for same pet → both tracked, removing one keeps pet online."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)
    
    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    conn1 = f"conn-{uuid.uuid4().hex[:8]}"
    conn2 = f"conn-{uuid.uuid4().hex[:8]}"
    
    try:
        # Add two connections
        await manager.mark_online(pet_id, conn1)
        await manager.mark_online(pet_id, conn2)
        
        # Pet should be online
        assert await manager.is_pet_online(pet_id), "Pet should be online with 2 connections"
        
        # Verify both members exist
        key = _presence_key(pet_id)
        members = await redis.zrange(key, 0, -1)
        assert conn1 in members, "Connection 1 should be in set"
        assert conn2 in members, "Connection 2 should be in set"
        
        # Remove one connection
        await manager.mark_offline(pet_id, conn1)
        
        # Pet should still be online
        assert await manager.is_pet_online(pet_id), "Pet should still be online with 1 connection"
        
        # Verify only one member remains
        members = await redis.zrange(key, 0, -1)
        assert conn1 not in members, "Connection 1 should be removed"
        assert conn2 in members, "Connection 2 should remain"
        
        # Remove second connection
        await manager.mark_offline(pet_id, conn2)
        
        # Pet should now be offline
        assert not await manager.is_pet_online(pet_id), "Pet should be offline with no connections"
        
        # Key should be deleted
        exists = await redis.exists(key)
        assert exists == 0, "Key should be deleted when empty"
        
        print("✓ Multi-connection tracking works correctly")
        
    finally:
        # Cleanup
        await redis.delete(_presence_key(pet_id))
        await redis.aclose()


async def test_presence_stale_pruning():
    """Stale connections are pruned on read."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)
    
    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    conn_id = f"conn-{uuid.uuid4().hex[:8]}"
    
    try:
        # Add connection with old timestamp
        key = _presence_key(pet_id)
        old_timestamp = int(time.time()) - PRESENCE_STALE_AFTER - 10
        await redis.zadd(key, {conn_id: old_timestamp})
        await redis.expire(key, 300)
        
        # Reading should prune it
        is_online = await manager.is_pet_online(pet_id)
        assert not is_online, "Pet should be offline due to stale timestamp"
        
        # Key should be deleted
        exists = await redis.exists(key)
        assert exists == 0, "Key should be deleted after pruning stale member"
        
        print("✓ Stale connection pruning works correctly")
        
    finally:
        await redis.delete(_presence_key(pet_id))
        await redis.aclose()


async def test_presence_fresh_connection():
    """Fresh connection within staleness window is online."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)
    
    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    conn_id = f"conn-{uuid.uuid4().hex[:8]}"
    
    try:
        # Add connection with recent timestamp (40s ago, within 60s window)
        key = _presence_key(pet_id)
        recent_timestamp = int(time.time()) - 40
        await redis.zadd(key, {conn_id: recent_timestamp})
        await redis.expire(key, 300)
        
        # Should still be online
        is_online = await manager.is_pet_online(pet_id)
        assert is_online, "Pet should be online within staleness window"
        
        print("✓ Fresh connection within window is online")
        
    finally:
        await redis.delete(_presence_key(pet_id))
        await redis.aclose()


async def test_match_presence_separate_tracking():
    """Match-specific presence is tracked separately from generic presence."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)
    
    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    match1 = f"match-{uuid.uuid4().hex[:8]}"
    match2 = f"match-{uuid.uuid4().hex[:8]}"
    conn1 = f"conn-{uuid.uuid4().hex[:8]}"
    conn2 = f"conn-{uuid.uuid4().hex[:8]}"
    
    try:
        # Pet active in match1
        await manager.mark_online(pet_id, conn1, match1)
        
        # Should be online generally
        assert await manager.is_pet_online(pet_id), "Pet should be online"
        # Should be in match1
        assert await manager.is_pet_in_match(match1, pet_id), "Pet should be in match1"
        # Should NOT be in match2
        assert not await manager.is_pet_in_match(match2, pet_id), "Pet should NOT be in match2"
        
        # Add second connection in match2
        await manager.mark_online(pet_id, conn2, match2)
        
        # Should be in both matches
        assert await manager.is_pet_in_match(match1, pet_id), "Pet should still be in match1"
        assert await manager.is_pet_in_match(match2, pet_id), "Pet should now be in match2"
        
        # Remove from match1
        await manager.mark_offline(pet_id, conn1, match1)
        
        # Should NOT be in match1 anymore
        assert not await manager.is_pet_in_match(match1, pet_id), "Pet should NOT be in match1 after disconnect"
        # Should still be in match2
        assert await manager.is_pet_in_match(match2, pet_id), "Pet should still be in match2"
        # Should still be online generally
        assert await manager.is_pet_online(pet_id), "Pet should still be online"
        
        print("✓ Match-specific presence tracking works correctly")
        
    finally:
        await redis.delete(_presence_key(pet_id))
        await redis.delete(_match_presence_key(match1, pet_id))
        await redis.delete(_match_presence_key(match2, pet_id))
        await redis.aclose()


async def test_match_presence_consistency():
    """Generic and match presence refreshed together remain consistent."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)
    
    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    match_id = f"match-{uuid.uuid4().hex[:8]}"
    conn_id = f"conn-{uuid.uuid4().hex[:8]}"
    
    try:
        # Single heartbeat updates both
        await manager.mark_online(pet_id, conn_id, match_id)
        
        # Both should be fresh
        generic_key = _presence_key(pet_id)
        match_key = _match_presence_key(match_id, pet_id)
        
        generic_score = await redis.zscore(generic_key, conn_id)
        match_score = await redis.zscore(match_key, conn_id)
        
        assert generic_score is not None, "Generic presence should exist"
        assert match_score is not None, "Match presence should exist"
        assert abs(generic_score - match_score) < 2, "Timestamps should be identical or nearly so"
        
        # Wait 2 seconds, refresh again
        await asyncio.sleep(2)
        await manager.mark_online(pet_id, conn_id, match_id)
        
        new_generic_score = await redis.zscore(generic_key, conn_id)
        new_match_score = await redis.zscore(match_key, conn_id)
        
        assert new_generic_score > generic_score, "Generic timestamp should be updated"
        assert new_match_score > match_score, "Match timestamp should be updated"
        assert abs(new_generic_score - new_match_score) < 2, "New timestamps should be consistent"
        
        print("✓ Generic and match presence remain consistent")
        
    finally:
        await redis.delete(_presence_key(pet_id))
        await redis.delete(_match_presence_key(match_id, pet_id))
        await redis.aclose()


async def test_match_presence_stale():
    """Expired/stale match presence returns false."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)
    
    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    match_id = f"match-{uuid.uuid4().hex[:8]}"
    conn_id = f"conn-{uuid.uuid4().hex[:8]}"
    
    try:
        # Add stale match presence
        key = _match_presence_key(match_id, pet_id)
        old_timestamp = int(time.time()) - PRESENCE_STALE_AFTER - 10
        await redis.zadd(key, {conn_id: old_timestamp})
        await redis.expire(key, 300)
        
        # Should return false
        is_in_match = await manager.is_pet_in_match(match_id, pet_id)
        assert not is_in_match, "Stale match presence should return false"
        
        # Key should be deleted after pruning
        exists = await redis.exists(key)
        assert exists == 0, "Key should be deleted after pruning"
        
        print("✓ Stale match presence correctly returns false")
        
    finally:
        await redis.delete(_match_presence_key(match_id, pet_id))
        await redis.aclose()


async def test_two_tabs_same_match():
    """Same pet in the same match from two tabs: removing one connection
    keeps the pet present in the match; removing both takes them out."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)

    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    match_id = f"match-{uuid.uuid4().hex[:8]}"
    conn1 = f"conn-{uuid.uuid4().hex[:8]}"
    conn2 = f"conn-{uuid.uuid4().hex[:8]}"

    try:
        await manager.mark_online(pet_id, conn1, match_id)
        await manager.mark_online(pet_id, conn2, match_id)

        assert await manager.is_pet_in_match(match_id, pet_id), "Pet should be in match with 2 tabs"

        # Close one tab
        await manager.mark_offline(pet_id, conn1, match_id)
        assert await manager.is_pet_in_match(match_id, pet_id), "Pet should still be in match with 1 tab"
        assert await manager.is_pet_online(pet_id), "Pet should still be online"

        # Close the other tab
        await manager.mark_offline(pet_id, conn2, match_id)
        assert not await manager.is_pet_in_match(match_id, pet_id), "Pet should be out of match with 0 tabs"
        assert not await manager.is_pet_online(pet_id), "Pet should be offline"

        print("\u2713 Two tabs on the same match tracked independently")

    finally:
        await redis.delete(_presence_key(pet_id))
        await redis.delete(_match_presence_key(match_id, pet_id))
        await redis.aclose()


async def test_connect_registers_match_presence():
    """connect() must register match presence immediately, not only after the
    first heartbeat ping ~20s later — otherwise a reply arriving in that window
    still raises a redundant notification for a thread already on screen."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manager = ConnectionManager()
    await manager.initialize(redis)

    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    match_id = f"match-{uuid.uuid4().hex[:8]}"
    conn_id = f"conn-{uuid.uuid4().hex[:8]}"

    class _FakeWebSocket:
        pass

    try:
        await manager.connect(_FakeWebSocket(), match_id, pet_id, conn_id)

        assert await manager.is_pet_online(pet_id), "Pet should be online right after connect"
        assert await manager.is_pet_in_match(match_id, pet_id), (
            "Pet should be present in the match right after connect, before any ping"
        )

        print("\u2713 connect() registers match presence immediately")

    finally:
        await redis.delete(_presence_key(pet_id))
        await redis.delete(_match_presence_key(match_id, pet_id))
        await redis.aclose()


async def test_cross_instance_match_presence():
    """Presence written by one backend instance is visible from another.

    Two ConnectionManager instances with independent Redis clients stand in
    for two backend processes. The NEW_MESSAGE suppression check on instance B
    must see a recipient whose socket lives on instance A."""
    redis_a = Redis.from_url(settings.redis_url, decode_responses=True)
    redis_b = Redis.from_url(settings.redis_url, decode_responses=True)
    manager_a = ConnectionManager()
    manager_b = ConnectionManager()
    await manager_a.initialize(redis_a)
    await manager_b.initialize(redis_b)

    pet_id = f"test-pet-{uuid.uuid4().hex[:8]}"
    match_id = f"match-{uuid.uuid4().hex[:8]}"
    conn_id = f"conn-{uuid.uuid4().hex[:8]}"

    try:
        # Socket connects on instance A
        await manager_a.mark_online(pet_id, conn_id, match_id)

        # Instance B, handling the sender's message, must see the recipient
        assert await manager_b.is_pet_online(pet_id), "Instance B should see pet online"
        assert await manager_b.is_pet_in_match(match_id, pet_id), (
            "Instance B should see pet present in the match via shared Redis"
        )

        # Disconnect on A → gone everywhere
        await manager_a.mark_offline(pet_id, conn_id, match_id)
        assert not await manager_b.is_pet_in_match(match_id, pet_id), (
            "Instance B should see pet gone after disconnect on A"
        )

        print("\u2713 Match presence is respected across backend instances")

    finally:
        await redis_a.delete(_presence_key(pet_id))
        await redis_a.delete(_match_presence_key(match_id, pet_id))
        await redis_a.aclose()
        await redis_b.aclose()


async def run_all_tests():
    """Run all presence tests."""
    print("\n=== Running Redis Presence Tests ===\n")
    
    tests = [
        ("Multi-connection tracking", test_presence_multi_connection),
        ("Stale connection pruning", test_presence_stale_pruning),
        ("Fresh connection check", test_presence_fresh_connection),
        ("Match-specific tracking", test_match_presence_separate_tracking),
        ("Presence consistency", test_match_presence_consistency),
        ("Stale match presence", test_match_presence_stale),
        ("Two tabs same match", test_two_tabs_same_match),
        ("Connect registers match presence", test_connect_registers_match_presence),
        ("Cross-instance match presence", test_cross_instance_match_presence),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            print(f"✗ {name} FAILED: {e}")
            failed += 1
    
    print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
