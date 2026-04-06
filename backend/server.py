from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
import os

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from backend.config import db, limiter, create_indexes
from backend.routes import auth, admin, company, jobs, candidates, analysis, settings, dashboard, assessment, employees

# Create the main app
app = FastAPI(title="Aikrut - Smart HR Assistant")
api_router = APIRouter(prefix="/api")

# Configure Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[origin.strip() for origin in os.environ.get('CORS_ORIGINS', '').split(',') if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def ensure_test_user():
    """Ensure a persistent testing account exists based on env variables."""
    test_email = os.environ.get("TEST_USER_EMAIL")
    test_password = os.environ.get("TEST_USER_PASSWORD")
    if test_email and test_password:
        existing = await db.users.find_one({"email": test_email})
        from backend.auth.dependencies import hash_password
        hashed_pw = hash_password(test_password)
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
            import uuid
            from datetime import datetime, timezone
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

@app.on_event("startup")
async def startup_db():
    """Initialize database indexes on startup."""
    await create_indexes()
    await ensure_test_user()

@app.on_event("shutdown")
async def shutdown_db_client():
    from backend.config import client
    client.close()

# Include all modular routers
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(company.router)
api_router.include_router(jobs.router)
api_router.include_router(candidates.router)
api_router.include_router(analysis.router)
api_router.include_router(settings.router)
api_router.include_router(dashboard.router)
api_router.include_router(assessment.router)
api_router.include_router(employees.router, prefix="/employees", tags=["Employees"])

app.include_router(api_router)
