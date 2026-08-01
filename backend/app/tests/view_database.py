"""
Script to view current database contents
"""
import asyncio
from sqlalchemy import select

from app.core.database import AsyncSessionLocal

# Import all models to ensure proper initialization
from app.models.user import User
from app.models.pet_profile import PetProfile
from app.models.pet_photo import PetPhoto
from app.models.match_preference import MatchPreference
from app.models.swipe import Swipe
from app.models.match import Match
from app.models.message import Message
from app.models.notification import Notification
from app.models.block import Block
from app.models.favorite import Favorite


async def view_database():
    """View current database contents."""
    async with AsyncSessionLocal() as session:
        try:
            # Get all users
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            print(f"\n{'='*80}")
            print(f"CURRENT DATABASE CONTENTS")
            print(f"{'='*80}\n")
            
            print(f"Total Users: {len(users)}\n")
            
            for idx, user in enumerate(users, 1):
                print(f"\n{'-'*80}")
                print(f"User {idx}: {user.full_name or 'N/A'}")
                print(f"  Email: {user.email}")
                print(f"  Occupation: {user.occupation or 'N/A'}")
                print(f"  Location: {user.address or 'N/A'}")
                print(f"  Coordinates: ({user.latitude}, {user.longitude})")
                
                # Get pets for this user
                pet_result = await session.execute(
                    select(PetProfile).where(PetProfile.user_id == user.id)
                )
                pets = pet_result.scalars().all()
                
                print(f"  Pets ({len(pets)}):")
                for pet in pets:
                    # Get photos for this pet
                    photo_result = await session.execute(
                        select(PetPhoto).where(PetPhoto.pet_id == pet.id)
                    )
                    photos = photo_result.scalars().all()
                    
                    print(f"    - {pet.name} ({pet.species.value}, {pet.breed})")
                    print(f"      Age: {pet.age_months} months, Gender: {pet.gender}")
                    print(f"      Bio: {pet.bio[:60]}..." if pet.bio and len(pet.bio) > 60 else f"      Bio: {pet.bio}")
                    print(f"      Health: Vaccinated={pet.is_vaccinated}, Neutered={pet.is_neutered}, Trained={pet.is_trained}")
                    print(f"      Photos: {len(photos)}")
            
            print(f"\n{'='*80}\n")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main function."""
    await view_database()


if __name__ == "__main__":
    asyncio.run(main())
