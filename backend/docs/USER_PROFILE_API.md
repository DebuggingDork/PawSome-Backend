# User Profile API

## Overview
User profiles provide essential information about pet owners with privacy controls based on relationship status.

## Privacy Levels

### 1. Public Profile (Anyone)
Visible to all users browsing pets:
- `full_name`
- `occupation`
- `bio`
- `profile_photo_url`

### 2. Private Profile (Matched Connections Only)
Visible only to users whose pets have matched:
- Everything from public profile
- `address` (private, only visible to matched connections)

### 3. Full Profile (Owner Only)
Only visible to the profile owner:
- Everything from private profile
- `email`
- `is_verified`

## Endpoints

### GET /users/me
Get your own full profile including address and email.

**Authentication:** Required

**Response:** UserFullProfile
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_verified": true,
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover and outdoor enthusiast",
  "address": "123 Main St, City, State",
  "profile_photo_url": "https://..."
}
```

### PATCH /users/me
Update your profile information.

**Authentication:** Required

**Request Body:**
```json
{
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover and outdoor enthusiast",
  "address": "123 Main St, City, State",
  "profile_photo_url": "https://..."
}
```

All fields are optional. Only send fields you want to update.

**Response:** UserFullProfile (same as GET /users/me)

### GET /users/{user_id}
View another user's profile. Response varies based on relationship:

**Authentication:** Optional (public profile if not authenticated)

**Response:**
- **If not authenticated:** UserPublicProfile (name, occupation, bio, photo)
- **If authenticated but not matched:** UserPublicProfile
- **If authenticated and matched:** UserPrivateProfile (includes address)

**Public Response Example:**
```json
{
  "id": "uuid",
  "full_name": "Jane Smith",
  "occupation": "Veterinarian",
  "bio": "Cat lover with 3 rescue cats",
  "profile_photo_url": "https://..."
}
```

**Private Response Example (Matched Connection):**
```json
{
  "id": "uuid",
  "full_name": "Jane Smith",
  "occupation": "Veterinarian",
  "bio": "Cat lover with 3 rescue cats",
  "address": "456 Oak Ave, City, State",
  "profile_photo_url": "https://..."
}
```

## Pet Photo Requirements

### New Pet Creation Flow

1. **Create Pet Profile**
   - POST /pets
   - Pet is created with `is_active=false` (not visible in browse)
   
2. **Upload First Photo**
   - POST /pets/{pet_id}/photos/presign (get upload URL)
   - PUT to the presigned URL (upload image)
   - POST /pets/{pet_id}/photos (confirm upload)
   - **Pet automatically becomes active** (`is_active=true`)

3. **Browse & Match**
   - Pet now appears in public browse catalog
   - Primary photo is shown as the card image

### Photo Rules

- **Minimum:** At least 1 photo required (pet must have photo to be active)
- **Maximum:** 5 photos per pet
- **First photo:** Automatically becomes primary and activates the pet
- **Cannot delete last photo:** You must maintain at least one image
- **Primary photo:** Can be changed using PATCH /pets/{pet_id}/photos/{photo_id}/primary

## Workflow Examples

### Example 1: New User Setup
1. Register/login: POST /auth/register or /auth/login
2. Update profile: PATCH /users/me with name, occupation, bio, photo
3. Create pet: POST /pets (pet is inactive)
4. Upload pet photo: Complete photo upload flow (pet becomes active)
5. Start browsing: GET /pets (see other active pets)

### Example 2: Viewing Another User's Profile
1. Browse pets: GET /pets
2. Like a pet: POST /swipes (like action)
3. If mutual match: GET /users/{user_id} (see public profile + address)
4. No match: GET /users/{user_id} (see public profile only)

### Example 3: Managing Pet Photos
1. Upload additional photos: Up to 5 total
2. Change primary photo: PATCH /pets/{pet_id}/photos/{photo_id}/primary
3. Delete photo: DELETE /pets/{pet_id}/photos/{photo_id}
   - ❌ Cannot delete if it's the last photo
   - ✅ Can delete if pet has 2+ photos

## Database Schema

### User Model (Updated)
```python
- id: UUID (primary key)
- email: string (unique)
- password_hash: string
- google_id: string (nullable)
- is_verified: boolean
- full_name: string (nullable)          # NEW
- occupation: string (nullable)         # NEW
- bio: text (nullable)                  # NEW
- address: text (nullable)              # NEW - private
- profile_photo_url: string (nullable)  # NEW
- created_at: timestamp
- updated_at: timestamp
```

### Privacy Logic Implementation

The `GET /users/{user_id}` endpoint checks:
1. Is the requesting user viewing their own profile? → Full profile
2. Do any of the requesting user's pets match any of the target user's pets? → Private profile
3. Otherwise → Public profile
