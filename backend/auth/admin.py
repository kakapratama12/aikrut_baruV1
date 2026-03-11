import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import ADMIN_JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS, SUPER_ADMIN_USERNAME

security = HTTPBearer()

def create_admin_token(username: str) -> str:
    payload = {
        "username": username,
        "is_admin": True,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, ADMIN_JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, ADMIN_JWT_SECRET, algorithms=[JWT_ALGORITHM])
        is_admin = payload.get("is_admin")
        username = payload.get("username")
        
        if not is_admin or username != SUPER_ADMIN_USERNAME:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        return {"username": username, "is_admin": True}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid admin token")
