# PawSome API - Complete Endpoint Documentation

**Base URL:** `http://localhost:8000/api/v1` (development)

**Authentication:** Most endpoints require Bearer token authentication
```
Authorization: Bearer <access_token>
```
# use this fuckin .env for running backend server

```env
# ============================================================
# Database Configuration
# ============================================================

DATABASE_URL=postgresql://neondb_owner:npg_xgY3G4KPJpud@ep-delicate-cloud-aoffo7k7-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

# ============================================================
# Redis Configuration
# ============================================================

REDIS_URL=rediss://default:gQAAAAAAAimgAAIgcDIyMDhiZWNlOWE4YjA0MWI2YTRkZjRlNTllMDJlZGM5Yg@vital-jennet-141728.upstash.io:6379

# ============================================================
# JWT Authentication
# ============================================================

JWT_SECRET=0cf737d9da1194cfc3fc733bb3cbc8ba72b445ab4bac924a7d8d0d13138ded962a9e595e364461e139b41c1fd0f76992845e91c72a8dc8a769bfb9c80d7c9836
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ============================================================
# Frontend Configuration
# ============================================================

FRONTEND_URL=http://localhost:5173

# ============================================================
# Application Configuration
# ============================================================

APP_ENV=development

# ============================================================
# CORS Configuration
# ============================================================

CORS_ORIGINS=http://localhost:5173

# ============================================================
# Cloudflare R2 (Photo Storage)
# ============================================================

R2_ACCOUNT_ID=587b29c736a0ef36b92b0d4266fff410
R2_ACCESS_KEY_ID=321cb85c59fbe8312c1b9efbcbcf0bfa
R2_SECRET_ACCESS_KEY=c7d9010b72bb8539da5a83d2faafbc68057e892452164886f77366f4a8d31263

R2_BUCKET_NAME=pawsome-photos-dev
R2_PUBLIC_BASE_URL=https://pub-2241f255146e4b8ab3347e935732ec62.r2.dev
```

## Table of Contents

1. [Authentication](#authentication)
2. [Users](#users)
3. [Onboarding](#onboarding)
4. [Achievements](#achievements)
5. [Pets](#pets)
6. [Pet Photos](#pet-photos)
7. [Matching System](#matching-system)
8. [Chat System](#chat-system)

---

## Authentication

### Register New User

**POST** `/auth/register`

Creates a new user account and sends verification email.

**Request Body:**
```json
{
  "email": "john@example.com",
  "password": "securepassword123"
}
```

**Response:** `201 Created`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer"
}
```

**Errors:**
- `409`: Email already registered

---

### Login

**POST** `/auth/login`

Authenticate existing user.

**Request Body:**
```json
{
  "email": "john@example.com",
  "password": "securepassword123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer"
}
```

**Errors:**
- `401`: Invalid credentials

---

### Refresh Token

**POST** `/auth/refresh`

Get new access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer"
}
```

---

### Logout

**POST** `/auth/logout`

Revoke refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `204 No Content`

---

### Get Current User

**GET** `/auth/me`

 **Requires Authentication**

Get basic info about authenticated user.

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john@example.com",
  "is_verified": false
}
```

---

### Verify Email

**POST** `/auth/verify-email`

Verify user's email address using token from email.

**Request Body:**
```json
{
  "token": "AbCdEf123456..."
}
```

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john@example.com",
  "is_verified": true
}
```

**Errors:**
- `400`: Invalid or expired verification token
- `404`: User not found

---

### Resend Verification Email

**POST** `/auth/resend-verification`

Request new verification email.

**Request Body:**
```json
{
  "email": "john@example.com"
}
```

**Response:** `200 OK`
```json
{
  "message": "Verification email sent"
}
```

**Errors:**
- `400`: Email already verified

---

## Users

### Get My Full Profile

**GET** `/users/me`

 **Requires Authentication**

Get complete profile of authenticated user including private fields.

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john@example.com",
  "is_verified": true,
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover and outdoor enthusiast. Looking for playmates for my golden retriever!",
  "address": "123 Main St, Seattle, WA",
  "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
}
```

---

### Update My Profile

**PATCH** `/users/me`

 **Requires Authentication**

Update user profile fields. All fields are optional.

**Request Body:**
```json
{
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover and outdoor enthusiast",
  "address": "123 Main St, Seattle, WA"
}
```

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john@example.com",
  "is_verified": true,
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover and outdoor enthusiast",
  "address": "123 Main St, Seattle, WA",
  "profile_photo_url": null
}
```

---

### Get Profile Completion Status

**GET** `/users/me/completion`

 **Requires Authentication**

Get gamified profile completion progress.

**Response:** `200 OK`
```json
{
  "completion_percentage": 75,
  "is_complete": false,
  "completed_fields": ["full_name", "occupation", "pet_created", "pet_photo"],
  "missing_fields": ["profile_photo", "bio", "address"],
  "suggestions": [
    "Upload a profile photo to build trust",
    "Write a bio about yourself and your pet preferences"
  ],
  "profile_fields_complete": 60,
  "pet_profile_complete": 100,
  "total_pets": 1,
  "active_pets": 1,
  "has_profile_photo": false,
  "has_basic_info": true,
  "has_bio": false,
  "has_address": false,
  "has_at_least_one_pet": true,
  "has_active_pet": true
}
```

---

### Get User Profile by ID

**GET** `/users/{user_id}`

Get another user's profile. Privacy levels:
- **Public** (no auth): name, occupation, bio, photo
- **Private** (matched users only): includes address
- **Owner** (yourself): redirects to `/users/me`

**Response:** `200 OK` (Public)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover and outdoor enthusiast",
  "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
}
```

**Response:** `200 OK` (Matched - includes address)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover and outdoor enthusiast",
  "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg",
  "address": "123 Main St, Seattle, WA"
}
```

---

### Upload Profile Photo - Get Presigned URL

**POST** `/users/me/photo/presign`

 **Requires Authentication**

Step 1: Get presigned URL for direct upload to R2.

**Request Body:**
```json
{
  "content_type": "image/jpeg"
}
```

**Allowed content types:** `image/jpeg`, `image/png`, `image/webp`

**Response:** `200 OK`
```json
{
  "upload_url": "https://r2.cloudflarestorage.com/...",
  "object_key": "users/550e8400.../profile.jpg",
  "expires_in": 600
}
```

**Usage:**
1. PUT the image file to `upload_url` with same Content-Type header
2. Call confirm endpoint with `object_key`

---

### Upload Profile Photo - Confirm

**POST** `/users/me/photo`

 **Requires Authentication**

Step 2: Confirm upload after PUTting file to presigned URL.

**Request Body:**
```json
{
  "object_key": "users/550e8400.../profile.jpg"
}
```

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john@example.com",
  "is_verified": true,
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "bio": "Dog lover",
  "address": "123 Main St",
  "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
}
```

**Note:** Grants `PROFILE_PHOTO` achievement on first upload.

---

### Delete Profile Photo

**DELETE** `/users/me/photo`

 **Requires Authentication**

Remove profile photo.

**Response:** `204 No Content`

---

## Onboarding

### Get Onboarding Status

**GET** `/onboarding/status`

 **Requires Authentication**

Get step-by-step onboarding wizard progress.

**Response:** `200 OK`
```json
{
  "current_step": "pet_photos",
  "total_steps": 6,
  "completed_steps": 3,
  "completion_percentage": 50,
  "is_complete": false,
  "can_start_swiping": false,
  "should_show_wizard": true,
  "steps": [
    {
      "step": "email_verification",
      "title": "Verify Your Email",
      "description": "Check your inbox and click the verification link",
      "completed": false,
      "required": false,
      "action_url": "/api/v1/auth/resend-verification",
      "action_text": "Resend Email"
    },
    {
      "step": "profile_basics",
      "title": "Tell Us About Yourself",
      "description": "Add your name and occupation",
      "completed": true,
      "required": true,
      "action_url": "/api/v1/users/me",
      "action_text": "Complete Profile"
    },
    {
      "step": "profile_photo",
      "title": "Add Your Photo",
      "description": "Upload a profile picture to build trust",
      "completed": true,
      "required": true,
      "action_url": "/api/v1/users/me/photo/presign",
      "action_text": "Upload Photo"
    },
    {
      "step": "pet_profile",
      "title": "Create Pet Profile",
      "description": "Add details about your furry friend",
      "completed": true,
      "required": true,
      "action_url": "/api/v1/pets",
      "action_text": "Add Pet"
    },
    {
      "step": "pet_photos",
      "title": "Add Pet Photos",
      "description": "Upload at least one photo of your pet",
      "completed": false,
      "required": true,
      "action_url": null,
      "action_text": "Upload Photos"
    },
    {
      "step": "preferences",
      "title": "Set Your Preferences",
      "description": "Add bio and address for better matches",
      "completed": false,
      "required": false,
      "action_url": "/api/v1/users/me",
      "action_text": "Set Preferences"
    }
  ]
}
```

---

### Skip Optional Steps

**POST** `/onboarding/skip-optional`

 **Requires Authentication**

Mark optional onboarding steps as skipped.

**Response:** `200 OK`
```json
{
  "message": "Optional steps skipped. You can complete them later from your profile.",
  "skippable_steps": ["email_verification", "preferences"]
}
```

---

## Achievements

### Get My Achievements

**GET** `/achievements/me`

 **Requires Authentication**

Get all achievement badges and progress.

**Response:** `200 OK`
```json
{
  "total_earned": 4,
  "total_available": 9,
  "completion_percentage": 44,
  "badges": [
    {
      "type": "profile_photo",
      "name": "Picture Perfect",
      "description": "Upload your profile photo",
      "icon": "📸",
      "earned": true,
      "earned_at": "2024-01-15T10:30:00Z"
    },
    {
      "type": "full_name",
      "name": "First Steps",
      "description": "Add your name to your profile",
      "icon": "👤",
      "earned": true,
      "earned_at": "2024-01-15T10:25:00Z"
    },
    {
      "type": "pet_created",
      "name": "Pet Parent",
      "description": "Create your first pet profile",
      "icon": "🐕",
      "earned": true,
      "earned_at": "2024-01-15T11:00:00Z"
    },
    {
      "type": "pet_photo",
      "name": "Show & Tell",
      "description": "Upload your pet's first photo",
      "icon": "📷",
      "earned": true,
      "earned_at": "2024-01-15T11:15:00Z"
    },
    {
      "type": "first_match",
      "name": "Match Maker",
      "description": "Get your first match",
      "icon": "💝",
      "earned": false,
      "earned_at": null
    },
    {
      "type": "five_matches",
      "name": "Popular Paw",
      "description": "Achieve 5 matches",
      "icon": "⭐",
      "earned": false,
      "earned_at": null
    },
    {
      "type": "first_message",
      "name": "Breaking the Ice",
      "description": "Send your first message",
      "icon": "💬",
      "earned": false,
      "earned_at": null
    },
    {
      "type": "profile_complete",
      "name": "All Set",
      "description": "Complete your profile 100%",
      "icon": "✨",
      "earned": false,
      "earned_at": null
    },
    {
      "type": "verified_email",
      "name": "Verified",
      "description": "Verify your email address",
      "icon": "✅",
      "earned": false,
      "earned_at": null
    }
  ],
  "recent_achievements": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440004",
      "achievement_type": "pet_photo",
      "earned_at": "2024-01-15T11:15:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440003",
      "achievement_type": "pet_created",
      "earned_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

---

## Pets

### Browse Pets (Public Catalog)

**GET** `/pets`

Public endpoint - no authentication required. Browse all active pets with optional filters.

**Query Parameters:**
- `species` (optional): `dog` or `cat`
- `gender` (optional): `male` or `female`
- `breed` (optional): Partial breed name (case-insensitive)
- `limit` (optional, default: 20, max: 100): Results per page
- `offset` (optional, default: 0): Pagination offset

**Example:** `/pets?species=dog&gender=female&limit=10&offset=0`

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "name": "Max",
      "species": "dog",
      "breed": "Golden Retriever",
      "age_years": 3,
      "gender": "male",
      "bio": "Energetic and loves to play fetch!",
      "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg",
      "owner": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "full_name": "John Doe",
        "occupation": "Software Engineer",
        "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
      }
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440001",
      "name": "Bella",
      "species": "dog",
      "breed": "Labrador",
      "age_years": 2,
      "gender": "female",
      "bio": "Friendly and loves swimming",
      "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg",
      "owner": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "full_name": "Jane Smith",
        "occupation": "Teacher",
        "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
      }
    }
  ],
  "total": 45,
  "limit": 20,
  "offset": 0
}
```

---

### Create Pet Profile

**POST** `/pets`

**Requires Authentication**

Create a new pet profile. Maximum 5 pets per user.

**Request Body:**
```json
{
  "name": "Max",
  "species": "dog",
  "breed": "Golden Retriever",
  "age_years": 3,
  "gender": "male",
  "bio": "Energetic and loves to play fetch! Great with other dogs."
}
```

**Response:** `201 Created`
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Max",
  "species": "dog",
  "breed": "Golden Retriever",
  "age_years": 3,
  "gender": "male",
  "bio": "Energetic and loves to play fetch! Great with other dogs.",
  "is_active": false,
  "primary_photo_url": null,
  "created_at": "2024-01-15T11:00:00Z"
}
```

**Note:** 
- Pet starts as `is_active: false`
- Becomes active after first photo is uploaded
- Grants `PET_CREATED` achievement

**Errors:**
- `400`: Maximum of 5 pets per user

---

### Get My Pets

**GET** `/pets/me`

 **Requires Authentication**

List all active pets owned by current user.

**Response:** `200 OK`
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Max",
    "species": "dog",
    "breed": "Golden Retriever",
    "age_years": 3,
    "gender": "male",
    "bio": "Energetic and loves to play fetch!",
    "is_active": true,
    "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg",
    "created_at": "2024-01-15T11:00:00Z"
  }
]
```

---

### Get Pet by ID

**GET** `/pets/{pet_id}`

Get pet details. Owner sees full data, others see public view with owner info.

**Response:** `200 OK`
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "name": "Max",
  "species": "dog",
  "breed": "Golden Retriever",
  "age_years": 3,
  "gender": "male",
  "bio": "Energetic and loves to play fetch!",
  "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg",
  "owner": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "John Doe",
    "occupation": "Software Engineer",
    "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
  }
}
```

**Errors:**
- `404`: Pet not found or inactive

---

### Update Pet

**PATCH** `/pets/{pet_id}`

 **Requires Authentication** (must be owner)

Update pet profile. All fields are optional.

**Request Body:**
```json
{
  "name": "Maximus",
  "age_years": 4,
  "bio": "Updated bio - now even more energetic!"
}
```

**Response:** `200 OK`
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Maximus",
  "species": "dog",
  "breed": "Golden Retriever",
  "age_years": 4,
  "gender": "male",
  "bio": "Updated bio - now even more energetic!",
  "is_active": true,
  "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg",
  "created_at": "2024-01-15T11:00:00Z"
}
```

---

### Delete Pet (Soft Delete)

**DELETE** `/pets/{pet_id}`

 **Requires Authentication** (must be owner)

Deactivate pet profile (soft delete).

**Response:** `204 No Content`

---

## Pet Photos

All photo endpoints use two-step upload process:
1. Get presigned URL
2. PUT file to URL
3. Confirm upload

### Get Presigned URL for Pet Photo

**POST** `/pets/{pet_id}/photos/presign`

 **Requires Authentication** (must be owner)

Step 1: Get presigned URL for uploading pet photo. Maximum 5 photos per pet.

**Request Body:**
```json
{
  "content_type": "image/jpeg"
}
```

**Allowed content types:** `image/jpeg`, `image/png`, `image/webp`

**Response:** `200 OK`
```json
{
  "upload_url": "https://r2.cloudflarestorage.com/...",
  "object_key": "pets/770e8400.../abc123.jpg",
  "expires_in": 600
}
```

**Errors:**
- `400`: Maximum of 5 photos per pet
- `503`: Photo storage not configured

---

### Confirm Pet Photo Upload

**POST** `/pets/{pet_id}/photos`

 **Requires Authentication** (must be owner)

Step 2: Confirm photo upload after PUTting file to presigned URL.

**Request Body:**
```json
{
  "object_key": "pets/770e8400.../abc123.jpg"
}
```

**Response:** `201 Created`
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "pet_id": "770e8400-e29b-41d4-a716-446655440000",
  "url": "https://r2.example.com/pets/770e8400.../abc123.jpg",
  "is_primary": true,
  "sort_order": 0,
  "object_key": "pets/770e8400.../abc123.jpg"
}
```

**Note:**
- First photo becomes primary automatically
- First photo activates the pet (`is_active: true`)
- Grants `PET_PHOTO` achievement on first upload

---

### Set Primary Photo

**PATCH** `/pets/{pet_id}/photos/{photo_id}/primary`

 **Requires Authentication** (must be owner)

Make a photo the primary (card image in browse catalog).

**Response:** `200 OK`
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440001",
  "pet_id": "770e8400-e29b-41d4-a716-446655440000",
  "url": "https://r2.example.com/pets/770e8400.../def456.jpg",
  "is_primary": true,
  "sort_order": 1,
  "object_key": "pets/770e8400.../def456.jpg"
}
```

---

### Delete Pet Photo

**DELETE** `/pets/{pet_id}/photos/{photo_id}`

 **Requires Authentication** (must be owner)

Delete a pet photo. Cannot delete the last photo.

**Response:** `204 No Content`

**Errors:**
- `400`: Cannot delete the last photo
- `404`: Photo not found

---

## Matching System

### Swipe on Pet

**POST** `/matches/swipe`

 **Requires Authentication**

Swipe right (like) or left (skip) on another pet.

**Request Body:**
```json
{
  "pet_id": "770e8400-e29b-41d4-a716-446655440000",
  "target_pet_id": "770e8400-e29b-41d4-a716-446655440001",
  "action": "like"
}
```

**Action values:** `like` or `skip`

**Response:** `200 OK`
```json
{
  "swiper_pet_id": "770e8400-e29b-41d4-a716-446655440000",
  "target_pet_id": "770e8400-e29b-41d4-a716-446655440001",
  "action": "like",
  "is_match": false,
  "match_id": null,
  "created_at": "2024-01-15T12:00:00Z"
}
```

**Validation:**
- Both pets must exist and be active
- Swiper pet must belong to current user
- Must be same species (dogs with dogs only)
- Cannot swipe on your own pet
- Cannot swipe twice on same pet

**Errors:**
- `404`: Pet not found or inactive
- `400`: Invalid swipe (own pet, species mismatch, already swiped)

---

### Get My Matches

**GET** `/matches/my-matches`

 **Requires Authentication**

Get all matches for current user's pets.

**Query Parameters:**
- `pet_id` (optional): Filter by specific pet

**Response:** `200 OK`
```json
[
  {
    "id": "990e8400-e29b-41d4-a716-446655440000",
    "pet1_id": "770e8400-e29b-41d4-a716-446655440000",
    "pet2_id": "770e8400-e29b-41d4-a716-446655440001",
    "created_at": "2024-01-15T14:30:00Z"
  },
  {
    "id": "990e8400-e29b-41d4-a716-446655440001",
    "pet1_id": "770e8400-e29b-41d4-a716-446655440000",
    "pet2_id": "770e8400-e29b-41d4-a716-446655440002",
    "created_at": "2024-01-15T15:45:00Z"
  }
]
```

---

### Get Notifications

**GET** `/matches/notifications`

**Requires Authentication**

Get all notifications for current user.

**Query Parameters:**
- `unread_only` (optional, default: false): Filter unread only

**Response:** `200 OK`
```json
[
  {
    "id": "aa0e8400-e29b-41d4-a716-446655440000",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "notification_type": "new_like",
    "pet_id": "770e8400-e29b-41d4-a716-446655440000",
    "related_pet_id": "770e8400-e29b-41d4-a716-446655440001",
    "match_id": null,
    "message": "Max is interested in Bella!",
    "is_read": false,
    "read_at": null,
    "created_at": "2024-01-15T14:00:00Z",
    "pet": {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "name": "Bella",
      "species": "dog",
      "breed": "Labrador",
      "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg"
    },
    "related_pet": {
      "id": "770e8400-e29b-41d4-a716-446655440001",
      "name": "Max",
      "species": "dog",
      "breed": "Golden Retriever",
      "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg"
    }
  }
]
```

**Notification types:** `new_like`, `new_match`, `like_rejected`

---

### Accept Like (Create Match)

**POST** `/matches/likes/{notification_id}/accept`

 **Requires Authentication**

Accept a like notification and create a match.

**Response:** `200 OK`
```json
{
  "match_id": "990e8400-e29b-41d4-a716-446655440000",
  "message": "Match created! You can now chat with Max's owner."
}
```

**Note:**
- Creates match between two pets
- Sends match notifications to both users
- Marks original like notification as read
- Grants `FIRST_MATCH` achievement (first match)
- Grants `FIVE_MATCHES` achievement (at 5 matches)

**Errors:**
- `404`: Like notification not found
- `400`: Match already exists

---

### Reject Like

**POST** `/matches/likes/{notification_id}/reject`

 **Requires Authentication**

Reject a like notification.

**Response:** `200 OK`
```json
{
  "message": "Like rejected"
}
```

**Note:**
- Marks notification as read
- Sends rejection notification to other user

---

### Mark Notification as Read

**POST** `/matches/notifications/mark-read`

 **Requires Authentication**

Mark one or multiple notifications as read.

**Request Body:**
```json
{
  "notification_ids": [
    "aa0e8400-e29b-41d4-a716-446655440000",
    "aa0e8400-e29b-41d4-a716-446655440001"
  ]
}
```

**Response:** `200 OK`
```json
{
  "marked_read": 2
}
```

---

## Chat System

### WebSocket Connection

**WS** `/chat/ws/{match_id}?pet_id={pet_id}&token={access_token}`

 **Requires Authentication** (via query param)

Real-time chat with WebSocket connection.

**Connection URL Example:**
```
ws://localhost:8000/api/v1/chat/ws/990e8400-e29b-41d4-a716-446655440000?pet_id=770e8400-e29b-41d4-a716-446655440000&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Send Message:**
```json
{
  "type": "message",
  "content": "Hey! Max would love to meet Bella at the park!",
  "msg_type": "text"
}
```

**Received Message:**
```json
{
  "type": "message",
  "data": {
    "id": "bb0e8400-e29b-41d4-a716-446655440000",
    "match_id": "990e8400-e29b-41d4-a716-446655440000",
    "sender_pet_id": "770e8400-e29b-41d4-a716-446655440001",
    "content": "Hey! Max would love to meet Bella at the park!",
    "msg_type": "text",
    "created_at": "2024-01-15T16:00:00.123456Z"
  }
}
```

**Mark as Read:**
```json
{
  "type": "read",
  "message_id": "bb0e8400-e29b-41d4-a716-446655440000"
}
```

**Typing Indicator:**
```json
{
  "type": "typing",
  "is_typing": true
}
```

**Received Typing Indicator:**
```json
{
  "type": "typing",
  "data": {
    "pet_id": "770e8400-e29b-41d4-a716-446655440001",
    "is_typing": true
  }
}
```

**Note:** First message sent grants `FIRST_MESSAGE` achievement.

---

### Get Match Details

**GET** `/chat/matches/{match_id}`

 **Requires Authentication**

Get match details including both pets and owners.

**Response:** `200 OK`
```json
{
  "match_id": "990e8400-e29b-41d4-a716-446655440000",
  "pet1": {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "name": "Max",
    "species": "dog",
    "breed": "Golden Retriever",
    "age_years": 3,
    "gender": "male",
    "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg",
    "owner": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "full_name": "John Doe",
      "occupation": "Software Engineer",
      "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
    }
  },
  "pet2": {
    "id": "770e8400-e29b-41d4-a716-446655440001",
    "name": "Bella",
    "species": "dog",
    "breed": "Labrador",
    "age_years": 2,
    "gender": "female",
    "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg",
    "owner": {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "full_name": "Jane Smith",
      "occupation": "Teacher",
      "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
    }
  },
  "created_at": "2024-01-15T14:30:00Z"
}
```

---

### Get Chat History

**GET** `/chat/matches/{match_id}/messages`

 **Requires Authentication**

Get message history for a match.

**Query Parameters:**
- `limit` (optional, default: 50, max: 200): Number of messages
- `before_id` (optional): Get messages before this ID (pagination)

**Response:** `200 OK`
```json
{
  "messages": [
    {
      "id": "bb0e8400-e29b-41d4-a716-446655440000",
      "match_id": "990e8400-e29b-41d4-a716-446655440000",
      "sender_pet_id": "770e8400-e29b-41d4-a716-446655440000",
      "content": "Hey! Max would love to meet Bella!",
      "msg_type": "text",
      "created_at": "2024-01-15T16:00:00Z"
    },
    {
      "id": "bb0e8400-e29b-41d4-a716-446655440001",
      "match_id": "990e8400-e29b-41d4-a716-446655440000",
      "sender_pet_id": "770e8400-e29b-41d4-a716-446655440001",
      "content": "That sounds great! How about tomorrow at Green Lake Park?",
      "msg_type": "text",
      "created_at": "2024-01-15T16:05:00Z"
    }
  ],
  "has_more": false
}
```

---

### Get Active Chats

**GET** `/chat/active-chats`

 **Requires Authentication**

Get all active chat conversations for current user's pets.

**Query Parameters:**
- `pet_id` (optional): Filter by specific pet

**Response:** `200 OK`
```json
[
  {
    "match_id": "990e8400-e29b-41d4-a716-446655440000",
    "your_pet": {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "name": "Max",
      "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg"
    },
    "other_pet": {
      "id": "770e8400-e29b-41d4-a716-446655440001",
      "name": "Bella",
      "primary_photo_url": "https://r2.example.com/pets/770e8400.../photo1.jpg"
    },
    "other_owner": {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "full_name": "Jane Smith",
      "profile_photo_url": "https://r2.example.com/users/550e8400.../profile.jpg"
    },
    "last_message": {
      "id": "bb0e8400-e29b-41d4-a716-446655440001",
      "content": "That sounds great! How about tomorrow?",
      "created_at": "2024-01-15T16:05:00Z",
      "is_from_you": false
    },
    "unread_count": 2,
    "matched_at": "2024-01-15T14:30:00Z"
  }
]
```

---

### Mark Messages as Read (REST)

**POST** `/chat/matches/{match_id}/read`

**Requires Authentication**

Mark all messages up to a specific message as read (alternative to WebSocket).

**Request Body:**
```json
{
  "message_id": "bb0e8400-e29b-41d4-a716-446655440001",
  "pet_id": "770e8400-e29b-41d4-a716-446655440000"
}
```

**Response:** `200 OK`
```json
{
  "success": true
}
```

---

## Error Responses

All error responses follow this format:

**Example:** `400 Bad Request`
```json
{
  "detail": "Cannot swipe on your own pet"
}
```

**Common Status Codes:**
- `200`: Success
- `201`: Created
- `204`: No Content (success, no body)
- `400`: Bad Request (validation error, business rule violation)
- `401`: Unauthorized (invalid/missing token)
- `403`: Forbidden (authenticated but not allowed)
- `404`: Not Found
- `409`: Conflict (duplicate resource)
- `503`: Service Unavailable (feature not configured)

---

## Complete User Journey Examples

### Example 1: Complete Registration & Onboarding

**Step 1: Register**
```bash
POST /auth/register
{
  "email": "sarah@example.com",
  "password": "mySecurePass123"
}
# Response: access_token, refresh_token
# Email verification sent to inbox
```

**Step 2: Check Onboarding Status**
```bash
GET /onboarding/status
Authorization: Bearer <token>
# Response shows: current_step = "profile_basics"
```

**Step 3: Complete Profile**
```bash
PATCH /users/me
{
  "full_name": "Sarah Johnson",
  "occupation": "Veterinarian",
  "bio": "Love all animals, especially dogs!"
}
# Grants FULL_NAME achievement
```

**Step 4: Upload Profile Photo**
```bash
# 4a. Get presigned URL
POST /users/me/photo/presign
{
  "content_type": "image/jpeg"
}
# Response: upload_url, object_key

# 4b. Upload to R2 (client-side)
PUT <upload_url>
Content-Type: image/jpeg
<binary image data>

# 4c. Confirm upload
POST /users/me/photo
{
  "object_key": "users/550e8400.../profile.jpg"
}
# Grants PROFILE_PHOTO achievement
```

**Step 5: Create Pet Profile**
```bash
POST /pets
{
  "name": "Luna",
  "species": "dog",
  "breed": "Husky",
  "age_years": 2,
  "gender": "female",
  "bio": "Playful husky who loves snow!"
}
# Grants PET_CREATED achievement
# Pet is inactive until photo uploaded
```

**Step 6: Upload Pet Photo**
```bash
# 6a. Get presigned URL
POST /pets/{pet_id}/photos/presign
{
  "content_type": "image/jpeg"
}

# 6b. Upload to R2
PUT <upload_url>
Content-Type: image/jpeg
<binary image data>

# 6c. Confirm upload
POST /pets/{pet_id}/photos
{
  "object_key": "pets/770e8400.../abc123.jpg"
}
# Grants PET_PHOTO achievement
# Pet becomes active
```

**Step 7: Verify Onboarding Complete**
```bash
GET /onboarding/status
# Response: can_start_swiping = true
```

---

### Example 2: Browse, Swipe, Match, and Chat

**Step 1: Browse Available Pets**
```bash
GET /pets?species=dog&limit=20&offset=0
# Response: list of active dogs with owner info
```

**Step 2: Swipe Right on a Pet**
```bash
POST /matches/swipe
{
  "pet_id": "770e8400-e29b-41d4-a716-446655440000",  # Your pet
  "target_pet_id": "770e8400-e29b-41d4-a716-446655440001",  # Pet you like
  "action": "like"
}
# Response: is_match = false (waiting for other user)
# Notification sent to target pet owner
```

**Step 3: Check Notifications**
```bash
GET /matches/notifications?unread_only=true
# Response: list of new likes on your pets
```

**Step 4: Accept a Like (Create Match)**
```bash
POST /matches/likes/{notification_id}/accept
# Response: match_id created
# Grants FIRST_MATCH achievement (if first)
# Both users receive NEW_MATCH notification
```

**Step 5: Connect to Chat**
```javascript
const ws = new WebSocket(
  `ws://localhost:8000/api/v1/chat/ws/${matchId}?pet_id=${petId}&token=${token}`
);

ws.onopen = () => {
  console.log('Connected to chat');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'message') {
    console.log('New message:', data.data);
  }
};
```

**Step 6: Send Message**
```javascript
ws.send(JSON.stringify({
  type: 'message',
  content: 'Hi! Luna would love to play with your dog!',
  msg_type: 'text'
}));
// Grants FIRST_MESSAGE achievement (if first)
```

**Step 7: Mark as Read**
```javascript
ws.send(JSON.stringify({
  type: 'read',
  message_id: 'bb0e8400-e29b-41d4-a716-446655440000'
}));
```

---

### Example 3: Check Achievements Progress

```bash
GET /achievements/me
Authorization: Bearer <token>

# Response shows all achievements:
# - Earned: profile_photo, full_name, pet_created, pet_photo, first_match, first_message
# - Not earned: five_matches, profile_complete, verified_email
# - completion_percentage: 66%
```

---

## WebSocket Message Types Summary

### Client → Server

| Type | Purpose | Fields |
|------|---------|--------|
| `message` | Send chat message | `content`, `msg_type` |
| `read` | Mark message as read | `message_id` |
| `typing` | Typing indicator | `is_typing` |

### Server → Client

| Type | Purpose | Data Fields |
|------|---------|-------------|
| `message` | New message received | `id`, `match_id`, `sender_pet_id`, `content`, `msg_type`, `created_at` |
| `read` | Other user read messages | `pet_id`, `message_id` |
| `typing` | Other user typing | `pet_id`, `is_typing` |

---

## Authentication Flow

### Token Management

**Access Token:**
- Expires in 30 minutes (default)
- Used for API authentication
- Include in `Authorization: Bearer <token>` header

**Refresh Token:**
- Expires in 7 days (default)
- Single-use (rotated on each refresh)
- Used to get new access token

**Best Practices:**
```javascript
// Store tokens securely
localStorage.setItem('access_token', response.access_token);
localStorage.setItem('refresh_token', response.refresh_token);

// Intercept 401 errors and refresh
async function refreshAccessToken() {
  const refresh_token = localStorage.getItem('refresh_token');
  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token })
  });
  
  if (response.ok) {
    const data = await response.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return data.access_token;
  } else {
    // Refresh failed, redirect to login
    window.location.href = '/login';
  }
}

// Retry failed request with new token
async function fetchWithAuth(url, options = {}) {
  let token = localStorage.getItem('access_token');
  
  options.headers = {
    ...options.headers,
    'Authorization': `Bearer ${token}`
  };
  
  let response = await fetch(url, options);
  
  if (response.status === 401) {
    // Token expired, refresh and retry
    token = await refreshAccessToken();
    options.headers['Authorization'] = `Bearer ${token}`;
    response = await fetch(url, options);
  }
  
  return response;
}
```

---

## Rate Limiting & Pagination

### Pagination

Most list endpoints support pagination:
- `limit`: Number of items per page (default varies, max usually 100)
- `offset`: Number of items to skip

**Example:**
```bash
# Page 1
GET /pets?limit=20&offset=0

# Page 2
GET /pets?limit=20&offset=20

# Page 3
GET /pets?limit=20&offset=40
```

### Cursor-based Pagination (Messages)

Chat history uses cursor-based pagination:
```bash
# Get latest 50 messages
GET /chat/matches/{match_id}/messages?limit=50

# Get next 50 messages before oldest message
GET /chat/matches/{match_id}/messages?limit=50&before_id=<oldest_message_id>
```

---

## File Upload Process

All image uploads use a two-step process with direct R2 upload:

**Step 1: Get Presigned URL**
```javascript
const response = await fetchWithAuth('/api/v1/users/me/photo/presign', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ content_type: 'image/jpeg' })
});

const { upload_url, object_key } = await response.json();
```

**Step 2: Upload File to R2**
```javascript
await fetch(upload_url, {
  method: 'PUT',
  headers: { 'Content-Type': 'image/jpeg' },
  body: imageFile  // File or Blob
});
```

**Step 3: Confirm Upload**
```javascript
await fetchWithAuth('/api/v1/users/me/photo', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ object_key })
});
```

**Image Constraints:**
- Max size: 10 MB
- Allowed types: JPEG, PNG, WebP
- User profile: 1 photo
- Pet profile: Max 5 photos per pet

---

## Environment Variables

Frontend should configure these base URLs:

```javascript
// Development
const API_BASE_URL = 'http://localhost:8000/api/v1';
const WS_BASE_URL = 'ws://localhost:8000/api/v1';

// Production
const API_BASE_URL = 'https://api.pawsome.com/api/v1';
const WS_BASE_URL = 'wss://api.pawsome.com/api/v1';
```

---

## Achievement Types Reference

| Type | Name | Description | Icon | How to Earn |
|------|------|-------------|------|-------------|
| `profile_photo` | Picture Perfect | Upload your profile photo | 📸 | Upload first profile photo |
| `full_name` | First Steps | Add your name to profile |  | Add full_name field |
| `pet_created` | Pet Parent | Create first pet profile |  | Create first pet |
| `pet_photo` | Show & Tell | Upload pet's first photo |  | Upload first pet photo |
| `first_match` | Match Maker | Get your first match |  | Accept a like (first match) |
| `five_matches` | Popular Paw | Achieve 5 matches | | Reach 5 total matches |
| `first_message` | Breaking the Ice | Send first message |  | Send first chat message |
| `profile_complete` | All Set | Complete profile 100% |  | Fill all profile fields + active pet |
| `verified_email` | Verified | Verify email address |  | Complete email verification |

---

## Notification Types Reference

| Type | Description | When Sent | Action Required |
|------|-------------|-----------|-----------------|
| `new_like` | Someone liked your pet | User swipes right on your pet | Accept or Reject |
| `new_match` | Match created | User accepts a like | Start chatting |
| `like_rejected` | Your like was rejected | Other user rejects your like | None |

---

## Common Frontend Patterns

### Real-time Updates with WebSocket

```javascript
class ChatService {
  constructor(matchId, petId, token) {
    this.ws = new WebSocket(
      `ws://localhost:8000/api/v1/chat/ws/${matchId}?pet_id=${petId}&token=${token}`
    );
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };
  }
  
  handleMessage(data) {
    switch(data.type) {
      case 'message':
        this.onNewMessage(data.data);
        break;
      case 'typing':
        this.onTypingStatus(data.data);
        break;
      case 'read':
        this.onMessageRead(data.data);
        break;
    }
  }
  
  sendMessage(content) {
    this.ws.send(JSON.stringify({
      type: 'message',
      content: content,
      msg_type: 'text'
    }));
  }
  
  sendTyping(isTyping) {
    this.ws.send(JSON.stringify({
      type: 'typing',
      is_typing: isTyping
    }));
  }
  
  markAsRead(messageId) {
    this.ws.send(JSON.stringify({
      type: 'read',
      message_id: messageId
    }));
  }
  
  disconnect() {
    this.ws.close();
  }
}
```

---

### Polling for Notifications

```javascript
// Poll every 30 seconds for new notifications
setInterval(async () => {
  const response = await fetchWithAuth(
    '/api/v1/matches/notifications?unread_only=true'
  );
  const notifications = await response.json();
  
  if (notifications.length > 0) {
    showNotificationBadge(notifications.length);
    updateNotificationList(notifications);
  }
}, 30000);
```

### Progressive Image Upload

```javascript
async function uploadImage(file, type = 'profile') {
  // Validate file
  if (file.size > 10 * 1024 * 1024) {
    throw new Error('File too large (max 10MB)');
  }
  
  const contentType = file.type; // e.g., 'image/jpeg'
  
  // Step 1: Get presigned URL
  const endpoint = type === 'profile' 
    ? '/api/v1/users/me/photo/presign'
    : `/api/v1/pets/${petId}/photos/presign`;
    
  const presignResponse = await fetchWithAuth(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content_type: contentType })
  });
  
  const { upload_url, object_key } = await presignResponse.json();
  
  // Step 2: Upload to R2 with progress
  await fetch(upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': contentType },
    body: file
  });
  
  // Step 3: Confirm upload
  const confirmEndpoint = type === 'profile'
    ? '/api/v1/users/me/photo'
    : `/api/v1/pets/${petId}/photos`;
    
  const confirmResponse = await fetchWithAuth(confirmEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ object_key })
  });
  
  return await confirmResponse.json();
}
```

### Optimistic UI Updates

```javascript
// Swipe with optimistic UI
async function swipeOnPet(petId, targetPetId, action) {
  // Immediately update UI (optimistic)
  removeCardFromDeck(targetPetId);
  
  try {
    const response = await fetchWithAuth('/api/v1/matches/swipe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pet_id: petId, target_pet_id: targetPetId, action })
    });
    
    const result = await response.json();
    
    if (result.is_match) {
      showMatchAnimation(result.match_id);
    }
  } catch (error) {
    // Rollback on error
    addCardBackToDeck(targetPetId);
    showError('Swipe failed, please try again');
  }
}
```

---

## Testing the API

### Using cURL

**Register:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

**Login:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

**Get Profile (with auth):**
```bash
curl -X GET http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer <your_access_token>"
```

**Browse Pets (public):**
```bash
curl -X GET "http://localhost:8000/api/v1/pets?species=dog&limit=10"
```

### Using Postman/Insomnia

1. Create environment variables:
   - `base_url`: `http://localhost:8000/api/v1`
   - `access_token`: (set after login)

2. Add pre-request script to auto-refresh token

3. Create collection with all endpoints

---

## Troubleshooting

### Common Issues

**401 Unauthorized:**
- Token expired → refresh token
- Token missing → include Authorization header
- Token invalid → re-login

**400 Bad Request:**
- Check request body format
- Validate required fields
- Check field constraints (max length, etc.)

**404 Not Found:**
- Check resource ID is correct UUID format
- Ensure resource exists and is active
- Verify you have permission to access

**503 Service Unavailable:**
- Photo storage not configured
- Check R2 credentials in backend `.env`

**WebSocket Connection Failed:**
- Check token in query parameter
- Ensure match exists and you're a participant
- Verify WebSocket URL format

---

## API Changelog

### v1.0.0 (Current)

**Features:**
- ✅ User authentication (register, login, refresh, logout)
- ✅ Email verification system
- ✅ User profile management with photo upload
- ✅ Profile completion tracking
- ✅ Onboarding wizard with step-by-step guidance
- ✅ Achievement badges system (9 achievements)
- ✅ Pet profile CRUD operations
- ✅ Pet photo management (up to 5 per pet)
- ✅ Browse public pet catalog with filters
- ✅ Swipe system (like/skip)
- ✅ Match system with accept/reject
- ✅ Notification system for likes and matches
- ✅ Real-time chat via WebSocket
- ✅ Chat history and active conversations
- ✅ Privacy controls (public/matched user profiles)

---

## Support & Contact

For API questions or bug reports, contact the 6300868001 :) .

**API Documentation:** `http://localhost:8000/docs` (Swagger UI)  
**API Version:** v1  
**Last Updated:** 13 June 2026

---

**End of Documentation**
