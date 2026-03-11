import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import db, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
from backend.models.user import UserRole

security = HTTPBearer()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Backward compatibility: if user doesn't have these fields, set defaults
        if "is_approved" not in user:
            user["is_approved"] = True
            user["is_active"] = True
            user["credits"] = 0.0
            user["role"] = UserRole.hr_admin.value
            user["is_platform_admin"] = False
            # Update in database for future
            await db.users.update_one(
                {"id": user_id}, 
                {"$set": {
                    "is_approved": True, 
                    "is_active": True, 
                    "credits": 0.0,
                    "role": UserRole.hr_admin.value,
                    "is_platform_admin": False
                }}
            )
        
        # Ensure role exists even if is_approved check was bypassed by older logic
        if "role" not in user:
            user["role"] = UserRole.hr_admin.value
            user["is_platform_admin"] = False
        
        # Check if user is approved and active (only for new users)
        if not user.get("is_approved", True):
            raise HTTPException(status_code=403, detail="Account pending approval. Please wait for admin approval.")
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is inactive. Please contact admin.")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def RequireRole(*allowed_roles: UserRole):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        is_platform_admin = current_user.get("is_platform_admin", False)
        if is_platform_admin:
            return current_user  # platform admin bypasses all role checks
            
        role_str = current_user.get("role", UserRole.hr_admin.value)
        try:
            role = UserRole(role_str)
        except ValueError:
            role = UserRole.hr_admin # Fallback against corrupted data
            
        if role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker

def get_company_id(current_user: dict) -> str:
    """Extract and validate company_id from the authenticated user.
    
    This is the SINGLE SOURCE OF TRUTH for tenant isolation.
    All endpoints must use this instead of query params or request body.
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=403, 
            detail="No company assigned. Please contact your administrator."
        )
    return company_id
