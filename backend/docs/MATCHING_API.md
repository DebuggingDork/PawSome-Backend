# PawSome Matching API Documentation

## Overview

The matching system allows users to swipe on pets (like Tinder) and get notified when matches occur. The system enforces:

- **Species matching only**: Dogs can only match with dogs, cats with cats, etc.
- **Mutual likes required**: Both pets must like each other to create a match
- **No duplicate swipes**: Can't swipe on the same pet twice
- **Real-time notifications**: Both users get notified when a match happens

## Database Models

### Swipe
Records every swipe action (like or skip).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| swiper_pet_id | UUID | Pet doing the swiping |
| target_pet_id | UUID | Pet being swiped on |
| action | Enum | "like" or "skip" |
| created_at | DateTime | When the swipe happened |

**Unique constraint**: (swiper_pet_id, target_pet_id) - prevents duplicate swipes

### Match
Created when two pets mutually like each other.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| pet1_id | UUID | First pet (smaller UUID) |
| pet2_id | UUID | Second pet (larger UUID) |
| created_at | DateTime | When the match was created |

**Unique constraint**: (pet1_id, pet2_id)

### Notification
Alerts users about matches and likes.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | User receiving notification |
| notification_type | Enum | "new_match" or "new_like" |
| pet_id | UUID | Your pet |
| related_pet_id | UUID | The other pet |
| match_id | UUID | Link to match (if applicable) |
| message | Text | Human-readable message |
| is_read | Boolean | Read status |
| created_at | DateTime | When notification was created |
| read_at | DateTime | When user read it |

## API Endpoints

### 1. Swipe on a Pet

**POST** `/matches/swipe`

Swipe right (like) or left (skip) on a pet. If it's a mutual like, creates a match and sends notifications to both users.

**Request Body:**
```json
{
  "pet_id": "uuid",           // Your pet's ID
  "target_pet_id": "uuid",    // Pet you're swiping on
  "action": "like" | "skip"   // Right swipe or left swipe
}
```

**Response:**
```json
{
  "swiper_pet_id": "uuid",
  "target_pet_id": "uuid",
  "action": "like",
  "is_match": true,           // True if mutual match
  "match_id": "uuid",         // Only present if is_match = true
  "created_at": "2026-06-13T00:00:00Z"
}
```

**Validations:**
- ✅ Your pet must belong to you and be active
- ✅ Target pet must exist and be active
- ✅ Can't swipe on your own pet
- ✅ Both pets must be same species (dog with dog, cat with cat)
- ✅ Can't swipe on same pet twice

**Errors:**
- `404`: Pet not found or inactive
- `400`: Species mismatch, already swiped, or invalid action
- `403`: Not your pet

---

### 2. Get Your Matches

**GET** `/matches/my-matches?pet_id=uuid` (optional)

Get all matches for your pets. Optionally filter by a specific pet.

**Query Parameters:**
- `pet_id` (optional): Filter matches for specific pet

**Response:**
```json
[
  {
    "id": "uuid",
    "pet1_id": "uuid",
    "pet2_id": "uuid",
    "created_at": "2026-06-13T00:00:00Z"
  }
]
```

---

### 3. Get Likes Received

**GET** `/matches/likes-received?pet_id=uuid`

See which pets have liked your pet but you haven't swiped on yet. These are potential matches waiting for your swipe!

**Query Parameters:**
- `pet_id` (required): Your pet's ID

**Response:**
```json
{
  "pets": [
    {
      "id": "uuid",
      "name": "Max",
      "species": "dog",
      "breed": "Golden Retriever",
      "age_months": 24,
      "gender": "male",
      "bio": "Loves playing fetch!",
      "primary_photo_url": "https://...",
      "photos": [...]
    }
  ],
  "total": 5
}
```

---

### 4. Get Notifications

**GET** `/matches/notifications?unread_only=false&limit=50`

Get your notifications about matches and likes.

**Query Parameters:**
- `unread_only` (default: false): Only show unread notifications
- `limit` (default: 50, max: 100): Number of notifications

**Response:**
```json
[
  {
    "id": "uuid",
    "notification_type": "new_match",
    "message": "It's a match! Buddy and Max liked each other!",
    "is_read": false,
    "created_at": "2026-06-13T00:00:00Z",
    "read_at": null,
    "your_pet": {
      "id": "uuid",
      "name": "Buddy",
      "primary_photo_url": "https://..."
    },
    "other_pet": {
      "id": "uuid",
      "name": "Max",
      "primary_photo_url": "https://..."
    },
    "match_id": "uuid"
  }
]
```

---

### 5. Mark Notifications as Read

**PATCH** `/matches/notifications/read`

Mark one or more notifications as read.

**Request Body:**
```json
{
  "notification_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:** `204 No Content`

---

### 6. Get Swipe History

**GET** `/matches/swipe-history?pet_id=uuid&action=like&limit=50`

See your pet's swipe history - who you've liked or skipped.

**Query Parameters:**
- `pet_id` (required): Your pet's ID
- `action` (optional): Filter by "like" or "skip"
- `limit` (default: 50, max: 100): Number of results

**Response:**
```json
{
  "swipes": [
    {
      "swipe_id": "uuid",
      "action": "like",
      "created_at": "2026-06-13T00:00:00Z",
      "target_pet": {
        "id": "uuid",
        "name": "Luna",
        "species": "dog",
        "breed": "Husky",
        "age_months": 18,
        "gender": "female",
        "bio": "Energetic and playful!",
        "primary_photo_url": "https://...",
        "photos": [...]
      }
    }
  ],
  "total": 10
}
```

---

## Workflow Examples

### Example 1: User Swipes Right (Like)

1. User A's dog "Buddy" swipes right on User B's dog "Max"
2. **POST** `/matches/swipe`
   ```json
   {
     "pet_id": "buddy-uuid",
     "target_pet_id": "max-uuid",
     "action": "like"
   }
   ```
3. System checks if Max already liked Buddy
4. If no mutual like yet, response:
   ```json
   {
     "is_match": false,
     "match_id": null
   }
   ```
5. User B later swipes right on Buddy
6. **IT'S A MATCH!** System:
   - Creates Match record
   - Sends notification to User A
   - Sends notification to User B
   - Response includes `is_match: true` and `match_id`

### Example 2: User Swipes Left (Skip)

1. User A's dog swipes left on another dog
2. **POST** `/matches/swipe` with `action: "skip"`
3. System records the skip
4. No notification sent to target pet owner
5. That pet won't show up in User A's feed again

### Example 3: Check Who Liked You

1. User wants to see who liked their pet
2. **GET** `/matches/likes-received?pet_id=your-pet-uuid`
3. Returns list of pets that swiped right but you haven't responded to
4. User can swipe on these pets to create instant matches

---

## Business Logic

### Species Validation
```python
if swiper_pet.species != target_pet.species:
    raise HTTPException(400, "Dogs can only match with dogs, cats with cats")
```

### Mutual Match Detection
```python
# Check if target pet already liked us
mutual_like = db.query(Swipe).filter(
    Swipe.swiper_pet_id == target_pet_id,
    Swipe.target_pet_id == my_pet_id,
    Swipe.action == "like"
).first()

if mutual_like:
    # Create match!
    match = Match(pet1_id=..., pet2_id=...)
    # Send notifications to both users
```

### Notification Creation
When a match occurs:
```python
# Notify User A
Notification(
    user_id=user_a_id,
    notification_type="new_match",
    pet_id=user_a_pet_id,
    related_pet_id=user_b_pet_id,
    match_id=match.id,
    message=f"It's a match! {pet_a.name} and {pet_b.name} liked each other!"
)

# Notify User B (same structure)
```

---

## Future Enhancements

### WebSocket Integration (Next Phase)
Once matches are established, you can implement:
- Real-time chat between matched users
- Live notifications when someone likes your pet
- Online/offline status indicators

### Suggested WebSocket Events:
```typescript
// Client sends
socket.emit('join_match', { match_id: 'uuid' })
socket.emit('send_message', { match_id: 'uuid', message: 'Hi!' })

// Server broadcasts
socket.on('new_message', { match_id, message, sender_id })
socket.on('match_created', { match_id, pet_details })
socket.on('user_online', { user_id })
```

---

## Testing the API

### Test Scenario: Create a Match

1. Create two users and their pets (both dogs):
   ```bash
   # User A creates dog "Buddy"
   POST /pets
   {
     "name": "Buddy",
     "species": "dog",
     "breed": "Golden Retriever",
     "age_months": 24,
     "gender": "male",
     "lat": 40.7128,
     "lng": -74.0060
   }
   
   # User B creates dog "Max"
   POST /pets
   {
     "name": "Max",
     "species": "dog",
     "breed": "Labrador",
     "age_months": 30,
     "gender": "male",
     "lat": 40.7128,
     "lng": -74.0060
   }
   ```

2. User A swipes right on Max:
   ```bash
   POST /matches/swipe
   {
     "pet_id": "buddy-uuid",
     "target_pet_id": "max-uuid",
     "action": "like"
   }
   # Response: is_match = false
   ```

3. User B swipes right on Buddy:
   ```bash
   POST /matches/swipe
   {
     "pet_id": "max-uuid",
     "target_pet_id": "buddy-uuid",
     "action": "like"
   }
   # Response: is_match = true, match_id = "..."
   ```

4. Check notifications:
   ```bash
   GET /matches/notifications
   # Both users see "It's a match!" notification
   ```

5. View matches:
   ```bash
   GET /matches/my-matches
   # Returns the match between Buddy and Max
   ```

---

## Error Handling

| Status Code | Scenario | Message |
|-------------|----------|---------|
| 400 | Species mismatch | "Species mismatch: dog cannot match with cat" |
| 400 | Already swiped | "Already swiped on this pet" |
| 400 | Own pet | "Cannot swipe on your own pet" |
| 403 | Not your pet | "Pet does not belong to you" |
| 404 | Pet not found | "Pet not found or inactive" |
| 401 | Not authenticated | "Not authenticated" |

---

## Database Indexes

For optimal performance, the following indexes are created:

**Swipes table:**
- `ix_swipes_swiper_pet_id` - Find all swipes by a pet
- `ix_swipes_target_pet_id` - Find who swiped on a pet
- `ix_swipes_target_action` - Find likes received (composite index)

**Matches table:**
- `ix_matches_pet1` - Find matches by first pet
- `ix_matches_pet2` - Find matches by second pet

**Notifications table:**
- `ix_notifications_user_id` - Find user's notifications

---

## Security Considerations

1. **Ownership validation**: Always verify the pet belongs to the current user
2. **Active status**: Only active pets can swipe/be swiped
3. **No self-swiping**: Prevent users from swiping on their own pets
4. **Rate limiting**: Consider adding rate limits to prevent spam swiping
5. **Data privacy**: Public responses never expose exact coordinates

---

## Next Steps

1. ✅ Implement swipe functionality
2. ✅ Implement match detection
3. ✅ Implement notifications
4. ⏳ Add WebSocket for real-time chat
5. ⏳ Add push notifications for mobile
6. ⏳ Add match expiration (optional)
7. ⏳ Add undo swipe feature (optional)
