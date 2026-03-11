import uuid
from typing import Optional, List
from pydantic import BaseModel, Field

class CompanyValue(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    weight: float  # 0-100, total must equal 100

class CompanyCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    industry: Optional[str] = ""
    website: Optional[str] = ""
    values: List[CompanyValue] = []

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    values: Optional[List[CompanyValue]] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    description: str
    industry: str
    website: str
    values: List[CompanyValue]
    created_at: str
    updated_at: str

class AdminCompanyCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    industry: Optional[str] = ""
    website: Optional[str] = ""
    subscription_tier: str = "free"  # free | pro | enterprise
    credits_balance: float = 0.0
    expiry_date: Optional[str] = None

class AdminCompanyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    subscription_tier: Optional[str] = None
    credits_balance: Optional[float] = None
    expiry_date: Optional[str] = None
    is_active: Optional[bool] = None

class AdminCompanyResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    industry: str = ""
    website: str = ""
    values: List[CompanyValue] = []
    subscription_tier: str = "free"
    credits_balance: float = 0.0
    expiry_date: Optional[str] = None
    is_active: bool = True
    created_at: str
    updated_at: str
