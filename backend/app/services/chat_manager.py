import asyncio
import json
import uuid
from typing import Dict, Set

from fastapi import WebSocket
from redis.asyncio import Redis


class ConnectionManager:
    """Manages WebSocket connections with Redis pub/sub for horizontal scaling"""
    
    def __init__(self):
        # Store active connections: {match_id: {pet_id: WebSocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # Redis pub/sub for cross-instance communication
        self.redis_client: Redis | None = None
        self.pubsub_task: asyncio.Task | None = None
        
    async def initialize(self, redis: Redis):
        """Initialize Redis pub/sub"""
        self.redis_client = redis
        # Start listening to pub/sub
        self.pubsub_task = asyncio.create_task(self._listen_to_redis())
    
    async def connect(self, websocket: WebSocket, match_id: str, pet_id: str):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        
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
        """Broadcast message to all instances via Redis pub/sub"""
        if self.redis_client:
            await self.redis_client.publish(
                f"chat:{match_id}",
                json.dumps(message)
            )
    
    async def _listen_to_redis(self):
        """Listen to Redis pub/sub for messages from other instances"""
        if not self.redis_client:
            return
        
        pubsub = self.redis_client.pubsub()
        
        # Subscribe to pattern for all match channels
        await pubsub.psubscribe("chat:*")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                    match_id = channel.replace("chat:", "")
                    data = json.loads(message["data"])
                    
                    # Send to local connections
                    await self.send_to_match(match_id, data)
        except asyncio.CancelledError:
            await pubsub.punsubscribe("chat:*")
            await pubsub.close()
    
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
