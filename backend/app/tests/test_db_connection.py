"""Test database connectivity"""
import asyncio
import sys
from sqlalchemy import text
from app.core.database import engine

async def test_connection():
    """Test database connection"""
    print("Testing database connection...")
    print(f"Connection timeout: 30 seconds")
    print(f"Command timeout: 60 seconds")
    
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"✅ Connection successful! Test query returned: {row[0]}")
            
            # Get database version
            result = await conn.execute(text("SELECT version()"))
            version = result.fetchone()
            print(f"📊 PostgreSQL version: {version[0][:50]}...")
            
            return True
    except asyncio.TimeoutError:
        print("❌ Connection timeout!")
        print("Possible causes:")
        print("  1. Neon database is suspended (serverless databases auto-suspend)")
        print("  2. Network/firewall blocking the connection")
        print("  3. Database credentials are incorrect")
        print("\nSolution: Check your Neon dashboard to wake up the database")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"\nError type: {type(e).__name__}")
        return False
    finally:
        await engine.dispose()

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
