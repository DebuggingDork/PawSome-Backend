# WebSocket Chat System

## Architecture

**Horizontally Scalable** - Uses Redis pub/sub for cross-instance messaging.

```
Client A (Instance 1) → WebSocket → Redis Pub/Sub → Instance 2 → Client B
```

## Endpoints

### WebSocket Connection
```
ws://localhost:8000/chat/ws/{match_id}?token={jwt_access_token}
```

**Client → Server Messages:**
```json
// Send message
{"type": "message", "content": "Hello!", "msg_type": "text"}

// Typing indicator
{"type": "typing", "is_typing": true}
```

**Server → Client Messages:**
```json
// New message
{
  "type": "message",
  "data": {
    "id": "uuid",
    "match_id": "uuid",
    "sender_pet_id": "uuid",
    "content": "Hello!",
    "msg_type": "text",
    "created_at": "2026-06-13T01:00:00Z"
  }
}

// Typing indicator
{
  "type": "typing",
  "data": {
    "pet_id": "uuid",
    "is_typing": true
  }
}
```

### REST Endpoints

**Get Chat History**
```
GET /chat/{match_id}/history?limit=50&before={message_id}
```
Returns messages newest first. Use `before` param for pagination.

**Get Chat Status**
```
GET /chat/{match_id}/status
```
Returns online status and message count.

## Flow

1. Users match (from `/matches/swipe`)
2. Open WebSocket: `ws://localhost:8000/chat/ws/{match_id}?token=xyz`
3. Send/receive messages in real-time
4. Messages saved to DB + broadcast via Redis to all instances
5. Typing indicators broadcast but not saved

## Security

- JWT token required in query param
- Verify user is part of the match
- Only active pets can chat
- Messages soft-deleted (is_deleted flag)

## Database

**messages table:**
- id, match_id, sender_pet_id, content, msg_type, created_at, is_deleted
- Indexed on match_id and sender_pet_id

## Redis Usage

**Online status:** `online:{pet_id}` (5min TTL)  
**Pub/Sub:** `chat:{match_id}` channel for broadcasts

## Scaling

Multiple backend instances automatically sync via Redis pub/sub.
No sticky sessions needed.

## Testing

```javascript
// JavaScript WebSocket client
const ws = new WebSocket('ws://localhost:8000/chat/ws/{match_id}?token={token}');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'message',
    content: 'Hello!'
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg);
};
```

## Python Test
```python
import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://localhost:8000/chat/ws/{match_id}?token={token}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "message", "content": "Hi!"}))
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(test_chat())
```

## Error Handling

- Invalid token → WS closes with 1008 policy violation
- Not part of match → WS closes with 1008
- Connection drops → Auto cleanup, other user notified offline
- Message validation → Empty messages ignored

## Performance

- Messages cached in memory during active connection
- Redis pub/sub for instant cross-instance delivery
- Online status cached 5 min in Redis
- DB writes async, don't block WS sends

## Future Enhancements

- Read receipts (track last_read_message_id per user)
- Message reactions/emojis
- Image/video messages (send R2 URLs)
- Voice messages
- Playdate scheduling in chat
- Message search
- Push notifications for offline users
