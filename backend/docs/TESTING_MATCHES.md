# Testing the Matching System

## Quick Start Guide

This guide walks you through testing the complete matching workflow using the API.

## Prerequisites

1. Backend running: `uv run fastapi dev`
2. Database migrated: `uv run alembic upgrade head`
3. Two test user accounts created

## Step-by-Step Testing

### 1. Create Two Users

```bash
# User A
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@test.com",
    "password": "password123"
  }'

# User B
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "bob@test.com",
    "password": "password123"
  }'
```

### 2. Login and Get Tokens

```bash
# Login as User A
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@test.com",
    "password": "password123"
  }'

# Save the access_token from response
TOKEN_A="eyJ..."

# Login as User B
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "bob@test.com",
    "password": "password123"
  }'

TOKEN_B="eyJ..."
```

### 3. Create Pet Profiles (Both Dogs for Matching)

```bash
# User A creates "Buddy" (Golden Retriever)
curl -X POST http://localhost:8000/pets \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Buddy",
    "species": "dog",
    "breed": "Golden Retriever",
    "age_months": 24,
    "gender": "male",
    "bio": "Friendly and playful!",
    "lat": 40.7128,
    "lng": -74.0060
  }'

# Save pet_id as PET_A
PET_A="uuid-here"

# User B creates "Max" (Labrador)
curl -X POST http://localhost:8000/pets \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Max",
    "species": "dog",
    "breed": "Labrador",
    "age_months": 30,
    "gender": "male",
    "bio": "Loves to fetch!",
    "lat": 40.7128,
    "lng": -74.0060
  }'

PET_B="uuid-here"
```

### 4. Test Swipe (Like) - No Match Yet

```bash
# User A swipes RIGHT on Max
curl -X POST http://localhost:8000/matches/swipe \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "pet_id": "'$PET_A'",
    "target_pet_id": "'$PET_B'",
    "action": "like"
  }'

# Response should show:
# {
#   "is_match": false,
#   "match_id": null
# }
```

### 5. Test Mutual Match

```bash
# User B swipes RIGHT on Buddy - THIS CREATES A MATCH!
curl -X POST http://localhost:8000/matches/swipe \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "pet_id": "'$PET_B'",
    "target_pet_id": "'$PET_A'",
    "action": "like"
  }'

# Response should show:
# {
#   "is_match": true,
#   "match_id": "some-uuid",
#   ...
# }
```

### 6. Check Notifications

```bash
# User A checks notifications
curl -X GET http://localhost:8000/matches/notifications \
  -H "Authorization: Bearer $TOKEN_A"

# Should see: "It's a match! Buddy and Max liked each other!"

# User B checks notifications
curl -X GET http://localhost:8000/matches/notifications \
  -H "Authorization: Bearer $TOKEN_B"

# Should also see the match notification
```

### 7. View Matches

```bash
# User A views all matches
curl -X GET http://localhost:8000/matches/my-matches \
  -H "Authorization: Bearer $TOKEN_A"

# User B views all matches
curl -X GET http://localhost:8000/matches/my-matches \
  -H "Authorization: Bearer $TOKEN_B"
```

### 8. Mark Notification as Read

```bash
# Get notification ID from step 6, then:
curl -X PATCH http://localhost:8000/matches/notifications/read \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "notification_ids": ["notification-uuid-here"]
  }'
```

## Testing Edge Cases

### Test Species Mismatch

```bash
# Create a cat for User B
curl -X POST http://localhost:8000/pets \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Whiskers",
    "species": "cat",
    "breed": "Persian",
    "age_months": 18,
    "gender": "female",
    "bio": "Sleepy cat",
    "lat": 40.7128,
    "lng": -74.0060
  }'

CAT_ID="uuid-here"

# Try to swipe dog on cat - SHOULD FAIL
curl -X POST http://localhost:8000/matches/swipe \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "pet_id": "'$PET_A'",
    "target_pet_id": "'$CAT_ID'",
    "action": "like"
  }'

# Response: 400 Bad Request
# "Species mismatch: dog cannot match with cat"
```

### Test Duplicate Swipe

```bash
# Try to swipe on Max again - SHOULD FAIL
curl -X POST http://localhost:8000/matches/swipe \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "pet_id": "'$PET_A'",
    "target_pet_id": "'$PET_B'",
    "action": "like"
  }'

# Response: 400 Bad Request
# "Already swiped on this pet"
```

### Test Left Swipe (Skip)

```bash
# Create another dog
curl -X POST http://localhost:8000/pets \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Charlie",
    "species": "dog",
    "breed": "Beagle",
    "age_months": 12,
    "gender": "male",
    "lat": 40.7128,
    "lng": -74.0060
  }'

CHARLIE_ID="uuid-here"

# User B skips Charlie (left swipe)
curl -X POST http://localhost:8000/matches/swipe \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "pet_id": "'$PET_B'",
    "target_pet_id": "'$CHARLIE_ID'",
    "action": "skip"
  }'

# Response: is_match = false (no notification sent to Charlie's owner)
```

### Test Likes Received

```bash
# Check who liked Buddy (should be Max)
curl -X GET "http://localhost:8000/matches/likes-received?pet_id=$PET_A" \
  -H "Authorization: Bearer $TOKEN_A"

# Should return empty if already matched, or pending likes if any
```

### Test Swipe History

```bash
# View all of Buddy's swipes
curl -X GET "http://localhost:8000/matches/swipe-history?pet_id=$PET_A" \
  -H "Authorization: Bearer $TOKEN_A"

# Filter by action
curl -X GET "http://localhost:8000/matches/swipe-history?pet_id=$PET_A&action=like" \
  -H "Authorization: Bearer $TOKEN_A"
```

## Using Swagger UI

Alternatively, test everything through the interactive docs:

1. Go to http://localhost:8000/docs
2. Click "Authorize" button at top
3. Enter your token: `Bearer your-token-here`
4. Try all the endpoints interactively

## Expected Workflow in Production

```
User A sees User B's pet in feed
   ↓
User A swipes RIGHT (POST /matches/swipe action=like)
   ↓
System records the like in database
   ↓
Later, User B sees User A's pet
   ↓
User B swipes RIGHT
   ↓
System detects mutual like → creates Match
   ↓
System creates 2 Notifications (one for each user)
   ↓
Both users get push notification: "It's a match!"
   ↓
Frontend shows match modal with other pet's info
   ↓
Users can now chat (WebSocket in Phase 5)
```

## Database Verification

You can also check the database directly:

```sql
-- Check swipes
SELECT * FROM swipes ORDER BY created_at DESC;

-- Check matches
SELECT * FROM matches ORDER BY created_at DESC;

-- Check notifications
SELECT * FROM notifications ORDER BY created_at DESC;

-- Check who liked a specific pet
SELECT sp.*, pp.name 
FROM swipes s
JOIN pet_profiles pp ON pp.id = s.swiper_pet_id
WHERE s.target_pet_id = 'your-pet-uuid'
AND s.action = 'like';
```

## Troubleshooting

### "Pet not found or inactive"
- Make sure the pet IDs are correct
- Check that pets have `is_active = true`

### "Species mismatch"
- This is expected! Dogs can only match with dogs, cats with cats, etc.
- Make sure both pets are the same species

### "Already swiped on this pet"
- You can only swipe once per pet
- Check your swipe history to see previous swipes

### No notifications showing up
- Notifications are only created on mutual matches (not on single likes)
- Check that both pets liked each other
- Query the notifications table directly to verify

### Match not created
- Both pets must LIKE each other (not skip)
- Check that the swipes table has both direction likes
- Verify species are the same

## Next Steps

Once matching is working:
1. Build the frontend swipe UI (Tinder-style cards)
2. Implement WebSocket chat (Phase 5)
3. Add push notifications via Firebase FCM
4. Build the explore feed with geo-filtering
5. Add super-woofs and premium features
