"""
Seed script to populate the database with 10 users, their pets, and pet photos.
One user (Sarah) will have 3 pets, others will have 1 pet each.
"""
import asyncio
import uuid
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import hash_password

# Import all models to ensure proper initialization
from app.models.user import User
from app.models.pet_profile import PetProfile, PetSpecies
from app.models.pet_photo import PetPhoto
from app.models.match_preference import MatchPreference  # Import to resolve relationship
from app.models.swipe import Swipe
from app.models.match import Match
from app.models.message import Message
from app.models.notification import Notification
from app.models.block import Block
from app.models.favorite import Favorite


# Sample pet images (placeholder URLs - you can replace with real image URLs)
DOG_IMAGES = [
    "https://images.unsplash.com/photo-1587300003388-59208cc962cb",  # Golden Retriever
    "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e",  # Husky
    "https://images.unsplash.com/photo-1560807707-8cc77767d783",  # Bulldog
    "https://images.unsplash.com/photo-1558788353-f76d92427f16",  # Beagle
    "https://images.unsplash.com/photo-1537151608828-ea2b11777ee8",  # German Shepherd
    "https://images.unsplash.com/photo-1561037404-61cd46aa615b",  # Labrador
    "https://images.unsplash.com/photo-1543466835-00a7907e9de1",  # Border Collie
]

CAT_IMAGES = [
    "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba",  # Tabby
    "https://images.unsplash.com/photo-1573865526739-10c1dd481b5c",  # Maine Coon
    "https://images.unsplash.com/photo-1574158622682-e40e69881006",  # Persian
    "https://images.unsplash.com/photo-1495360010541-f48722b34f7d",  # Siamese
]

RABBIT_IMAGES = [
    "https://images.unsplash.com/photo-1585110396000-c9ffd4e4b308",  # White Rabbit
    "https://images.unsplash.com/photo-1535241749838-299277b6305f",  # Brown Rabbit
]

BIRD_IMAGES = [
    "https://images.unsplash.com/photo-1552728089-57bdde30beb3",  # Parrot
]


# User and Pet data
SEED_DATA = [
    {
        "user": {
            "email": "sarah.johnson@email.com",
            "password": "Password123!",
            "full_name": "Sarah Johnson",
            "occupation": "Veterinary Technician",
            "bio": "Animal lover with a passion for pet care. I have three wonderful pets who are my world!",
            "address": "456 Oak Street, San Francisco, CA 94102",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "preferred_match_radius_km": 25.0,
        },
        "pets": [
            {
                "name": "Max",
                "species": PetSpecies.DOG,
                "breed": "Golden Retriever",
                "age_months": 36,
                "gender": "male",
                "bio": "Friendly and energetic Golden Retriever who loves playing fetch and swimming. Great with kids and other dogs!",
                "lat": 37.7749,
                "lng": -122.4194,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 3, 15),
                "is_neutered": True,
                "is_trained": True,
                "photos": [DOG_IMAGES[0], DOG_IMAGES[0] + "?w=800&h=600&fit=crop"]
            },
            {
                "name": "Luna",
                "species": PetSpecies.CAT,
                "breed": "Maine Coon",
                "age_months": 24,
                "gender": "female",
                "bio": "Majestic Maine Coon with a fluffy coat. Very social and loves to cuddle. Gets along well with dogs too!",
                "lat": 37.7749,
                "lng": -122.4194,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 5, 10),
                "is_neutered": True,
                "is_trained": False,
                "photos": [CAT_IMAGES[1], CAT_IMAGES[1] + "?w=800&h=600&fit=crop"]
            },
            {
                "name": "Thumper",
                "species": PetSpecies.RABBIT,
                "breed": "Holland Lop",
                "age_months": 18,
                "gender": "male",
                "bio": "Adorable Holland Lop bunny with floppy ears. Very gentle and loves munching on fresh vegetables.",
                "lat": 37.7749,
                "lng": -122.4194,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 6, 20),
                "is_neutered": True,
                "is_trained": True,
                "photos": [RABBIT_IMAGES[0], RABBIT_IMAGES[0] + "?w=800&h=600&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "michael.chen@email.com",
            "password": "Password123!",
            "full_name": "Michael Chen",
            "occupation": "Software Engineer",
            "bio": "Tech enthusiast and dog lover. Working from home means more time with my furry friend!",
            "address": "789 Pine Avenue, Seattle, WA 98101",
            "latitude": 47.6062,
            "longitude": -122.3321,
            "preferred_match_radius_km": 30.0,
        },
        "pets": [
            {
                "name": "Rocky",
                "species": PetSpecies.DOG,
                "breed": "Siberian Husky",
                "age_months": 42,
                "gender": "male",
                "bio": "Energetic Husky who loves hiking and outdoor adventures. Very vocal and loves to 'talk'!",
                "lat": 47.6062,
                "lng": -122.3321,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 1, 20),
                "is_neutered": True,
                "is_trained": True,
                "photos": [DOG_IMAGES[1], DOG_IMAGES[1] + "?w=800&h=600&fit=crop", DOG_IMAGES[1] + "?w=600&h=800&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "emma.williams@email.com",
            "password": "Password123!",
            "full_name": "Emma Williams",
            "occupation": "Graphic Designer",
            "bio": "Creative soul with a soft spot for cats. My cat is my muse and constant companion.",
            "address": "123 Maple Drive, Portland, OR 97201",
            "latitude": 45.5152,
            "longitude": -122.6784,
            "preferred_match_radius_km": 20.0,
        },
        "pets": [
            {
                "name": "Whiskers",
                "species": PetSpecies.CAT,
                "breed": "Persian",
                "age_months": 30,
                "gender": "female",
                "bio": "Elegant Persian cat with a luxurious coat. Loves lazy afternoons and gentle petting. Prefers quiet environments.",
                "lat": 45.5152,
                "lng": -122.6784,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 2, 14),
                "is_neutered": True,
                "is_trained": False,
                "photos": [CAT_IMAGES[2], CAT_IMAGES[2] + "?w=800&h=600&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "james.martinez@email.com",
            "password": "Password123!",
            "full_name": "James Martinez",
            "occupation": "Fitness Trainer",
            "bio": "Active lifestyle enthusiast. Looking for pet friends who enjoy morning runs and outdoor activities!",
            "address": "567 Elm Street, Denver, CO 80202",
            "latitude": 39.7392,
            "longitude": -104.9903,
            "preferred_match_radius_km": 35.0,
        },
        "pets": [
            {
                "name": "Duke",
                "species": PetSpecies.DOG,
                "breed": "German Shepherd",
                "age_months": 48,
                "gender": "male",
                "bio": "Loyal and protective German Shepherd. Excellent running companion and very well-trained. Great with active families.",
                "lat": 39.7392,
                "lng": -104.9903,
                "is_vaccinated": True,
                "vaccination_date": date(2023, 12, 10),
                "is_neutered": True,
                "is_trained": True,
                "photos": [DOG_IMAGES[4], DOG_IMAGES[4] + "?w=800&h=600&fit=crop", DOG_IMAGES[4] + "?w=600&h=800&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "olivia.brown@email.com",
            "password": "Password123!",
            "full_name": "Olivia Brown",
            "occupation": "Elementary School Teacher",
            "bio": "Teacher by day, pet mom always! Love socializing my pup with other friendly dogs.",
            "address": "234 Birch Lane, Austin, TX 78701",
            "latitude": 30.2672,
            "longitude": -97.7431,
            "preferred_match_radius_km": 40.0,
        },
        "pets": [
            {
                "name": "Bella",
                "species": PetSpecies.DOG,
                "breed": "Labrador Retriever",
                "age_months": 28,
                "gender": "female",
                "bio": "Sweet and gentle Labrador who loves everyone she meets. Great with children and very patient. Loves water!",
                "lat": 30.2672,
                "lng": -97.7431,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 4, 5),
                "is_neutered": True,
                "is_trained": True,
                "photos": [DOG_IMAGES[5], DOG_IMAGES[5] + "?w=800&h=600&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "daniel.lee@email.com",
            "password": "Password123!",
            "full_name": "Daniel Lee",
            "occupation": "Architect",
            "bio": "Design enthusiast with a curious cat companion. Always looking for interesting cat playdates!",
            "address": "890 Cedar Court, Boston, MA 02108",
            "latitude": 42.3601,
            "longitude": -71.0589,
            "preferred_match_radius_km": 15.0,
        },
        "pets": [
            {
                "name": "Shadow",
                "species": PetSpecies.CAT,
                "breed": "Siamese",
                "age_months": 20,
                "gender": "male",
                "bio": "Curious and talkative Siamese cat. Very social and enjoys meeting new feline friends. Quite the acrobat!",
                "lat": 42.3601,
                "lng": -71.0589,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 7, 1),
                "is_neutered": True,
                "is_trained": False,
                "photos": [CAT_IMAGES[3], CAT_IMAGES[3] + "?w=800&h=600&fit=crop", CAT_IMAGES[3] + "?w=600&h=800&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "sophia.garcia@email.com",
            "password": "Password123!",
            "full_name": "Sophia Garcia",
            "occupation": "Marketing Manager",
            "bio": "Marketing pro and dog enthusiast. My pup is my best colleague during work-from-home days!",
            "address": "345 Willow Way, Miami, FL 33101",
            "latitude": 25.7617,
            "longitude": -80.1918,
            "preferred_match_radius_km": 45.0,
        },
        "pets": [
            {
                "name": "Charlie",
                "species": PetSpecies.DOG,
                "breed": "Beagle",
                "age_months": 32,
                "gender": "male",
                "bio": "Friendly Beagle with an amazing sense of smell. Loves sniffing adventures and making new friends at the dog park.",
                "lat": 25.7617,
                "lng": -80.1918,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 3, 25),
                "is_neutered": True,
                "is_trained": True,
                "photos": [DOG_IMAGES[3], DOG_IMAGES[3] + "?w=800&h=600&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "noah.anderson@email.com",
            "password": "Password123!",
            "full_name": "Noah Anderson",
            "occupation": "Photographer",
            "bio": "Professional photographer specializing in pet photography. My dog is my favorite model!",
            "address": "678 Spruce Street, Chicago, IL 60601",
            "latitude": 41.8781,
            "longitude": -87.6298,
            "preferred_match_radius_km": 50.0,
        },
        "pets": [
            {
                "name": "Cooper",
                "species": PetSpecies.DOG,
                "breed": "Border Collie",
                "age_months": 26,
                "gender": "male",
                "bio": "Intelligent and agile Border Collie. Loves learning new tricks and playing frisbee. Super photogenic!",
                "lat": 41.8781,
                "lng": -87.6298,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 5, 18),
                "is_neutered": True,
                "is_trained": True,
                "photos": [DOG_IMAGES[6], DOG_IMAGES[6] + "?w=800&h=600&fit=crop", DOG_IMAGES[6] + "?w=600&h=800&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "ava.wilson@email.com",
            "password": "Password123!",
            "full_name": "Ava Wilson",
            "occupation": "Yoga Instructor",
            "bio": "Zen lifestyle and cat lover. My cat often joins me during my yoga sessions at home!",
            "address": "901 Ash Boulevard, Phoenix, AZ 85001",
            "latitude": 33.4484,
            "longitude": -112.0740,
            "preferred_match_radius_km": 25.0,
        },
        "pets": [
            {
                "name": "Mittens",
                "species": PetSpecies.CAT,
                "breed": "Tabby",
                "age_months": 22,
                "gender": "female",
                "bio": "Relaxed and affectionate Tabby cat. Enjoys peaceful environments and sunbathing. Very gentle and calm.",
                "lat": 33.4484,
                "lng": -112.0740,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 6, 8),
                "is_neutered": True,
                "is_trained": False,
                "photos": [CAT_IMAGES[0], CAT_IMAGES[0] + "?w=800&h=600&fit=crop"]
            }
        ]
    },
    {
        "user": {
            "email": "ethan.thomas@email.com",
            "password": "Password123!",
            "full_name": "Ethan Thomas",
            "occupation": "Real Estate Agent",
            "bio": "Always on the go but my bulldog keeps me grounded. Looking for playmates for lazy weekend hangouts!",
            "address": "432 Redwood Drive, San Diego, CA 92101",
            "latitude": 32.7157,
            "longitude": -117.1611,
            "preferred_match_radius_km": 30.0,
        },
        "pets": [
            {
                "name": "Tank",
                "species": PetSpecies.DOG,
                "breed": "English Bulldog",
                "age_months": 40,
                "gender": "male",
                "bio": "Laid-back English Bulldog with a big personality. Loves lounging and short walks. Great apartment dog!",
                "lat": 32.7157,
                "lng": -117.1611,
                "is_vaccinated": True,
                "vaccination_date": date(2024, 2, 28),
                "is_neutered": True,
                "is_trained": True,
                "photos": [DOG_IMAGES[2], DOG_IMAGES[2] + "?w=800&h=600&fit=crop", DOG_IMAGES[2] + "?w=600&h=800&fit=crop"]
            }
        ]
    }
]


async def create_pet_photo(pet_id: uuid.UUID, url: str, is_primary: bool, sort_order: int) -> PetPhoto:
    """Create a pet photo record."""
    return PetPhoto(
        id=uuid.uuid4(),
        pet_id=pet_id,
        object_key=f"pets/{pet_id}/{uuid.uuid4()}.jpg",
        url=url,
        is_primary=is_primary,
        sort_order=sort_order,
    )


async def seed_database():
    """Seed the database with users, pets, and photos."""
    print("Starting database seeding...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if data already exists
            from sqlalchemy import select
            result = await session.execute(select(User).limit(1))
            existing_users = result.scalars().first()
            
            if existing_users:
                print("Database already contains users. Skipping seed.")
                return
            
            # Create all users and their pets
            for idx, data in enumerate(SEED_DATA, 1):
                print(f"\nCreating user {idx}/10: {data['user']['full_name']}")
                
                # Create user
                user = User(
                    id=uuid.uuid4(),
                    email=data['user']['email'],
                    password_hash=hash_password(data['user']['password']),
                    is_verified=True,
                    full_name=data['user']['full_name'],
                    occupation=data['user']['occupation'],
                    bio=data['user']['bio'],
                    address=data['user']['address'],
                    latitude=data['user']['latitude'],
                    longitude=data['user']['longitude'],
                    preferred_match_radius_km=data['user']['preferred_match_radius_km'],
                )
                session.add(user)
                
                # Create pets for this user
                for pet_idx, pet_data in enumerate(data['pets'], 1):
                    print(f"  Creating pet {pet_idx}: {pet_data['name']} ({pet_data['species'].value})")
                    
                    pet = PetProfile(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        name=pet_data['name'],
                        species=pet_data['species'],
                        breed=pet_data['breed'],
                        age_months=pet_data['age_months'],
                        gender=pet_data['gender'],
                        bio=pet_data['bio'],
                        lat=pet_data['lat'],
                        lng=pet_data['lng'],
                        is_active=True,
                        is_vaccinated=pet_data['is_vaccinated'],
                        vaccination_date=pet_data['vaccination_date'],
                        is_neutered=pet_data['is_neutered'],
                        is_trained=pet_data['is_trained'],
                    )
                    session.add(pet)
                    
                    # Create photos for this pet
                    for photo_idx, photo_url in enumerate(pet_data['photos']):
                        photo = await create_pet_photo(
                            pet_id=pet.id,
                            url=photo_url,
                            is_primary=(photo_idx == 0),  # First photo is primary
                            sort_order=photo_idx,
                        )
                        session.add(photo)
                        print(f"    Added photo {photo_idx + 1}/{len(pet_data['photos'])}")
            
            # Commit all changes
            await session.commit()
            print("\n✅ Database seeding completed successfully!")
            print(f"\nCreated:")
            print(f"  - 10 users")
            print(f"  - 12 pets (Sarah has 3 pets, others have 1 each)")
            print(f"  - Multiple photos per pet")
            
            print("\n📍 Geographic distribution:")
            print("  - San Francisco, CA: Sarah Johnson (Max, Luna, Thumper)")
            print("  - Seattle, WA: Michael Chen (Rocky)")
            print("  - Portland, OR: Emma Williams (Whiskers)")
            print("  - Denver, CO: James Martinez (Duke)")
            print("  - Austin, TX: Olivia Brown (Bella)")
            print("  - Boston, MA: Daniel Lee (Shadow)")
            print("  - Miami, FL: Sophia Garcia (Charlie)")
            print("  - Chicago, IL: Noah Anderson (Cooper)")
            print("  - Phoenix, AZ: Ava Wilson (Mittens)")
            print("  - San Diego, CA: Ethan Thomas (Tank)")
            
            print("\n🔐 Login credentials (all users):")
            print("  Password: Password123!")
            print("\n  Example logins:")
            print("  - sarah.johnson@email.com")
            print("  - michael.chen@email.com")
            print("  - emma.williams@email.com")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error during seeding: {e}")
            raise


async def main():
    """Main function to run the seed script."""
    try:
        await seed_database()
    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
