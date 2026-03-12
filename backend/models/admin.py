from typing import Optional, List
from pydantic import BaseModel

class AdminDashboardStats(BaseModel):
    total_users: int
    pending_users: int
    active_users: int
    total_jobs: int
    total_candidates: int
    total_analyses: int
    total_credits_distributed: float

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

class CreditTopupRequest(BaseModel):
    amount: float
    note: Optional[str] = "Admin topup"

class CreditEstimateResponse(BaseModel):
    operation: str
    estimated_credits: float
    note: str

class GlobalSettingsUpdate(BaseModel):
    super_admin_email: Optional[str] = None
    default_credits_new_user: Optional[float] = None
    allow_company_registration: Optional[bool] = None

class CreditRatesUpdate(BaseModel):
    rates: dict

class AdminSettingsUpdate(BaseModel):
    settings: dict

class SettingsUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    model_name: Optional[str] = None
    language: Optional[str] = None
    primary_color: Optional[str] = None  # Brand color for PDF reports
    secondary_color: Optional[str] = None  # Secondary brand color
    company_logo: Optional[str] = None  # Base64 encoded logo for PDF reports
