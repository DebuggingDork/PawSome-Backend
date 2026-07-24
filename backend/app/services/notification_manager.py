import asyncio
import json
from typing import Dict

from fastapi import WebSocket
from redis.asyncio import Redis


class NotificationManager:
    """Pushes notifications (new like, new match, new message) to connected
    users in real time over WebSocket, via Redis pub/sub — same shape as
    ConnectionManager in chat_manager.py, just keyed by user_id instead of
    (match_id, pet_id) since notifications belong to a person, not a chat."""

    def __init__(self):
        # {user_id: WebSocket} — one notification connection per signed-in user.
        self.active_connections: Dict[str, WebSocket] = {}
        self.redis_client: Redis | None = None
        self.pubsub_task: asyncio.Task | None = None

    async def initialize(self, redis: Redis):
        self.redis_client = redis
        self.pubsub_task = asyncio.create_task(self._listen_to_redis())

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, payload: dict):
        websocket = self.active_connections.get(user_id)
        if websocket is None:
            return
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            self.disconnect(user_id)

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
