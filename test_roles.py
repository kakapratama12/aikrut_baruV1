import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

sys.path.append(".")
from backend.server import create_token
import httpx
import time
import subprocess

async def setup_users():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.aikrut
    
    await db.users.update_one(
        {"id": "test_hr_admin"},
        {"$set": {"id": "test_hr_admin", "email": "hr@test.com", "role": "hr_admin", "is_approved": True, "is_active": True}},
        upsert=True
    )
    await db.users.update_one(
        {"id": "test_viewer"},
        {"$set": {"id": "test_viewer", "email": "viewer@test.com", "role": "viewer", "is_approved": True, "is_active": True}},
        upsert=True
    )
    
if __name__ == "__main__":
    asyncio.run(setup_users())
    token_hr = create_token("test_hr_admin")
    token_viewer = create_token("test_viewer")
    
    env = os.environ.copy()
    server_process = subprocess.Popen(["backend/venv/bin/uvicorn", "backend.server:app", "--port", "8008"], env=env)
    time.sleep(3)
    
    try:
        url = "http://localhost:8008/api/competencies"
        payload = {
            "company_id": "test_company",
            "name": "Test Role Competency",
            "description": "Just testing roles",
            "type": "hard_skill",
            "levels": [
                {"level": 1, "description": "1"},
                {"level": 2, "description": "2"},
                {"level": 3, "description": "3"},
                {"level": 4, "description": "4"},
                {"level": 5, "description": "5"}
            ]
        }
        
        print("\n--- TEST 1: No Token ---")
        resp1 = httpx.post(url, json=payload)
        print(f"Status: {resp1.status_code}, Response: {resp1.json()}")
        
        print("\n--- TEST 2: Wrong Role (Viewer) ---")
        resp2 = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {token_viewer}"})
        print(f"Status: {resp2.status_code}, Response: {resp2.json()}")
        
        print("\n--- TEST 3: Correct Role (HR Admin) ---")
        resp3 = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {token_hr}"})
        print(f"Status: {resp3.status_code}")
        if resp3.status_code == 200:
            print(f"Success! ID: {resp3.json().get('id', 'N/A')}")
        else:
            print(resp3.json())

    finally:
        server_process.terminate()
