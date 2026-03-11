from enum import Enum
from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRole(str, Enum):
    hr_admin = "hr_admin"
    manager = "manager"
    viewer = "viewer"
    employee = "employee"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole = UserRole.hr_admin
    is_platform_admin: bool = False

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    company_id: Optional[str] = None
    role: UserRole = UserRole.hr_admin
    is_platform_admin: bool = False
    created_at: str
    is_approved: Optional[bool] = False
    is_active: Optional[bool] = False
    credits: Optional[float] = 0.0
    expiry_date: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ApproveUserRequest(BaseModel):
    company_id: str
    role: UserRole
    credits: float = 100.0

class UserUpdateByAdmin(BaseModel):
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None
    credits: Optional[float] = None
    expiry_date: Optional[str] = None
