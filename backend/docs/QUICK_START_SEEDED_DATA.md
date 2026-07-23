# Quick Start with Seeded Data

## What Was Done

### 1. ✅ Database Seeded
- **10 users** with complete profiles (names, occupations, bios, locations)
- **12 pets** (Sarah has 3 pets, others have 1 each)
- **Multiple photos** per pet
- **Real US city coordinates** for location-based matching
- **Complete health records** (vaccination, neutering, training status)

### 2. ✅ Browse Filtering Enhanced
Added new filtering options to `/matches/browse`:
- **Breed filter** - Search by breed name (partial match)
- **Health filters** - Filter by vaccination, neutering, training status
- **Location optional** - Works without coordinates (shows all pets)

### 3. ✅ New Breeds Endpoint
Created `/matches/breeds` to get all registered breeds for dropdown menus

## How to Use

### Step 1: Start the Backend
```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

### Step 2: Login with Test User
All users have password: `Password123!`

**Login as Sarah Johnson** (she has 3 pets!):
```json
POST /api/v1/auth/login
{
  "email": "sarah.johnson@email.com",
  "password": "Password123!"
}
```

### Step 3: Get Your Pets
```http
GET /api/v1/pets/me
Authorization: Bearer YOUR_TOKEN
```

### Step 4: Browse Pets
```http
GET /api/v1/matches/browse?pet_id=YOUR_PET_ID&radius=500
Authorization: Bearer YOUR_TOKEN
```

**With filters:**
```http
GET /api/v1/matches/browse?pet_id=YOUR_PET_ID&radius=500&breed=Golden&is_vaccinated=true
Authorization: Bearer YOUR_TOKEN
```

### Step 5: Get Breeds for Dropdown
```http
GET /api/v1/matches/breeds
Authorization: Bearer YOUR_TOKEN
```

Or filter by species:
```http
GET /api/v1/matches/breeds?species=dog
Authorization: Bearer YOUR_TOKEN
```

## Test Users

| Email | Password | Name | Location | Pets |
|-------|----------|------|----------|------|
| sarah.johnson@email.com | Password123! | Sarah Johnson | San Francisco | 3 (Max, Luna, Thumper) |
| michael.chen@email.com | Password123! | Michael Chen | Seattle | 1 (Rocky) |
| emma.williams@email.com | Password123! | Emma Williams | Portland | 1 (Whiskers) |
| james.martinez@email.com | Password123! | James Martinez | Denver | 1 (Duke) |
| olivia.brown@email.com | Password123! | Olivia Brown | Austin | 1 (Bella) |
| daniel.lee@email.com | Password123! | Daniel Lee | Boston | 1 (Shadow) |
| sophia.garcia@email.com | Password123! | Sophia Garcia | Miami | 1 (Charlie) |
| noah.anderson@email.com | Password123! | Noah Anderson | Chicago | 1 (Cooper) |
| ava.wilson@email.com | Password123! | Ava Wilson | Phoenix | 1 (Mittens) |
| ethan.thomas@email.com | Password123! | Ethan Thomas | San Diego | 1 (Tank) |

## Available Breeds
- Beagle
- Border Collie
- English Bulldog
- German Shepherd
- Golden Retriever
- Holland Lop (rabbit)
- Labrador Retriever
- Maine Coon (cat)
- Persian (cat)
- Siberian Husky
- Siamese (cat)
- Tabby (cat)

## Browse Filters Available

### Required
- `pet_id` - Your pet doing the browsing

### Optional
- `radius` (1-500km, default: 50) - Search radius
- `species` - dog, cat, rabbit, bird, other
- `breed` - Partial breed name (e.g., "Golden" matches "Golden Retriever")
- `gender` - male, female
- `age_min` - Minimum age in months
- `age_max` - Maximum age in months
- `is_vaccinated` - true/false
- `is_neutered` - true/false
- `is_trained` - true/false
- `limit` (1-50, default: 50) - Max results

## Why "No pets nearby"?

If you see this message, try:

1. **Increase radius**: Use `radius=500` to see all pets across USA
2. **Remove filters**: Start with no filters, then add them one by one
3. **Check your pet**: Make sure you're using correct `pet_id` from `/pets/me`
4. **Location**: If you have location set, pets need to be within radius

## Testing

Run the automated test:
```bash
cd backend
.venv\Scripts\python.exe test_browse_with_seeded_data.py
```

This will test:
- ✅ Login
- ✅ Get pets
- ✅ Browse (no filters)
- ✅ Breed filter
- ✅ Species filter
- ✅ Health filters
- ✅ Get breeds list

## Frontend Integration Checklist

- [ ] Add breed searchable dropdown
- [ ] Populate breeds from `/matches/breeds` endpoint
- [ ] Add health filter checkboxes (vaccinated, neutered, trained)
- [ ] Add distance radius slider (1-500km)
- [ ] Show active filter badges
- [ ] Add "Clear filters" button
- [ ] Handle "no results" vs "no filters" states

## Files Created

1. `seed_database.py` - Seeds 10 users, 12 pets with photos
2. `clear_and_seed.py` - Clears database and reseeds
3. `view_database.py` - Views current database contents
4. `test_browse_with_seeded_data.py` - Tests browse functionality
5. `SEEDING_README.md` - Detailed seeding documentation
6. `BROWSE_FILTERING_GUIDE.md` - Complete filtering guide
7. This file - Quick start guide

## Need Help?

See detailed guides:
- `SEEDING_README.md` - Database seeding details
- `BROWSE_FILTERING_GUIDE.md` - Complete API documentation
