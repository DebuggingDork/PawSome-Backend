"""
Script to clear all data and reseed the database with fresh test data
"""
import asyncio
from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def clear_and_seed():
    """Clear all data and reseed."""
    async with AsyncSessionLocal() as session:
        try:
            print("Clearing all data from database...")
            
            # Delete from tables in correct order (respecting foreign keys)
            tables_in_order = [
                'pet_photos',
                'messages',
                'chat_participants',
                'matches',
                'swipes',
                'notifications',
                'blocks',
                'favorites',
                'reports',
                'user_achievements',
                'message_reactions',
                'pet_profiles',
                'match_preferences',
                'users'
            ]
            
            for table in tables_in_order:
                try:
                    result = await session.execute(text(f"DELETE FROM {table};"))
                    print(f"  Cleared {table}")
                except Exception as e:
                    print(f"  Skipped {table} (may not exist): {e}")
            
            await session.commit()
            print("\n✅ All data cleared successfully!")
            print("\n" + "="*80)
            print("Now run: python seed_database.py")
            print("="*80 + "\n")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main function."""
    print("\n⚠️  WARNING: This will delete ALL data from the database!")
    print("="*80)
    await clear_and_seed()


if __name__ == "__main__":
    asyncio.run(main())
