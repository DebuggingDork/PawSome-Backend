import asyncio
import json
import logging
import uuid
from typing import Dict, Set

from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Identifies this process among however many are running, so the pub/sub
# listener can tell its own echo apart from a genuine message off another
# instance. Regenerated per process start, which is exactly the lifetime we want.
INSTANCE_ID = uuid.uuid4().hex


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
    
    async def connect(self, websocket: WebSocket, match_id: str, pet_id: str):
        """Register an already-accepted WebSocket.

        The caller accepts the handshake itself, before the authorisation and
        Redis work — accepting in here meant the client sat in CONNECTING for
        the whole of that setup.
        """
        if match_id not in self.active_connections:
            self.active_connections[match_id] = {}

        self.active_connections[match_id][pet_id] = websocket
        
        # Set online status in Redis
        if self.redis_client:
            await self.redis_client.setex(
                f"online:{pet_id}", 
                300,  # 5 min expiry
                "1"
            )
    
    def disconnect(self, match_id: str, pet_id: str):
        """Remove WebSocket connection"""
        if match_id in self.active_connections:
            self.active_connections[match_id].pop(pet_id, None)
            if not self.active_connections[match_id]:
                del self.active_connections[match_id]
    
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
                # Connection broken, remove it
                self.disconnect(match_id, pet_id)
    
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
        """Check if a pet is online (any instance)"""
        if not self.redis_client:
            return False
        result = await self.redis_client.get(f"online:{pet_id}")
        return result is not None
    
    def get_local_connections(self, match_id: str) -> Set[str]:
        """Get pet IDs connected to this instance for a match"""
        return set(self.active_connections.get(match_id, {}).keys())


# Global instance
manager = ConnectionManager()
