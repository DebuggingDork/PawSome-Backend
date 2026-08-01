import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Set

from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Identifies this process among however many are running, so the pub/sub
# listener can tell its own echo apart from a genuine message off another
# instance. Regenerated per process start, which is exactly the lifetime we want.
INSTANCE_ID = uuid.uuid4().hex

# ── Presence ──────────────────────────────────────────────────────────────────
#
# `presence:{pet_id}` is a sorted set of connection ids scored by the epoch
# second that connection was last heard from. Not a plain key with a TTL, which
# is what this replaced and which was wrong in both directions: the TTL was set
# once at connect and never refreshed, so anyone still connected went "offline"
# after five minutes, and the key was never removed on disconnect, so anyone who
# left stayed "online" until it expired.
#
# A set rather than a counter because a pet can legitimately have several live
# sockets — two tabs, phone and laptop, a reconnect that overlaps the socket it
# replaced. Refcounting with INCR/DECR cannot survive a process dying between
# the two, and would drift permanently negative or positive; membership can be
# rebuilt from whoever is still checking in, so it self-heals.
#
# Scored by last-seen so an abrupt disconnect (killed tab, dead network, zombie
# socket the browser never reported) needs no cleanup to be handled: the member
# simply stops being refreshed and ages out of the window on the next read.
#
# The client heartbeats every 20s (HEARTBEAT_MS in the frontend's chat.ts), so
# 60s is three missed beats before a connection is presumed gone — long enough
# to ride out a slow round trip, short enough that "online" means something.
PRESENCE_STALE_AFTER = 60
# Hard backstop on the key itself, so a pet whose every connection vanished
# without cleanup cannot leave a sorted set behind forever. Comfortably longer
# than the staleness window: pruning is what decides presence, this only decides
# when the key stops existing at all.
PRESENCE_KEY_TTL = 300


def _presence_key(pet_id: str) -> str:
    return f"presence:{pet_id}"


class ConnectionManager:
    """Manages WebSocket connections with Redis pub/sub for horizontal scaling"""
    
    def __init__(self):
        # Store active connections: {match_id: {pet_id: WebSocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # Redis pub/sub for cross-instance communication
        self.redis_client: Redis | None = None
        self.pubsub_task: asyncio.Task | None = None
        
    async def initialize(self, redis: Redis):
        """Initialize Redis pub/sub.

        Idempotent — called once at startup and defensively from the WebSocket
        route, which would otherwise start a second listener task per socket.
        """
        if self.redis_client is not None:
            return
        self.redis_client = redis
        # Start listening to pub/sub
        self.pubsub_task = asyncio.create_task(self._listen_to_redis())
        logger.info("chat fan-out initialised")
    
    async def connect(
        self,
        websocket: WebSocket,
        match_id: str,
        pet_id: str,
        connection_id: str | None = None,
    ):
        """Register an already-accepted WebSocket.

        The caller accepts the handshake itself, before the authorisation and
        Redis work — accepting in here meant the client sat in CONNECTING for
        the whole of that setup.
        """
        if match_id not in self.active_connections:
            self.active_connections[match_id] = {}

        self.active_connections[match_id][pet_id] = websocket

        if connection_id:
            await self.mark_online(pet_id, connection_id)

    def disconnect(self, match_id: str, pet_id: str, websocket: WebSocket | None = None):
        """Remove a WebSocket connection from this instance's routing table.

        `websocket` identifies *which* connection is going away. Without it, a
        socket that was already replaced — an overlapping reconnect, a second
        tab on the same match — deregisters whichever one currently holds the
        slot, including a live one that just took its place. When it is passed,
        a stale socket cleaning itself up leaves the current one alone.

        Presence is separate and lives in Redis; see `mark_offline`.
        """
        if match_id not in self.active_connections:
            return

        current = self.active_connections[match_id].get(pet_id)
        if current is None:
            return
        if websocket is not None and current is not websocket:
            return

        self.active_connections[match_id].pop(pet_id, None)
        if not self.active_connections[match_id]:
            del self.active_connections[match_id]

    async def mark_online(self, pet_id: str, connection_id: str) -> None:
        """Record this connection as live, or refresh how recently it was seen.

        Called once on connect and again on every client heartbeat, which is why
        it is a single idempotent ZADD rather than separate add/refresh paths —
        re-adding an existing member just updates its score.
        """
        if not self.redis_client:
            return
        key = _presence_key(pet_id)
        try:
            now = int(time.time())
            pipe = self.redis_client.pipeline()
            pipe.zadd(key, {connection_id: now})
            pipe.expire(key, PRESENCE_KEY_TTL)
            await pipe.execute()
        except Exception:
            # Presence is a label on a chat header. It must never be the reason
            # a message fails to send or a socket fails to open.
            logger.warning("presence: could not mark %s online", pet_id, exc_info=True)

    async def mark_offline(self, pet_id: str, connection_id: str) -> None:
        """Drop one connection from a pet's presence set.

        Only this connection. Any other socket the same pet still has open
        keeps them online, which is the whole reason presence is a set of
        connection ids and not a boolean.
        """
        if not self.redis_client:
            return
        key = _presence_key(pet_id)
        try:
            pipe = self.redis_client.pipeline()
            pipe.zrem(key, connection_id)
            pipe.zcard(key)
            _, remaining = await pipe.execute()
            if not remaining:
                await self.redis_client.delete(key)
        except Exception:
            # Worst case this connection ages out of the window on its own,
            # which is the same path an abrupt disconnect already takes.
            logger.warning("presence: could not mark %s offline", pet_id, exc_info=True)
    
    async def send_to_match(self, match_id: str, message: dict, exclude_pet: str | None = None):
        """Send message to all connected users in a match (local instance only)"""
        if match_id not in self.active_connections:
            return

        message_text = json.dumps(message)

        for pet_id, websocket in list(self.active_connections[match_id].items()):
            if exclude_pet and pet_id == exclude_pet:
                continue

            try:
                await websocket.send_text(message_text)
            except Exception:
                # Connection broken, remove it — passing the socket so this
                # cannot evict a newer one that replaced it in the meantime.
                self.disconnect(match_id, pet_id, websocket)
    
    async def broadcast_message(self, match_id: str, message: dict):
        """Deliver to this instance's sockets, then fan out to the others.

        Local delivery goes first and does not depend on Redis. Every message
        used to be published to Redis and only reached the sockets when it came
        back through the pub/sub listener — so a message between two people
        connected to *this* process still made a full round trip to a remote
        Redis before either of them saw it, and if that subscription was
        unhealthy the message never arrived at all despite having been saved.
        """
        await self.send_to_match(match_id, message)

        if not self.redis_client:
            return

        try:
            # _origin lets the listener recognise its own echo and skip it,
            # since those sockets were served above.
            await self.redis_client.publish(
                f"chat:{match_id}",
                json.dumps({**message, "_origin": INSTANCE_ID}),
            )
        except Exception:
            # Other instances miss this one, but everyone connected here has
            # it already and it's committed to the database either way — far
            # better than failing the send outright.
            logger.warning("chat: Redis publish failed for match %s", match_id, exc_info=True)
    
    async def _listen_to_redis(self):
        """Listen to Redis pub/sub for messages from other instances.

        Reconnects on any non-cancellation error instead of letting the task
        die silently — a dropped pub/sub connection (idle timeout, brief
        network blip) used to kill this loop for good, breaking realtime
        message delivery for every match until the process was restarted,
        even though messages kept saving fine via the REST/WS handlers."""
        if not self.redis_client:
            return

        while True:
            # Dedicated subscriber client — see app/core/redis.py for why the
            # command client's 5s socket timeout can't be used here.
            from app.core.redis import pubsub_redis_client

            pubsub = pubsub_redis_client.pubsub()
            try:
                await pubsub.psubscribe("chat:*")
                async for message in pubsub.listen():
                    if message["type"] == "pmessage":
                        channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                        match_id = channel.replace("chat:", "")
                        data = json.loads(message["data"])

                        # Our own publish coming back around: broadcast_message
                        # already served this instance's sockets before sending
                        # it, so re-delivering would duplicate every message.
                        if data.pop("_origin", None) == INSTANCE_ID:
                            continue

                        # Send to local connections
                        await self.send_to_match(match_id, data)
            except asyncio.CancelledError:
                await pubsub.punsubscribe("chat:*")
                await pubsub.close()
                return
            except Exception:
                await pubsub.close()
                await asyncio.sleep(1)  # brief backoff, then resubscribe
    
    async def is_pet_online(self, pet_id: str) -> bool:
        """Is any live connection for this pet checking in, on any instance?

        Prunes on read rather than on a timer. A connection that died without
        cleanup — killed tab, dropped network, a zombie socket the browser never
        reported closed — leaves its member behind with a score that stops
        advancing, and this is where it gets dropped. That means no background
        sweeper and no per-user timers: the only thing that ever needs to know
        is the request asking.
        """
        if not self.redis_client:
            return False
        key = _presence_key(pet_id)
        try:
            cutoff = int(time.time()) - PRESENCE_STALE_AFTER
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, "-inf", cutoff)
            pipe.zcard(key)
            _, live = await pipe.execute()
            return bool(live)
        except Exception:
            logger.warning("presence: could not read %s", pet_id, exc_info=True)
            return False
    
    def get_local_connections(self, match_id: str) -> Set[str]:
        """Get pet IDs connected to this instance for a match"""
        return set(self.active_connections.get(match_id, {}).keys())


# Global instance
manager = ConnectionManager()
