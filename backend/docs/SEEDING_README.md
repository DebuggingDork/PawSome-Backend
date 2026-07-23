# Database Seeding Guide

## Overview
This seed script populates the PawSome database with realistic test data including:
- **10 users** with complete profiles
- **12 pets** (one user has 3 pets, others have 1 each)
- **Multiple photos** per pet
- **Geographic diversity** across major US cities
- **Complete health records** and vaccination data

## What Gets Seeded

### Users (10 total)
1. **Sarah Johnson** - San Francisco, CA (Veterinary Technician) - **HAS 3 PETS**
2. **Michael Chen** - Seattle, WA (Software Engineer)
3. **Emma Williams** - Portland, OR (Graphic Designer)
4. **James Martinez** - Denver, CO (Fitness Trainer)
5. **Olivia Brown** - Austin, TX (Elementary School Teacher)
6. **Daniel Lee** - Boston, MA (Architect)
7. **Sophia Garcia** - Miami, FL (Marketing Manager)
8. **Noah Anderson** - Chicago, IL (Photographer)
9. **Ava Wilson** - Phoenix, AZ (Yoga Instructor)
10. **Ethan Thomas** - San Diego, CA (Real Estate Agent)

### Pets (12 total)

#### Sarah's 3 Pets:
- **Max** - Golden Retriever (male, 36 months)
- **Luna** - Maine Coon cat (female, 24 months)
- **Thumper** - Holland Lop rabbit (male, 18 months)

#### Other Users' Pets:
- **Rocky** - Siberian Husky (Michael's)
- **Whiskers** - Persian cat (Emma's)
- **Duke** - German Shepherd (James's)
- **Bella** - Labrador Retriever (Olivia's)
- **Shadow** - Siamese cat (Daniel's)
- **Charlie** - Beagle (Sophia's)
- **Cooper** - Border Collie (Noah's)
- **Mittens** - Tabby cat (Ava's)
- **Tank** - English Bulldog (Ethan's)

### Features Include:
- ✅ Unique names, bios, and owner details
- ✅ Real latitude/longitude coordinates for each city
- ✅ Vaccination records and health data
- ✅ Multiple photos per pet (2-3 photos each)
- ✅ Diverse pet species: Dogs, Cats, and a Rabbit
- ✅ Various breeds and ages
- ✅ Complete user profiles with occupations and addresses

## Running the Seed Script

### Prerequisites
1. Database must be running
2. Alembic migrations must be applied
3. Virtual environment must be activated

### Steps

```bash
# 1. Navigate to backend directory
cd backend

# 2. Activate virtual environment (if not already activated)
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Mac/Linux

# 3. Run the seed script
python seed_database.py
```

### Expected Output
```
Starting database seeding...

Creating user 1/10: Sarah Johnson
  Creating pet 1: Max (dog)
    Added photo 1/2
    Added photo 2/2
  Creating pet 2: Luna (cat)
    Added photo 1/2
    Added photo 2/2
  Creating pet 3: Thumper (rabbit)
    Added photo 1/2
    Added photo 2/2

Creating user 2/10: Michael Chen
  Creating pet 1: Rocky (dog)
    Added photo 1/3
    Added photo 2/3
    Added photo 3/3

...

✅ Database seeding completed successfully!

Created:
  - 10 users
  - 12 pets (Sarah has 3 pets, others have 1 each)
  - Multiple photos per pet
```

## Login Credentials

All users have the same password for testing:
**Password:** `Password123!`

### Example Login Emails:
- sarah.johnson@email.com (has 3 pets!)
- michael.chen@email.com
- emma.williams@email.com
- james.martinez@email.com
- olivia.brown@email.com
- daniel.lee@email.com
- sophia.garcia@email.com
- noah.anderson@email.com
- ava.wilson@email.com
- ethan.thomas@email.com

## Geographic Distribution

The pets are distributed across major US cities for realistic location-based matching:

| City | State | User | Pet(s) |
|------|-------|------|--------|
| San Francisco | CA | Sarah Johnson | Max, Luna, Thumper |
| Seattle | WA | Michael Chen | Rocky |
| Portland | OR | Emma Williams | Whiskers |
| Denver | CO | James Martinez | Duke |
| Austin | TX | Olivia Brown | Bella |
| Boston | MA | Daniel Lee | Shadow |
| Miami | FL | Sophia Garcia | Charlie |
| Chicago | IL | Noah Anderson | Cooper |
| Phoenix | AZ | Ava Wilson | Mittens |
| San Diego | CA | Ethan Thomas | Tank |

## Troubleshooting

### "Database already contains users"
The script automatically checks if data exists and won't duplicate. To reseed:
1. Clear the database or drop/recreate tables
2. Run migrations again: `alembic upgrade head`
3. Run the seed script

### Import Errors
Make sure you're in the backend directory and the virtual environment is activated.

### Connection Errors
Verify your `.env` file has correct database credentials and the database is running.

## Notes
- Pet photos use Unsplash placeholder URLs
- All pets have vaccination records and health data
- Sarah Johnson is the only user with 3 pets (as requested)
- Each user has unique biographical information
- All locations use real city coordinates
