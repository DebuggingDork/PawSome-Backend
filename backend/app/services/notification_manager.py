import asyncio
import json
from typing import Dict, Set

from fastapi import WebSocket
from redis.asyncio import Redis


class NotificationManager:
    """Pushes notifications (new like, new match, new message) to connected
    users in real time over WebSocket, via Redis pub/sub — same shape as
    ConnectionManager in chat_manager.py, just keyed by user_id instead of
    (match_id, pet_id) since notifications belong to a person, not a chat."""

    def __init__(self):
        # {user_id: {WebSocket, ...}} — a signed-in user can legitimately hold
        # more than one live connection at once (multiple tabs/devices, or on
        # this app specifically, the desktop and mobile navbars each mounting
        # their own NotificationBell at the same time regardless of viewport).
        # A single-slot dict here used to mean the second connection silently
        # stole the first one's spot, and either socket disconnecting could
        # pop the *other*, still-live one out of the map — killing delivery
        # to a tab that was never closed.
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.redis_client: Redis | None = None
        self.pubsub_task: asyncio.Task | None = None

    async def initialize(self, redis: Redis):
        self.redis_client = redis
        self.pubsub_task = asyncio.create_task(self._listen_to_redis())

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        sockets = self.active_connections.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, payload: dict):
        sockets = self.active_connections.get(user_id)
        if not sockets:
            return
        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(user_id, websocket)

    async def broadcast_to_user(self, user_id: str, payload: dict):
        """Publish via Redis so the push reaches the user regardless of which
        instance their WebSocket happens to be connected to."""
        if self.redis_client:
            await self.redis_client.publish(f"notif:{user_id}", json.dumps(payload))

    async def _listen_to_redis(self):
        """Same resubscribe-on-failure pattern as ConnectionManager — see
        chat_manager.py for why this matters (a dropped pub/sub connection
        used to kill delivery silently until the process restarted)."""
        if not self.redis_client:
            return

        while True:
            pubsub = self.redis_client.pubsub()
            try:
                await pubsub.psubscribe("notif:*")
                async for message in pubsub.listen():
                    if message["type"] == "pmessage":
                        channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                        user_id = channel.replace("notif:", "")
                        data = json.loads(message["data"])
                        await self.send_to_user(user_id, data)
            except asyncio.CancelledError:
                await pubsub.punsubscribe("notif:*")
                await pubsub.close()
                return
            except Exception:
                await pubsub.close()
                await asyncio.sleep(1)


# Global instance
manager = NotificationManager()
