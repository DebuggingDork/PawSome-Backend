import asyncio
import json
import logging
import uuid
from typing import Dict, Set

from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Same purpose as chat_manager's: tags what this process published so the
# listener can skip its own echo. Regenerated per process start.
INSTANCE_ID = uuid.uuid4().hex


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
        """Attach Redis and start the fan-out listener.

        Idempotent, because this is now called once at startup *and* defensively
        from the WebSocket route. It used to be called only from the route, so
        on a worker where nobody had yet opened a notification socket
        `redis_client` was None and every broadcast_to_user() silently returned
        without publishing anything — a like or match notification that was
        saved to the database but never pushed to anyone.
        """
        if self.redis_client is not None:
            return
        self.redis_client = redis
        self.pubsub_task = asyncio.create_task(self._listen_to_redis())
        logger.info("notification fan-out initialised")

    async def connect(self, websocket: WebSocket, user_id: str):
        """Register an already-accepted WebSocket — the caller owns the accept,
        so the handshake completes before the database and Redis setup."""
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
        instance their WebSocket happens to be connected to.

        Delivers locally first so a Redis problem can't stop a push to someone
        connected to this very process — the same ordering chat_manager uses,
        and for the same reason.
        """
        await self.send_to_user(user_id, payload)

        if not self.redis_client:
            logger.error(
                "notification fan-out is not initialised — user %s gets no live "
                "push for %s (the row is saved and will appear on next fetch)",
                user_id, payload.get("data", {}).get("notification_type", "?"),
            )
            return

        try:
            # _origin lets our own listener recognise this instance's echo and
            # skip it, since those sockets were already served above.
            await self.redis_client.publish(
                f"notif:{user_id}", json.dumps({**payload, "_origin": INSTANCE_ID})
            )
        except Exception:
            logger.warning(
                "notification: Redis publish failed for user %s — anyone connected "
                "to another instance won't see it live",
                user_id, exc_info=True,
            )

    async def _listen_to_redis(self):
        """Same resubscribe-on-failure pattern as ConnectionManager — see
        chat_manager.py for why this matters (a dropped pub/sub connection
        used to kill delivery silently until the process restarted)."""
        if not self.redis_client:
            return

        while True:
            # Dedicated subscriber client — see app/core/redis.py for why the
            # command client's 5s socket timeout can't be used here.
            from app.core.redis import pubsub_redis_client

            pubsub = pubsub_redis_client.pubsub()
            try:
                await pubsub.psubscribe("notif:*")
                async for message in pubsub.listen():
                    if message["type"] == "pmessage":
                        channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                        user_id = channel.replace("notif:", "")
                        data = json.loads(message["data"])

                        # Our own publish — broadcast_to_user already served
                        # this instance's sockets, so re-delivering would show
                        # the user every notification twice.
                        if data.pop("_origin", None) == INSTANCE_ID:
                            continue

                        await self.send_to_user(user_id, data)
            except asyncio.CancelledError:
                await pubsub.punsubscribe("notif:*")
                await pubsub.close()
                return
            except Exception:
                # Logged, not swallowed: a dead subscription means notifications
                # published by other instances stop arriving entirely, and this
                # loop retried forever without leaving any trace of why.
                logger.warning(
                    "notification pub/sub dropped, resubscribing in 1s", exc_info=True
                )
                await pubsub.close()
                await asyncio.sleep(1)


# Global instance
manager = NotificationManager()
