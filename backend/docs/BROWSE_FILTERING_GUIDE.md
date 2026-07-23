# Browse & Filtering Guide

## Overview
The browse endpoint has been enhanced with comprehensive filtering options including breed search, distance filtering, and health status filters.

## Changes Made

### 1. Enhanced Browse Endpoint
**Endpoint:** `GET /matches/browse`

#### New Query Parameters Added:
- ✅ `breed` - Filter by breed (partial match, case-insensitive)
- ✅ `is_vaccinated` - Filter by vaccination status (true/false)
- ✅ `is_neutered` - Filter by neutered status (true/false)
- ✅ `is_trained` - Filter by training status (true/false)

#### Existing Parameters:
- `pet_id` (required) - Your pet ID doing the browsing
- `radius` (default: 50, range: 1-500) - Search radius in km
- `species` - Filter by species (dog, cat, rabbit, bird, other)
- `age_min` - Minimum age in months
- `age_max` - Maximum age in months
- `gender` - Filter by gender (male/female)
- `limit` (default: 50, max: 50) - Max results

#### Location Behavior:
- **With Location:** If you have latitude/longitude set, distance filtering works normally
- **Without Location:** If you don't have location, all pets are shown with 0km distance (no distance filtering)

### 2. New Breeds Endpoint
**Endpoint:** `GET /matches/breeds`

Get all unique breeds registered in the application.

#### Query Parameters:
- `species` (optional) - Filter breeds by species

#### Example Response:
```json
[
  "Beagle",
  "Border Collie",
  "English Bulldog",
  "German Shepherd",
  "Golden Retriever",
  "Holland Lop",
  "Labrador Retriever",
  "Maine Coon",
  "Persian",
  "Siberian Husky",
  "Siamese",
  "Tabby"
]
```

## Usage Examples

### 1. Start the Backend Server
```bash
cd backend
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Mac/Linux

uvicorn app.main:app --reload
```

### 2. Login with Seeded User
```bash
# Login as Sarah Johnson (has 3 pets!)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sarah.johnson@email.com",
    "password": "Password123!"
  }'
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer"
}
```

### 3. Get Your Pets
```bash
curl -X GET http://localhost:8000/api/v1/pets/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Browse Pets (No Filters)
```bash
curl -X GET "http://localhost:8000/api/v1/matches/browse?pet_id=YOUR_PET_ID&radius=500" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Browse with Breed Filter
```bash
# Find all Golden Retrievers
curl -X GET "http://localhost:8000/api/v1/matches/browse?pet_id=YOUR_PET_ID&radius=500&breed=Golden" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 6. Browse with Multiple Filters
```bash
# Find vaccinated, neutered dogs within 100km
curl -X GET "http://localhost:8000/api/v1/matches/browse?pet_id=YOUR_PET_ID&radius=100&species=dog&is_vaccinated=true&is_neutered=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 7. Get All Breeds
```bash
# All breeds
curl -X GET http://localhost:8000/api/v1/matches/breeds \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Dog breeds only
curl -X GET "http://localhost:8000/api/v1/matches/breeds?species=dog" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Seeded Test Data

### Users & Locations
All seeded users have the password: `Password123!`

| Email | Name | City | Pets | Latitude | Longitude |
|-------|------|------|------|----------|-----------|
| sarah.johnson@email.com | Sarah Johnson | San Francisco, CA | 3 (Max, Luna, Thumper) | 37.7749 | -122.4194 |
| michael.chen@email.com | Michael Chen | Seattle, WA | 1 (Rocky) | 47.6062 | -122.3321 |
| emma.williams@email.com | Emma Williams | Portland, OR | 1 (Whiskers) | 45.5152 | -122.6784 |
| james.martinez@email.com | James Martinez | Denver, CO | 1 (Duke) | 39.7392 | -104.9903 |
| olivia.brown@email.com | Olivia Brown | Austin, TX | 1 (Bella) | 30.2672 | -97.7431 |
| daniel.lee@email.com | Daniel Lee | Boston, MA | 1 (Shadow) | 42.3601 | -71.0589 |
| sophia.garcia@email.com | Sophia Garcia | Miami, FL | 1 (Charlie) | 25.7617 | -80.1918 |
| noah.anderson@email.com | Noah Anderson | Chicago, IL | 1 (Cooper) | 41.8781 | -87.6298 |
| ava.wilson@email.com | Ava Wilson | Phoenix, AZ | 1 (Mittens) | 33.4484 | -112.0740 |
| ethan.thomas@email.com | Ethan Thomas | San Diego, CA | 1 (Tank) | 32.7157 | -117.1611 |

### Pet Details

**Dogs:**
- Max - Golden Retriever (Sarah, San Francisco)
- Rocky - Siberian Husky (Michael, Seattle)  
- Duke - German Shepherd (James, Denver)
- Bella - Labrador Retriever (Olivia, Austin)
- Charlie - Beagle (Sophia, Miami)
- Cooper - Border Collie (Noah, Chicago)
- Tank - English Bulldog (Ethan, San Diego)

**Cats:**
- Luna - Maine Coon (Sarah, San Francisco)
- Whiskers - Persian (Emma, Portland)
- Shadow - Siamese (Daniel, Boston)
- Mittens - Tabby (Ava, Phoenix)

**Rabbit:**
- Thumper - Holland Lop (Sarah, San Francisco)

All pets have:
- ✅ Vaccination records
- ✅ Complete health data (vaccinated, neutered, trained status)
- ✅ Multiple photos
- ✅ Unique bios and descriptions

## Frontend Integration

### 1. Get Breeds for Dropdown
```javascript
const response = await fetch('/api/v1/matches/breeds?species=dog', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const breeds = await response.json();
// Returns: ["Beagle", "Border Collie", "English Bulldog", ...]
```

### 2. Browse with Filters
```javascript
const params = new URLSearchParams({
  pet_id: myPetId,
  radius: 100,
  species: 'dog',
  breed: 'Golden',
  is_vaccinated: true,
  is_neutered: true,
  limit: 20
});

const response = await fetch(`/api/v1/matches/browse?${params}`, {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});

const data = await response.json();
// data.candidates = array of pets with distance_km
// data.total = total count
// data.filters_applied = what filters were used
```

### 3. Example Filter UI
```javascript
// Build filter object
const filters = {
  pet_id: selectedPetId,
  radius: radiusSlider.value || 50,
  species: speciesDropdown.value || null,
  breed: breedSearch.value || null,
  age_min: ageMinInput.value || null,
  age_max: ageMaxInput.value || null,
  gender: genderRadio.value || null,
  is_vaccinated: vaccinatedCheckbox.checked ? true : null,
  is_neutered: neuteredCheckbox.checked ? true : null,
  is_trained: trainedCheckbox.checked ? true : null,
  limit: 20
};

// Remove null/undefined values
Object.keys(filters).forEach(key => 
  (filters[key] === null || filters[key] === undefined) && delete filters[key]
);

// Make request
const params = new URLSearchParams(filters);
const response = await fetch(`/api/v1/matches/browse?${params}`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

## Testing the Changes

### Run the Test Script
```bash
cd backend
.venv\Scripts\python.exe test_browse_with_seeded_data.py
```

This will:
1. Login as Sarah Johnson
2. Get her pets
3. Browse all pets
4. Test breed filter
5. Get all available breeds
6. Test species filter (cats only)
7. Test health filters (vaccinated pets)

## Troubleshooting

### "No pets nearby right now"
**Causes:**
1. **Location not set** - User needs latitude/longitude
2. **Radius too small** - Increase radius (seeded pets are across USA)
3. **Too many filters** - Remove some filters to see more results
4. **No pet to browse with** - User needs at least one active pet

**Solutions:**
- Set user location in profile
- Increase radius to 500km to see all pets
- Remove filters one by one
- Create a pet profile with photos

### "Location not set" Error
This error has been removed! Now:
- With location: Distance-based filtering works
- Without location: All pets shown with 0km distance

### Empty Breed List
Make sure:
1. Database has been seeded
2. Pets are marked as `is_active=True`
3. At least one photo per pet exists

## API Response Structure

### Browse Response
```json
{
  "candidates": [
    {
      "pet": {
        "id": "uuid",
        "name": "Max",
        "species": "dog",
        "breed": "Golden Retriever",
        "age_months": 36,
        "gender": "male",
        "bio": "Friendly dog...",
        "is_vaccinated": true,
        "is_neutered": true,
        "is_trained": true,
        "primary_photo_url": "https://...",
        "photos": [...],
        "owner": {
          "id": "uuid",
          "full_name": "Sarah Johnson",
          "occupation": "Veterinary Technician",
          "profile_photo_url": "https://..."
        }
      },
      "distance_km": 12.45,
      "calculated_at": "2024-07-23T10:30:00Z"
    }
  ],
  "total": 15,
  "filters_applied": {
    "radius_km": 50,
    "species": "dog",
    "breed": "Golden",
    "age_min": null,
    "age_max": null,
    "gender": null,
    "is_vaccinated": true,
    "is_neutered": null,
    "is_trained": null
  }
}
```

## Summary

### What's New
✅ Breed filter with partial matching
✅ Health status filters (vaccinated, neutered, trained)
✅ Breeds list endpoint for dropdowns
✅ Location is now optional (shows all if not set)
✅ Better error handling

### Breaking Changes
❌ None! All existing functionality preserved

### Next Steps for Frontend
1. Add breed searchable dropdown
2. Add health status checkboxes
3. Show filter badges for active filters
4. Add "Clear all filters" button
5. Show "No filters applied" state differently from "No results"
