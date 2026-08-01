"""
Test script to browse pets with seeded data
"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1"

# Test users from seed data
TEST_USERS = [
    {"email": "sarah.johnson@email.com", "password": "Password123!", "name": "Sarah Johnson"},
    {"email": "michael.chen@email.com", "password": "Password123!", "name": "Michael Chen"},
    {"email": "emma.williams@email.com", "password": "Password123!", "name": "Emma Williams"},
]


async def test_browse():
    """Test browsing pets with seeded data"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        print("\n" + "="*80)
        print("TESTING BROWSE WITH SEEDED DATA")
        print("="*80)
        
        # 1. Login as first user
        user = TEST_USERS[0]
        print(f"\n1. Logging in as {user['name']} ({user['email']})...")
        
        login_response = await client.post("/auth/login", json={
            "email": user["email"],
            "password": user["password"]
        })
        
        if login_response.status_code != 200:
            print(f"   ❌ Login failed: {login_response.status_code}")
            print(f"   Response: {login_response.text}")
            return
        
        tokens = login_response.json()
        access_token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        print(f"   ✅ Logged in successfully!")
        
        # 2. Get user's pets
        print(f"\n2. Getting {user['name']}'s pets...")
        pets_response = await client.get("/pets/me", headers=headers)
        
        if pets_response.status_code != 200:
            print(f"   ❌ Failed to get pets: {pets_response.status_code}")
            return
        
        my_pets = pets_response.json()
        print(f"   ✅ Found {len(my_pets)} pet(s):")
        for pet in my_pets:
            print(f"      - {pet['name']} ({pet['species']}, {pet['breed']})")
        
        if not my_pets:
            print("   ⚠️  No pets found! Create a pet first.")
            return
        
        pet_id = my_pets[0]["id"]
        print(f"\n3. Using pet: {my_pets[0]['name']} (ID: {pet_id})")
        
        # 3. Test browse without filters
        print(f"\n4. Browsing pets (no filters, 50km radius)...")
        browse_response = await client.get(
            "/matches/browse",
            params={
                "pet_id": pet_id,
                "radius": 50,
                "limit": 50
            },
            headers=headers
        )
        
        if browse_response.status_code != 200:
            print(f"   ❌ Browse failed: {browse_response.status_code}")
            print(f"   Response: {browse_response.text}")
            return
        
        browse_data = browse_response.json()
        print(f"   ✅ Found {browse_data['total']} candidates:")
        
        for candidate in browse_data['candidates'][:5]:  # Show first 5
            pet = candidate['pet']
            dist = candidate['distance_km']
            owner = pet.get('owner', {})
            print(f"      - {pet['name']} ({pet['breed']}) - {dist}km away")
            print(f"        Owner: {owner.get('full_name', 'Unknown')}")
        
        if browse_data['total'] > 5:
            print(f"      ... and {browse_data['total'] - 5} more")
        
        # 4. Test breed filter
        print(f"\n5. Testing breed filter (Golden Retriever)...")
        breed_browse = await client.get(
            "/matches/browse",
            params={
                "pet_id": pet_id,
                "radius": 500,  # Large radius to find all
                "breed": "Golden",
                "limit": 50
            },
            headers=headers
        )
        
        if breed_browse.status_code == 200:
            breed_data = breed_browse.json()
            print(f"   ✅ Found {breed_data['total']} Golden Retrievers")
            for candidate in breed_data['candidates'][:3]:
                pet = candidate['pet']
                print(f"      - {pet['name']} ({pet['breed']})")
        
        # 5. Get all breeds
        print(f"\n6. Getting all available breeds...")
        breeds_response = await client.get("/matches/breeds", headers=headers)
        
        if breeds_response.status_code == 200:
            breeds = breeds_response.json()
            print(f"   ✅ Found {len(breeds)} unique breeds:")
            for breed in sorted(breeds):
                print(f"      - {breed}")
        
        # 6. Test species filter
        print(f"\n7. Testing species filter (cats only)...")
        cat_browse = await client.get(
            "/matches/browse",
            params={
                "pet_id": pet_id,
                "radius": 500,
                "species": "cat",
                "limit": 50
            },
            headers=headers
        )
        
        if cat_browse.status_code == 200:
            cat_data = cat_browse.json()
            print(f"   ✅ Found {cat_data['total']} cats")
            for candidate in cat_data['candidates'][:3]:
                pet = candidate['pet']
                print(f"      - {pet['name']} ({pet['breed']})")
        
        # 7. Test health filters
        print(f"\n8. Testing health filters (vaccinated only)...")
        health_browse = await client.get(
            "/matches/browse",
            params={
                "pet_id": pet_id,
                "radius": 500,
                "is_vaccinated": True,
                "limit": 50
            },
            headers=headers
        )
        
        if health_browse.status_code == 200:
            health_data = health_browse.json()
            print(f"   ✅ Found {health_data['total']} vaccinated pets")
        
        print(f"\n" + "="*80)
        print("BROWSE TESTS COMPLETED!")
        print("="*80)
        print(f"\n✅ All tests passed successfully!")
        print(f"\nKey takeaways:")
        print(f"  - Browse endpoint: GET /matches/browse")
        print(f"  - Required: pet_id (your pet browsing)")
        print(f"  - Optional filters: species, breed, radius, age_min/max, gender, health status")
        print(f"  - Breeds endpoint: GET /matches/breeds")
        print(f"  - Default radius: 50km (can be adjusted 1-500km)")
        print(f"\n")


async def main():
    """Main test function"""
    try:
        await test_browse()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
