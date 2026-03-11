import asyncio
import os
import uuid
from datetime import datetime, timezone
import passlib.context
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb://mongo:27017")
db = client["aikrut"]

pwd_context = passlib.context.CryptContext(schemes=["bcrypt"], deprecated="auto")

async def ensure_test_user():
    test_email = os.environ.get("TEST_USER_EMAIL", "testagent@example.com")
    test_password = os.environ.get("TEST_USER_PASSWORD", "admin")
    
    existing = await db.users.find_one({"email": test_email})
    hashed_pw = pwd_context.hash(test_password)
    
    if existing:
        await db.users.update_one(
            {"email": test_email},
            {"$set": {
                "password": hashed_pw,
                "is_approved": True,
                "is_active": True,
                "credits": 9999.0
            }}
        )
        print(f"Test user {test_email} updated with new credentials.")
    else:
        user_id = str(uuid.uuid4())
        user = {
            "id": user_id,
            "email": test_email,
            "password": hashed_pw,
            "name": "Test Agent",
            "company_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_approved": True,
            "is_active": True,
            "credits": 9999.0,
            "expiry_date": None
        }
        await db.users.insert_one(user)
        await db.settings.insert_one({
            "user_id": user_id,
            "openrouter_api_key": "",
            "model_name": "openai/gpt-4o-mini",
            "language": "en"
        })
        print(f"Test user {test_email} created.")

if __name__ == "__main__":
    asyncio.run(ensure_test_user())
