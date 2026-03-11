import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from slowapi import Limiter
from slowapi.util import get_remote_address

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'aikrut')]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable must be set")
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Super Admin Configuration
SUPER_ADMIN_USERNAME = "admin"
SUPER_ADMIN_PASSWORD = os.environ.get('SUPER_ADMIN_PASSWORD')
if not SUPER_ADMIN_PASSWORD:
    raise ValueError("SUPER_ADMIN_PASSWORD environment variable must be set")
ADMIN_JWT_SECRET = os.environ.get('ADMIN_JWT_SECRET')
if not ADMIN_JWT_SECRET:
    raise ValueError("ADMIN_JWT_SECRET environment variable must be set")

# Configure Rate Limiter
limiter = Limiter(key_func=get_remote_address)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== DATABASE INDEXES ====================

async def create_indexes():
    """Create database indexes for better query performance."""
    try:
        # Users collection indexes
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
        await db.users.create_index("company_id")
        await db.users.create_index("is_approved")
        await db.users.create_index("is_active")
        await db.users.create_index("created_at")
        
        # Companies collection indexes
        await db.companies.create_index("id", unique=True)
        
        # Jobs collection indexes
        await db.jobs.create_index("id", unique=True)
        await db.jobs.create_index("company_id")
        await db.jobs.create_index("created_at")
        
        # Candidates collection indexes
        await db.candidates.create_index("id", unique=True)
        await db.candidates.create_index("company_id")
        await db.candidates.create_index("email")
        await db.candidates.create_index("created_at")
        
        # Analyses collection indexes
        await db.analyses.create_index("id", unique=True)
        await db.analyses.create_index("user_id")
        await db.analyses.create_index("job_id")
        await db.analyses.create_index("candidate_id")
        await db.analyses.create_index("created_at")
        
        # Credit usage logs indexes
        await db.credit_usage_logs.create_index("id", unique=True)
        await db.credit_usage_logs.create_index("user_id")
        await db.credit_usage_logs.create_index("created_at")
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.warning(f"Index creation warning (may already exist): {e}")

