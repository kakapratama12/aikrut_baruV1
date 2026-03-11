from fastapi import FastAPI, APIRouter, HTTPException, Depends, File, UploadFile, Form, Query, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import httpx
import pdfplumber
import io
import json
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from backend.config import (
    db, 
    JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS, 
    SUPER_ADMIN_USERNAME, SUPER_ADMIN_PASSWORD, ADMIN_JWT_SECRET,
    limiter, logger, create_indexes
)

# Create the main app
app = FastAPI(title="Aikrut - Smart HR Assistant")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ==================== MODELS ====================

from enum import Enum
from pydantic import model_validator

# --- HR ASSESSMENT OS MODELS (PHASE 1) ---

class CompetencyType(str, Enum):
    hard_skill = "hard_skill"
    soft_skill = "soft_skill"

class CompetencyLevel(BaseModel):
    level: int  # 1-5
    description: Optional[str] = ""

class CompetencyCreate(BaseModel):
    company_id: str
    name: str
    description: str
    type: CompetencyType
    levels: List[CompetencyLevel] = []

class Competency(CompetencyCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str
    updated_at: str

class PositionCompetencyRequirement(BaseModel):
    competency_id: str
    rubric_id: Optional[str] = None
    standard_minimum: int  # 1-5
    weight_evidence: int   # %
    weight_roleplay: int   # %

class PositionCreate(BaseModel):
    company_id: str
    title: str
    department: str
    level: int  # 1-6
    required_competencies: List[PositionCompetencyRequirement] = []

class Position(PositionCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str
    updated_at: str

class EvaluationRubricCreate(BaseModel):
    company_id: str
    name: str
    evidence_mapping: List[Dict[str, Any]] = []
    roleplay_mapping: List[Dict[str, Any]] = []

class EvaluationRubric(EvaluationRubricCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str
    updated_at: str

class EmploymentType(str, Enum):
    internal = "internal"
    external = "external"

class EmployeeCreate(BaseModel):
    company_id: str
    name: str
    email: str
    current_position: str
    employment_type: EmploymentType = EmploymentType.internal
    status: str = "aktif"

class Employee(EmployeeCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str
    updated_at: str

class AssessmentStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    pending_review = "pending_review"
    approved = "approved"
    overridden = "overridden"
    request_more_info = "request_more_info"

class AssessmentPurpose(str, Enum):
    promotion = "promotion"
    hiring = "hiring"

class AIRecommendation(str, Enum):
    promote = "promote"
    hire = "hire"
    not_yet = "not_yet"
    no = "no"

class FinalOutcome(str, Enum):
    promoted = "promoted"
    hired = "hired"
    not_yet = "not_yet"
    no = "no"

class AssessmentSessionCreate(BaseModel):
    company_id: str
    person_id: str
    target_position_id: str
    purpose: AssessmentPurpose

class AssessmentSession(AssessmentSessionCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: AssessmentStatus = AssessmentStatus.pending
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None
    ai_recommendation: Optional[AIRecommendation] = None
    override_reason: Optional[str] = None
    final_outcome: Optional[FinalOutcome] = None
    credits_consumed: int = 0
    created_at: str
    decided_at: Optional[str] = None

    @model_validator(mode='after')
    def validate_override_reason(self) -> 'AssessmentSession':
        if self.final_outcome is not None and self.ai_recommendation is not None:
            # Normalize semantics for comparison 
            # (e.g. promote -> promoted, hire -> hired)
            mapping = {
                "promote": "promoted",
                "hire": "hired",
                "not_yet": "not_yet",
                "no": "no"
            }
            if mapping.get(self.ai_recommendation.value) != self.final_outcome.value:
                if not self.override_reason or not self.override_reason.strip():
                    raise ValueError("override_reason is required when final_outcome differs from ai_recommendation")
        return self

class CompetencyProfileCreate(BaseModel):
    session_id: str
    person_id: str
    company_id: str
    competency_scores: List[Dict[str, Any]] = []
    raw_evidence: Dict[str, Any] = {}
    raw_roleplay: Dict[str, Any] = {}
    narrative: Dict[str, Any] = {}

class CompetencyProfile(CompetencyProfileCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str
    updated_at: str

# --- LEGACY MODELS (DEPRECATED) ---

# Auth Models
from backend.models.user import (
    UserRole, UserCreate, UserLogin, UserResponse, TokenResponse
)

# Company Models
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

# Job Models
class PlaybookItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    weight: float  # 0-100, total per category must equal 100

class JobPlaybook(BaseModel):
    character: List[PlaybookItem] = []
    requirement: List[PlaybookItem] = []
    skill: List[PlaybookItem] = []

from typing import Union

class JobCreate(BaseModel):
    title: str
    description: Union[dict, str]
    requirements: Union[dict, str]
    location: Optional[str] = ""
    employment_type: Optional[str] = "full-time"
    salary_range: Optional[str] = ""
    playbook: Optional[JobPlaybook] = None

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[Union[dict, str]] = None
    requirements: Optional[Union[dict, str]] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_range: Optional[str] = None
    playbook: Optional[JobPlaybook] = None
    status: Optional[str] = None

class JobResponse(BaseModel):
    id: str
    company_id: str
    title: str
    description: Union[dict, str]
    requirements: Union[dict, str]
    location: str
    employment_type: str
    salary_range: str
    playbook: Optional[JobPlaybook]
    status: str
    created_at: str
    updated_at: str

# Candidate Models
class CandidateEvidence(BaseModel):
    type: str  # cv, psychotest, knowledge_test
    file_name: str
    content: str  # parsed text content
    uploaded_at: str

class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""

# ==================== TALENT TAGGING MODELS & CONSTANTS ====================

# Layer 1: Domain / Function (max 3)
LAYER_1_TAGS = [
    "OPERATIONS", "HUMAN_RESOURCES", "FINANCE", "ACCOUNTING", 
    "INFORMATION_TECHNOLOGY", "DATA_ANALYTICS", "PRODUCT", "ENGINEERING",
    "SALES", "MARKETING", "CUSTOMER_SUPPORT", "LEGAL", 
    "PROCUREMENT", "SUPPLY_CHAIN", "LOGISTICS"
]

# Layer 2: Job Family (max 3)
LAYER_2_TAGS = [
    # Operations & Admin
    "GENERAL_OPERATIONS", "GENERAL_ADMINISTRATION", "HR_OPERATIONS",
    "TALENT_ACQUISITION", "LEARNING_DEVELOPMENT", "PAYROLL_COMPLIANCE",
    "ACCOUNTING_SUPPORT", "FINANCIAL_REPORTING", "FINANCIAL_CONTROL",
    "PROCUREMENT_VENDOR_MANAGEMENT", "LEGAL_COMPLIANCE",
    # Tech
    "SOFTWARE_DEVELOPMENT", "IT_OPERATIONS", "PROJECT_MANAGEMENT",
    "PRODUCT_MANAGEMENT", "QA_TESTING", "DATA_ANALYTICS", "DATA_ENGINEERING",
    "DEVOPS_CLOUD", "UI_UX_DESIGN",
    # Sales & Marketing
    "B2B_SALES", "B2C_SALES", "KEY_ACCOUNT_MANAGEMENT", "DIGITAL_MARKETING",
    "PERFORMANCE_MARKETING", "BRAND_CONTENT", "CUSTOMER_SUPPORT", "CUSTOMER_SUCCESS",
    # Supply Chain & Engineering
    "SUPPLY_CHAIN_MANAGEMENT", "LOGISTICS_OPERATIONS", "NON_IT_ENGINEERING",
    "RESEARCH_DEVELOPMENT"
]

# Layer 4: Scope of Work (max 3)
LAYER_4_TAGS = ["OPERATIONAL", "TACTICAL", "STRATEGIC"]

# Layer definitions with metadata
LAYER_DEFINITIONS = {
    1: {"name": "Domain / Function", "max_tags": 3, "library": LAYER_1_TAGS},
    2: {"name": "Job Family", "max_tags": 3, "library": LAYER_2_TAGS},
    3: {"name": "Skill / Competency", "max_tags": 10, "library": None},  # Free text, AI normalized
    4: {"name": "Scope of Work", "max_tags": 3, "library": LAYER_4_TAGS}
}

# Logical consistency mapping: Layer 1 -> valid Layer 2 tags
LAYER_1_TO_2_MAPPING = {
    "OPERATIONS": ["GENERAL_OPERATIONS", "GENERAL_ADMINISTRATION"],
    "HUMAN_RESOURCES": ["HR_OPERATIONS", "TALENT_ACQUISITION", "LEARNING_DEVELOPMENT", "PAYROLL_COMPLIANCE"],
    "FINANCE": ["FINANCIAL_REPORTING", "FINANCIAL_CONTROL"],
    "ACCOUNTING": ["ACCOUNTING_SUPPORT", "FINANCIAL_REPORTING"],
    "INFORMATION_TECHNOLOGY": ["SOFTWARE_DEVELOPMENT", "IT_OPERATIONS", "DEVOPS_CLOUD", "QA_TESTING"],
    "DATA_ANALYTICS": ["DATA_ANALYTICS", "DATA_ENGINEERING"],
    "PRODUCT": ["PRODUCT_MANAGEMENT", "UI_UX_DESIGN"],
    "ENGINEERING": ["SOFTWARE_DEVELOPMENT", "NON_IT_ENGINEERING", "RESEARCH_DEVELOPMENT", "QA_TESTING"],
    "SALES": ["B2B_SALES", "B2C_SALES", "KEY_ACCOUNT_MANAGEMENT"],
    "MARKETING": ["DIGITAL_MARKETING", "PERFORMANCE_MARKETING", "BRAND_CONTENT"],
    "CUSTOMER_SUPPORT": ["CUSTOMER_SUPPORT", "CUSTOMER_SUCCESS"],
    "LEGAL": ["LEGAL_COMPLIANCE"],
    "PROCUREMENT": ["PROCUREMENT_VENDOR_MANAGEMENT"],
    "SUPPLY_CHAIN": ["SUPPLY_CHAIN_MANAGEMENT"],
    "LOGISTICS": ["LOGISTICS_OPERATIONS"]
}

class CandidateTag(BaseModel):
    tag_value: str
    layer: int  # 1, 2, 3, or 4
    layer_name: str
    source: str  # "AUTO" or "MANUAL"
    confidence_score: Optional[float] = None  # For AUTO tags, 0.0-1.0
    created_at: str

class TagAddRequest(BaseModel):
    tag_value: str
    layer: int

class TagExtractionResponse(BaseModel):
    tags: List[CandidateTag]
    extraction_summary: str
    evidence_used: List[str]

class CandidateResponse(BaseModel):
    id: str
    company_id: str
    name: str
    email: str
    phone: str
    evidence: List[CandidateEvidence]
    tags: Optional[List[CandidateTag]] = []
    deleted_tags: Optional[List[str]] = []  # Blacklisted tag values
    created_at: str
    updated_at: str

# Analysis Models
class ScoreBreakdown(BaseModel):
    item_id: str
    item_name: str
    raw_score: float  # 0-100
    weight: float
    weighted_score: float
    reasoning: str

class CategoryScore(BaseModel):
    category: str  # character, requirement, skill
    score: float
    breakdown: List[ScoreBreakdown]

class AnalysisResult(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    candidate_name: Optional[str] = None  # Store name for when candidate is deleted
    final_score: float
    category_scores: List[CategoryScore]
    overall_reasoning: str
    company_values_alignment: Optional[Dict[str, Any]] = None
    strengths: Optional[List[str]] = []
    gaps: Optional[List[str]] = []
    created_at: str

class BatchAnalysisRequest(BaseModel):
    job_id: str
    candidate_ids: List[str]

# Settings Models
class AISettings(BaseModel):
    openrouter_api_key: Optional[str] = ""
    model_name: str = "openai/gpt-4o-mini"
    language: str = "en"  # en or id

class SettingsUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    model_name: Optional[str] = None
    language: Optional[str] = None
    primary_color: Optional[str] = None  # Brand color for PDF reports
    secondary_color: Optional[str] = None  # Secondary brand color
    company_logo: Optional[str] = None  # Base64 encoded logo for PDF reports

# ==================== AUTH HELPERS ====================

from backend.auth.dependencies import (
    hash_password, verify_password, create_token,
    get_current_user, RequireRole, get_company_id
)

# ==================== MULTI-TENANT ADMIN MODELS ====================

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

from backend.models.user import ApproveUserRequest, UserUpdateByAdmin

# ==================== ADMIN AUTH HELPERS ====================

from backend.auth.admin import create_admin_token, get_current_admin
# AdminLogin and AdminTokenResponse were temporarily removed but I need them. Wait, I should import them if they were declared in server.py before.
# Let me just redefine AdminLogin and AdminTokenResponse in models.user or here.
class AdminLogin(BaseModel):
    username: str
    password: str

class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

# Admin Models

class AdminDashboardStats(BaseModel):
    total_users: int
    pending_users: int
    active_users: int
    total_jobs: int
    total_candidates: int
    total_analyses: int
    total_credits_distributed: float

# ==================== CREDIT SYSTEM ====================

from backend.services.credit import (
    DEFAULT_CREDIT_RATES, CreditUsageLog, CreditCheckResult,
    get_credit_rate, check_user_credits, deduct_credits, estimate_credits_for_operation
)

# ==================== AI SERVICE ====================

from backend.services.ai_service import (
    AISettings, get_ai_settings, call_openrouter, call_openrouter_with_usage
)

from backend.services.evidence import (
    parse_pdf, EVIDENCE_KEYWORDS, classify_page_by_keywords,
    parse_pdf_by_pages, classify_page_with_ai, split_pdf_into_evidence, serialize_doc
)

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "company_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_approved": False,  # Requires admin approval
        "is_active": False,    # Activated upon approval
        "credits": 0.0,        # Will be set by admin upon approval
        "expiry_date": None    # Optional, can be set by admin
    }
    
    await db.users.insert_one(user)
    
    # Create default settings
    await db.settings.insert_one({
        "user_id": user_id,
        "openrouter_api_key": "",
        "model_name": "openai/gpt-4o-mini",
        "language": "en"
    })
    
    # Return token but user will be blocked until approved
    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_data.email,
            name=user_data.name,
            company_id=None,
            created_at=user["created_at"],
            is_approved=False,
            is_active=False,
            credits=0.0,
            expiry_date=None
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            company_id=user.get("company_id"),
            created_at=user["created_at"],
            is_approved=user.get("is_approved", True),  # Default True for backward compatibility
            is_active=user.get("is_active", True),      # Default True for backward compatibility
            credits=user.get("credits", 0.0),
            expiry_date=user.get("expiry_date")
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    # Fetch fresh data from database to ensure credit balance is current
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        company_id=user.get("company_id"),
        created_at=user["created_at"],
        is_approved=user.get("is_approved", True),
        is_active=user.get("is_active", True),
        credits=user.get("credits", 0.0),
        expiry_date=user.get("expiry_date")
    )

# ==================== ADMIN ROUTES ====================

@api_router.post("/admin/login", response_model=AdminTokenResponse)
async def admin_login(credentials: AdminLogin):
    if credentials.username != SUPER_ADMIN_USERNAME or credentials.password != SUPER_ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    
    token = create_admin_token(credentials.username)
    return AdminTokenResponse(
        access_token=token,
        username=credentials.username
    )

@api_router.get("/admin/dashboard", response_model=AdminDashboardStats)
async def get_admin_dashboard(admin: dict = Depends(get_current_admin)):
    # Aggregate statistics
    total_users = await db.users.count_documents({})
    pending_users = await db.users.count_documents({"is_approved": False})
    active_users = await db.users.count_documents({"is_active": True})
    total_jobs = await db.jobs.count_documents({})
    total_candidates = await db.candidates.count_documents({})
    total_analyses = await db.analyses.count_documents({})
    
    # Calculate total credits distributed
    users_cursor = db.users.find({}, {"credits": 1})
    total_credits = 0.0
    async for user in users_cursor:
        total_credits += user.get("credits", 0.0)
    
    return AdminDashboardStats(
        total_users=total_users,
        pending_users=pending_users,
        active_users=active_users,
        total_jobs=total_jobs,
        total_candidates=total_candidates,
        total_analyses=total_analyses,
        total_credits_distributed=total_credits
    )

@api_router.get("/admin/users")
async def get_all_users(
    admin: dict = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 50,
    search: str = None
):
    """
    Get all users with pagination and optional search.
    Optimized with aggregation pipeline to avoid N+1 queries.
    """
    # Build match filter for search
    match_filter = {}
    if search:
        match_filter["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]
    
    # Aggregation pipeline for efficient stats calculation
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "companies",
                "localField": "company_id",
                "foreignField": "id",
                "as": "company_data"
            }
        },
        {
            "$addFields": {
                "company_id_for_lookup": {"$ifNull": ["$company_id", None]}
            }
        }
    ]
    
    users_cursor = db.users.aggregate(pipeline)
    users = []
    
    # Collect all user IDs and company IDs for batch queries
    user_data_list = []
    company_ids = set()
    
    async for user in users_cursor:
        # Remove _id and password
        user.pop("_id", None)
        user.pop("password", None)
        user.pop("company_data", None)
        user_data_list.append(user)
        if user.get("company_id"):
            company_ids.add(user["company_id"])
    
    # Batch queries for stats
    if user_data_list:
        # Get jobs count per company
        jobs_pipeline = [
            {"$match": {"company_id": {"$in": list(company_ids)}}} if company_ids else {"$match": {}},
            {"$group": {"_id": "$company_id", "count": {"$sum": 1}}}
        ]
        jobs_by_company = {}
        if company_ids:
            async for item in db.jobs.aggregate(jobs_pipeline):
                jobs_by_company[item["_id"]] = item["count"]
        
        # Get candidates count per company
        candidates_pipeline = [
            {"$match": {"company_id": {"$in": list(company_ids)}}} if company_ids else {"$match": {}},
            {"$group": {"_id": "$company_id", "count": {"$sum": 1}}}
        ]
        candidates_by_company = {}
        if company_ids:
            async for item in db.candidates.aggregate(candidates_pipeline):
                candidates_by_company[item["_id"]] = item["count"]
        
        # Get analyses count per user
        user_ids = [u["id"] for u in user_data_list]
        analyses_pipeline = [
            {"$match": {"user_id": {"$in": user_ids}}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}}
        ]
        analyses_by_user = {}
        async for item in db.analyses.aggregate(analyses_pipeline):
            analyses_by_user[item["_id"]] = item["count"]
        
        # Combine results
        for user in user_data_list:
            company_id = user.get("company_id")
            users.append({
                **user,
                "stats": {
                    "jobs_count": jobs_by_company.get(company_id, 0) if company_id else 0,
                    "candidates_count": candidates_by_company.get(company_id, 0) if company_id else 0,
                    "analyses_count": analyses_by_user.get(user["id"], 0)
                }
            })
    
    # Get total count for pagination
    total = await db.users.count_documents(match_filter)
    
    return {
        "users": users,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total
    }

@api_router.put("/admin/users/{user_id}")
async def update_user_by_admin(
    user_id: str, 
    update_data: UserUpdateByAdmin,
    admin: dict = Depends(get_current_admin)
):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build update dict
    update_dict = {}
    if update_data.is_approved is not None:
        update_dict["is_approved"] = update_data.is_approved
    if update_data.is_active is not None:
        update_dict["is_active"] = update_data.is_active
    if update_data.credits is not None:
        update_dict["credits"] = update_data.credits
    if update_data.expiry_date is not None:
        update_dict["expiry_date"] = update_data.expiry_date
    
    if update_dict:
        await db.users.update_one({"id": user_id}, {"$set": update_dict})
    
    # Return updated user
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    return {"user": updated_user}

@api_router.post("/admin/users/{user_id}/approve")
async def approve_user(
    user_id: str,
    request: ApproveUserRequest,
    admin: dict = Depends(get_current_admin)
):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate company exists and is active
    company = await db.companies.find_one({"id": request.company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if not company.get("is_active", True):
        raise HTTPException(status_code=400, detail="Company is inactive")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_approved": True,
            "is_active": True,
            "company_id": request.company_id,
            "role": request.role.value,
            "credits": request.credits
        }}
    )
    
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    return {"message": "User approved successfully", "user": updated_user}

@api_router.post("/admin/users/{user_id}/reject")
async def reject_user(
    user_id: str,
    admin: dict = Depends(get_current_admin)
):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_approved": False,
            "is_active": False
        }}
    )
    
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    return {"message": "User rejected", "user": updated_user}

# ==================== ADMIN: CREDIT MANAGEMENT ====================

# Pydantic models for credit endpoints
class CreditTopupRequest(BaseModel):
    amount: float
    note: str = ""

class CreditEstimateResponse(BaseModel):
    operation: str
    estimated_credits: int
    note: str = ""

# Fixed credit cost table (BUMN-friendly: predictable numbers for PO/budgeting)
# Editable via Super Admin in a future release — for now, derived from DEFAULT_CREDIT_RATES
CREDIT_COST_TABLE = {
    "evidence_analysis": 10,    # credits per session
    "roleplay_session": 25,     # credits per session
    "competency_scoring": 5,    # credits per session
}

@api_router.post("/admin/users/{user_id}/credits/topup")
async def topup_user_credits(
    user_id: str,
    body: CreditTopupRequest,
    admin: dict = Depends(get_current_admin)
):
    """Add credits to a user account and log the transaction."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    current_credits = user.get("credits", 0.0)
    new_balance = current_credits + body.amount

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"credits": new_balance}}
    )

    # Update company credits_balance (display only)
    company_id = user.get("company_id")
    if company_id:
        company = await db.companies.find_one({"id": company_id}, {"_id": 0})
        if company:
            new_company_balance = company.get("credits_balance", 0.0) + body.amount
            await db.companies.update_one(
                {"id": company_id},
                {"$set": {"credits_balance": new_company_balance}}
            )

    # Log to credit_usage_logs
    usage_log = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "operation_type": "admin_topup",
        "tokens_used": 0,
        "openrouter_cost": 0.0,
        "credits_charged": -body.amount,  # Negative = addition
        "model_used": "n/a",
        "note": body.note,
        "created_by": admin.get("username", "admin"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.credit_usage_logs.insert_one(usage_log)

    return {
        "message": f"Successfully added {body.amount} credits to user {user_id}",
        "previous_balance": current_credits,
        "added": body.amount,
        "new_balance": new_balance,
        "note": body.note
    }

@api_router.get("/admin/users/{user_id}/credits/history")
async def get_user_credit_history(
    user_id: str,
    limit: int = 50,
    admin: dict = Depends(get_current_admin)
):
    """Return credit usage history for a specific user."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cursor = db.credit_usage_logs.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)

    logs = [log async for log in cursor]
    current_credits = user.get("credits", 0.0)

    return {
        "user_id": user_id,
        "current_balance": current_credits,
        "history": logs,
        "total_entries": len(logs)
    }

@api_router.get("/admin/companies/{company_id}/credits/usage")
async def get_company_credit_usage(
    company_id: str,
    admin: dict = Depends(get_current_admin)
):
    """Aggregate credit usage for all users in a company."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get all user_ids for this company
    users_cursor = db.users.find({"company_id": company_id}, {"id": 1, "email": 1, "name": 1, "credits": 1, "_id": 0})
    users = [u async for u in users_cursor]
    user_ids = [u["id"] for u in users]

    if not user_ids:
        return {"company_id": company_id, "total_credits_consumed": 0, "users": [], "history": []}

    # Aggregate usage logs (exclude topups from consumption total)
    pipeline = [
        {"$match": {"user_id": {"$in": user_ids}, "operation_type": {"$ne": "admin_topup"}}},
        {"$group": {
            "_id": "$user_id",
            "total_credits": {"$sum": "$credits_charged"},
            "total_tokens": {"$sum": "$tokens_used"},
            "operations_count": {"$sum": 1}
        }}
    ]
    usage_by_user = {}
    async for doc in db.credit_usage_logs.aggregate(pipeline):
        usage_by_user[doc["_id"]] = {
            "credits_consumed": round(doc["total_credits"], 4),
            "tokens_used": doc["total_tokens"],
            "operations_count": doc["operations_count"]
        }

    # Merge user info with usage
    user_summary = []
    total_consumed = 0.0
    for u in users:
        uid = u["id"]
        usage = usage_by_user.get(uid, {"credits_consumed": 0, "tokens_used": 0, "operations_count": 0})
        total_consumed += usage["credits_consumed"]
        user_summary.append({
            "user_id": uid,
            "email": u.get("email"),
            "name": u.get("name"),
            "current_balance": u.get("credits", 0.0),
            **usage
        })

    return {
        "company_id": company_id,
        "company_name": company.get("name"),
        "total_credits_consumed": round(total_consumed, 4),
        "user_count": len(users),
        "users": user_summary
    }

# ==================== CREDIT ESTIMATE (User-facing) ====================

@api_router.get("/credits/estimate", response_model=CreditEstimateResponse)
async def estimate_credit_cost(
    operation: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Return estimated credit cost for a given operation.
    Used by frontend to show confirmation dialog before triggering assessment.
    Does NOT deduct credits.
    """
    if operation not in CREDIT_COST_TABLE:
        valid_ops = list(CREDIT_COST_TABLE.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown operation '{operation}'. Valid operations: {valid_ops}"
        )

    estimated = CREDIT_COST_TABLE[operation]
    return CreditEstimateResponse(
        operation=operation,
        estimated_credits=estimated,
        note="Estimated cost only. Actual cost may vary slightly based on session length."
    )

# ==================== SUPER ADMIN: COMPANY MANAGEMENT ====================


@api_router.post("/admin/companies", response_model=AdminCompanyResponse)
async def admin_create_company(
    data: AdminCompanyCreate,
    admin: dict = Depends(get_current_admin)
):
    """Create a new company (Super Admin only)."""
    company_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    company = {
        "id": company_id,
        "name": data.name,
        "description": data.description or "",
        "industry": data.industry or "",
        "website": data.website or "",
        "values": [],
        "subscription_tier": data.subscription_tier,
        "credits_balance": data.credits_balance,
        "expiry_date": data.expiry_date,
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }
    
    await db.companies.insert_one(company)
    return AdminCompanyResponse(**company)

@api_router.get("/admin/companies")
async def admin_list_companies(
    admin: dict = Depends(get_current_admin)
):
    """List all companies (Super Admin only)."""
    cursor = db.companies.find({}, {"_id": 0})
    companies = await cursor.to_list(1000)
    return {"companies": companies, "total": len(companies)}

@api_router.get("/admin/companies/{company_id}", response_model=AdminCompanyResponse)
async def admin_get_company(
    company_id: str,
    admin: dict = Depends(get_current_admin)
):
    """Get company detail (Super Admin only)."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return AdminCompanyResponse(**company)

@api_router.put("/admin/companies/{company_id}", response_model=AdminCompanyResponse)
async def admin_update_company(
    company_id: str,
    data: AdminCompanyUpdate,
    admin: dict = Depends(get_current_admin)
):
    """Update company details (Super Admin only)."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.companies.update_one({"id": company_id}, {"$set": update_data})
    
    updated = await db.companies.find_one({"id": company_id}, {"_id": 0})
    return AdminCompanyResponse(**updated)

@api_router.delete("/admin/companies/{company_id}")
async def admin_deactivate_company(
    company_id: str,
    admin: dict = Depends(get_current_admin)
):
    """Soft-delete: deactivate a company (Super Admin only)."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    await db.companies.update_one(
        {"id": company_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": f"Company {company_id} deactivated"}

# Admin Settings Models
class GlobalSettingsUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    model_name: Optional[str] = None
    default_credits_new_user: Optional[float] = None

class CreditRatesUpdate(BaseModel):
    rates: Dict[str, float]

@api_router.get("/admin/settings")
async def get_admin_settings(admin: dict = Depends(get_current_admin)):
    """Get global AI settings managed by admin."""
    settings = await db.admin_settings.find_one({"type": "global"}, {"_id": 0})
    if not settings:
        # Return defaults
        settings = {
            "type": "global",
            "openrouter_api_key": "",
            "model_name": "openai/gpt-4o-mini",
            "default_credits_new_user": 100.0,
            "openrouter_api_key_masked": ""
        }
    else:
        # Mask API key
        api_key = settings.get("openrouter_api_key", "")
        if api_key:
            settings["openrouter_api_key_masked"] = f"{api_key[:10]}...{api_key[-4:]}"
        else:
            settings["openrouter_api_key_masked"] = ""
    
    return settings

@api_router.put("/admin/settings")
async def update_admin_settings(
    update_data: GlobalSettingsUpdate,
    admin: dict = Depends(get_current_admin)
):
    """Update global AI settings."""
    settings = await db.admin_settings.find_one({"type": "global"}, {"_id": 0})
    
    if not settings:
        # Create new settings
        settings = {
            "type": "global",
            "openrouter_api_key": "",
            "model_name": "openai/gpt-4o-mini",
            "default_credits_new_user": 100.0
        }
    
    # Update fields
    if update_data.openrouter_api_key is not None:
        settings["openrouter_api_key"] = update_data.openrouter_api_key
    if update_data.model_name is not None:
        settings["model_name"] = update_data.model_name
    if update_data.default_credits_new_user is not None:
        settings["default_credits_new_user"] = update_data.default_credits_new_user
    
    # Upsert settings
    await db.admin_settings.update_one(
        {"type": "global"},
        {"$set": settings},
        upsert=True
    )
    
    return {"message": "Settings updated successfully", "settings": settings}

@api_router.get("/admin/credit-rates")
async def get_credit_rates(admin: dict = Depends(get_current_admin)):
    """Get credit rate multipliers for different operations."""
    rates = await db.admin_settings.find_one({"type": "credit_rates"}, {"_id": 0})
    if not rates:
        return {"rates": DEFAULT_CREDIT_RATES}
    return rates

@api_router.put("/admin/credit-rates")
async def update_credit_rates(
    update_data: CreditRatesUpdate,
    admin: dict = Depends(get_current_admin)
):
    """Update credit rate multipliers."""
    await db.admin_settings.update_one(
        {"type": "credit_rates"},
        {"$set": {"type": "credit_rates", "rates": update_data.rates}},
        upsert=True
    )
    return {"message": "Credit rates updated successfully", "rates": update_data.rates}

@api_router.get("/admin/usage-logs")
async def get_usage_logs(
    admin: dict = Depends(get_current_admin),
    limit: int = 100,
    user_id: Optional[str] = None
):
    """Get credit usage logs."""
    query = {}
    if user_id:
        query["user_id"] = user_id
    
    logs_cursor = db.credit_usage_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    logs = []
    async for log in logs_cursor:
        # Get user info
        user = await db.users.find_one({"id": log["user_id"]}, {"_id": 0, "email": 1, "name": 1})
        log["user_email"] = user.get("email", "Unknown") if user else "Unknown"
        log["user_name"] = user.get("name", "Unknown") if user else "Unknown"
        logs.append(log)
    
    return {"logs": logs}

# Helper function to get global settings
async def get_global_ai_settings() -> dict:
    """Get global AI settings from admin settings."""
    settings = await db.admin_settings.find_one({"type": "global"}, {"_id": 0})
    if not settings:
        logger.warning("No global AI settings found, returning defaults")
        return {
            "openrouter_api_key": "",
            "model_name": "openai/gpt-4o-mini"
        }
    
    # Log that we're using global settings (without exposing key)
    api_key = settings.get("openrouter_api_key", "")
    has_key = bool(api_key)
    key_length = len(api_key) if api_key else 0
    logger.info(f"Global AI settings retrieved - has API key: {has_key}, key_length: {key_length}, model: {settings.get('model_name')}")
    
    return settings

# ==================== COMPANY ROUTES ====================

@api_router.post("/company", response_model=CompanyResponse)
async def create_company(data: CompanyCreate, current_user: dict = Depends(get_current_user)):
    """DEPRECATED: Company creation is now admin-managed only. Use /api/admin/companies."""
    raise HTTPException(
        status_code=410,
        detail="Self-service company creation has been disabled. Contact your platform administrator."
    )

@api_router.get("/company", response_model=Optional[CompanyResponse])
async def get_company(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return None
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    if not company:
        return None
    
    return CompanyResponse(**company)

@api_router.put("/company", response_model=CompanyResponse)
async def update_company(data: CompanyUpdate, current_user: dict = Depends(get_current_user)):
    """DEPRECATED: Company updates are now admin-managed only. Use /api/admin/companies/{id}."""
    raise HTTPException(
        status_code=410,
        detail="Self-service company updates have been disabled. Contact your platform administrator."
    )

@api_router.post("/company/generate-values")
async def generate_company_values(narrative: str = Form(...), current_user: dict = Depends(get_current_user)):
    # Check credits first
    credit_check = await check_user_credits(current_user["id"])
    if not credit_check.has_credits:
        raise HTTPException(status_code=402, detail=credit_check.message)
    
    # Get global settings and user language preference
    global_settings = await get_global_ai_settings()
    user_settings = await get_ai_settings(current_user["id"])
    
    lang_instruction = "Respond in English." if user_settings.language == "en" else "Respond in Indonesian (Bahasa Indonesia)."
    
    system_prompt = f"""Based on the company culture narrative provided by the user, generate 5-7 structured company values.

{lang_instruction}

Return a JSON array with this structure:
[
  {{"name": "Value Name", "description": "Brief description of this value", "weight": 15}}
]

Requirements:
- Each value should have a clear, concise name
- Description should be 1-2 sentences
- Weights should total exactly 100
- Values should be distinct and meaningful for candidate evaluation"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Narrative:\n{narrative}"}
    ]
    
    # Call with usage tracking
    result = await call_openrouter_with_usage(
        global_settings["openrouter_api_key"], 
        global_settings["model_name"], 
        messages
    )
    
    # Deduct credits
    await deduct_credits(
        current_user["id"],
        "company_values_generation",
        result["tokens_used"],
        result["cost"],
        global_settings["model_name"]
    )
    
    try:
        # Extract JSON from response
        response = result["content"]
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        values_json = response[json_start:json_end]
        values = json.loads(values_json)
        
        # Add IDs
        for v in values:
            v["id"] = str(uuid.uuid4())
        
        return {"values": values}
    except Exception as e:
        logger.error(f"Failed to parse AI response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse AI-generated values")

# ==================== JOB ROUTES ====================

@api_router.post("/jobs", response_model=JobResponse)
async def create_job(data: JobCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    job = {
        "id": job_id,
        "company_id": current_user["company_id"],
        "title": data.title,
        "description": data.description,
        "requirements": data.requirements,
        "location": data.location or "",
        "employment_type": data.employment_type or "full-time",
        "salary_range": data.salary_range or "",
        "playbook": data.playbook.model_dump() if data.playbook else None,
        "status": "open",
        "created_at": now,
        "updated_at": now
    }
    
    await db.jobs.insert_one(job)
    return JobResponse(**job)

@api_router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return []
    
    jobs = await db.jobs.find({"company_id": current_user["company_id"]}, {"_id": 0}).to_list(1000)
    return [JobResponse(**job) for job in jobs]

@api_router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job)

@api_router.put("/jobs/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, data: JobUpdate, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "playbook" in update_data and update_data["playbook"]:
        update_data["playbook"] = update_data["playbook"].model_dump() if hasattr(update_data["playbook"], 'model_dump') else update_data["playbook"]
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.jobs.update_one({"id": job_id}, {"$set": update_data})
    
    updated_job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    return JobResponse(**updated_job)

@api_router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.jobs.delete_one({"id": job_id, "company_id": current_user.get("company_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted"}

@api_router.post("/jobs/generate-description")
async def generate_job_description(title: str = Form(...), context: str = Form(""), mode: str = Form("generate"), current_user: dict = Depends(get_current_user)):
    # Check credits first
    credit_check = await check_user_credits(current_user["id"])
    if not credit_check.has_credits:
        raise HTTPException(status_code=402, detail=credit_check.message)
    
    # Get global settings and user language preference
    global_settings = await get_global_ai_settings()
    user_settings = await get_ai_settings(current_user["id"])
    
    lang_instruction = "Write in English." if user_settings.language == "en" else "Write in Indonesian (Bahasa Indonesia)."
    
    mode_instruction = ""
    if mode == "improve":
        mode_instruction = "- REVISION MODE: Improve the existing context to be more professional, structured, and impactful."
    elif mode == "concise":
        mode_instruction = "- REVISION MODE: Make the existing context significantly more concise and brief, removing fluff."
    elif mode == "detailed":
        mode_instruction = "- REVISION MODE: Expand the existing context to be much more detailed, covering all possible sub-responsibilities and technical depths."

    if context.strip():
        # Generate based on narrative
        system_prompt = f"""Based on the job description narrative provided by the user, generate a professional job description and requirements.

Job Title: {title}

{lang_instruction}

GUIDELINES:
{mode_instruction}
- Do NOT use emojis.
- Keep professional HR tone. No unnecessary repetition.
- Use concise, clear sentences.
- Free Narrative Rule: Extract competencies from narrative, infer job title if not explicitly stated, expand into professional HR-ready job description, keep tone formal and professional.

Return a JSON object with this exact structure (do NOT use nested objects, just return formatted strings with explicit newlines `\\n`):
{{
  "description": "The full professional job description text, including About the Role and Responsibilities, formatted with newlines and bullet points.",
  "requirements": "The full professional job requirements text, including Experience, Skills, and Qualifications, formatted with newlines and bullet points."
}}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Narrative/Context:\n{context}"}
        ]
    else:
        # Generate based on title only
        system_prompt = f"""Generate a professional job description and requirements for the position: {title}

{lang_instruction}

GUIDELINES:
{mode_instruction}
- Do NOT use emojis.
- Keep professional HR tone. No unnecessary repetition.
- Use concise, clear sentences.
- Job Title Only Rule: Infer industry-standard responsibilities, infer realistic experience requirements, generate professional-level content.

Return a JSON object with this exact structure (do NOT use nested objects, just return formatted strings with explicit newlines `\\n`):
{{
  "description": "The full professional job description text, including About the Role and Responsibilities, formatted with newlines and bullet points.",
  "requirements": "The full professional job requirements text, including Experience, Skills, and Qualifications, formatted with newlines and bullet points."
}}"""

        messages = [{"role": "system", "content": system_prompt}]
    
    # Call with usage tracking
    result = await call_openrouter_with_usage(
        global_settings["openrouter_api_key"], 
        global_settings["model_name"], 
        messages
    )
    
    # Deduct credits
    await deduct_credits(
        current_user["id"],
        "job_description_generation",
        result["tokens_used"],
        result["cost"],
        global_settings["model_name"]
    )
    
    response = result["content"]
    
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            try:
                data = json.loads(json_str)
                description = data.get("description", "")
                requirements = data.get("requirements", "")
                
                if isinstance(description, dict):
                    # Fallback if AI somehow still gave dict
                    # Just convert it to string
                    description = "\\n\\n".join([f"{k.replace('_', ' ').title()}:\\n{v}" for k, v in description.items()])
                if isinstance(requirements, dict):
                    requirements = "\\n\\n".join([f"{k.replace('_', ' ').title()}:\\n{v}" for k, v in requirements.items()])
                
                return {
                    "description": description,
                    "requirements": requirements
                }
            except json.JSONDecodeError:
                pass
                
        # Default fallback if JSON parsing fails entirely
        return {
            "description": response,
            "requirements": ""
        }
    except Exception as e:
        logger.error(f"Error parsing job description response: {e}")
        return {
            "description": "Failed to generate description.",
            "requirements": "Failed to generate requirements."
        }

@api_router.post("/jobs/{job_id}/generate-playbook")
async def generate_job_playbook(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check credits first
    credit_check = await check_user_credits(current_user["id"])
    if not credit_check.has_credits:
        raise HTTPException(status_code=402, detail=credit_check.message)
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    
    # Get global settings and user language preference
    global_settings = await get_global_ai_settings()
    logger.info(f"Analysis: Retrieved global settings - has_key: {bool(global_settings.get('openrouter_api_key'))}, model: {global_settings.get('model_name')}")
    user_settings = await get_ai_settings(current_user["id"])
    
    lang_instruction = "Write in English." if user_settings.language == "en" else "Write in Indonesian (Bahasa Indonesia)."
    
    company_values_text = ""
    if company and company.get("values"):
        company_values_text = "Company Values:\n" + "\n".join([f"- {v['name']}: {v['description']}" for v in company["values"]])
    
    system_prompt = f"""Generate a comprehensive job evaluation playbook/rubric for screening candidates based on the job details provided by the user.

{lang_instruction}

Create evaluation criteria in 3 categories. Each category must have exactly 5 items with weights totaling 100%.

Return a JSON object:
{{
  "character": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ],
  "requirement": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ],
  "skill": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ]
}}

Categories:
- Character: Personality traits, cultural fit, soft skills, work ethic
- Requirement: Education, experience, certifications, mandatory qualifications  
- Skill: Technical abilities, tools, domain expertise

Make criteria specific to this role and measurable from CV/resume review."""

    user_content = f"""Job Title: {job.get('title', 'Unknown')}
Job Description: {job.get('description', '')}
Requirements: {job.get('requirements', '')}
{company_values_text}"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    # Call with usage tracking
    result = await call_openrouter_with_usage(
        global_settings["openrouter_api_key"], 
        global_settings["model_name"], 
        messages,
        temperature=0.5
    )
    
    # Deduct credits
    await deduct_credits(
        current_user["id"],
        "playbook_generation",
        result["tokens_used"],
        result["cost"],
        global_settings["model_name"]
    )
    
    response = result["content"]
    
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        playbook_data = json.loads(response[json_start:json_end])
        
        # Add IDs to each item
        for category in ["character", "requirement", "skill"]:
            if category in playbook_data:
                for item in playbook_data[category]:
                    item["id"] = str(uuid.uuid4())
        
        # Update job with playbook
        await db.jobs.update_one(
            {"id": job_id},
            {"$set": {"playbook": playbook_data, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {"playbook": playbook_data}
    except Exception as e:
        logger.error(f"Failed to parse playbook: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate playbook")

# ==================== CANDIDATE ROUTES ====================

@api_router.post("/candidates", response_model=CandidateResponse)
async def create_candidate(data: CandidateCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    candidate_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    candidate = {
        "id": candidate_id,
        "company_id": current_user["company_id"],
        "name": data.name,
        "email": data.email,
        "phone": data.phone or "",
        "evidence": [],
        "created_at": now,
        "updated_at": now
    }
    
    await db.candidates.insert_one(candidate)
    return CandidateResponse(**candidate)

@api_router.get("/candidates", response_model=List[CandidateResponse])
async def list_candidates(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return []
    
    candidates = await db.candidates.find({"company_id": current_user["company_id"]}, {"_id": 0}).to_list(1000)
    return [CandidateResponse(**c) for c in candidates]

# Candidate search/pagination endpoint - MUST be before {candidate_id} route
@api_router.get("/candidates/search")
async def search_candidates(
    q: str = Query("", description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Search and paginate candidates"""
    if not current_user.get("company_id"):
        return {"candidates": [], "total": 0, "page": page, "pages": 0}
    
    company_id = current_user["company_id"]
    
    # Build search query
    query = {"company_id": company_id}
    if q.strip():
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.candidates.count_documents(query)
    pages = (total + limit - 1) // limit
    
    # Get paginated results
    skip = (page - 1) * limit
    candidates = await db.candidates.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    return {
        "candidates": candidates,
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit
    }

# Merge logs endpoint - MUST be before {candidate_id} route
@api_router.get("/candidates/merge-logs")
async def get_merge_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Get merge audit logs for the company.
    """
    if not current_user.get("company_id"):
        return []
    
    logs = await db.merge_logs.find(
        {"company_id": current_user["company_id"]},
        {"_id": 0}
    ).sort("merged_at", -1).limit(limit).to_list(limit)
    
    return logs

@api_router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse(**candidate)

@api_router.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.candidates.delete_one({"id": candidate_id, "company_id": current_user.get("company_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"message": "Candidate deleted"}

@api_router.post("/candidates/upload-cv")
@limiter.limit("5/minute")
async def upload_cv(
    request: Request,
    file: UploadFile = File(...),
    candidate_id: Optional[str] = Form(None),
    force_create: bool = Form(False),
    merge_target_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload CV with duplicate detection and evidence splitting.
    
    Flow for NEW candidate (no candidate_id):
    1. Parse PDF and extract contact info
    2. Check for duplicates by email/phone/name
    3. If duplicates found and force_create=False: return duplicate warning
    4. If force_create=True or merge_target_id provided: proceed
    5. Split PDF into evidence types (CV, certificates, etc.)
    6. Create candidate or merge into existing
    
    Flow for EXISTING candidate (candidate_id provided):
    1. Parse PDF
    2. Split into evidence types
    3. Append all evidence to existing candidate
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    content = await file.read()
    parsed_text = parse_pdf(content)
    
    if not parsed_text:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")
    
    now = datetime.now(timezone.utc).isoformat()
    company_id = current_user["company_id"]
    
    # Get AI settings for contact extraction and evidence classification
    settings = await get_ai_settings(current_user["id"])
    admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    
    # Split PDF into evidence types
    evidence_list = await split_pdf_into_evidence(
        content, 
        file.filename,
        settings.openrouter_api_key if settings else None,
        settings.model_name if settings else None
    )
    
    # Add timestamps and source to evidence
    for ev in evidence_list:
        ev["uploaded_at"] = now
        ev["source"] = "pdf_upload"
    
    # If adding to existing candidate, just append evidence
    if candidate_id:
        candidate = await db.candidates.find_one(
            {"id": candidate_id, "company_id": company_id}
        )
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Convert evidence_list to proper format (remove 'pages' field for storage)
        evidence_to_add = []
        for ev in evidence_list:
            evidence_to_add.append({
                "type": ev["type"],
                "file_name": ev["file_name"],
                "content": ev["content"],
                "uploaded_at": ev["uploaded_at"],
                "source": ev.get("source", "pdf_upload"),
                "pages": ev.get("pages", [])
            })
        
        await db.candidates.update_one(
            {"id": candidate_id, "company_id": company_id},
            {
                "$push": {"evidence": {"$each": evidence_to_add}},
                "$set": {"updated_at": now}
            }
        )
        
        updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
        return {
            "status": "updated",
            "candidate": CandidateResponse(**updated),
            "evidence_added": len(evidence_to_add),
            "evidence_types": [e["type"] for e in evidence_to_add]
        }
    
    # For new candidate: Extract contact info first
    name = ""
    email = ""
    phone = ""
    
    # Use AI to extract contact info if API key is available
    if settings.openrouter_api_key:
        try:
            cv_parse_prompt = admin_settings.get("cv_parse_prompt") if admin_settings else None
            
            if cv_parse_prompt:
                system_prompt = cv_parse_prompt.replace("{cv_text}", "The candidate's CV text is provided by the user.")
            else:
                system_prompt = f"""Extract contact information from the CV/resume text provided by the user.

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CV TEXT:\n{parsed_text[:3000]}"}
            ]
            response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.1)
            
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                contact_info = json.loads(response[json_start:json_end])
                name = contact_info.get("name", "").strip()
                email = contact_info.get("email", "").strip()
                phone = contact_info.get("phone", "").strip()
        except Exception as e:
            logger.warning(f"AI CV parsing failed, using fallback: {e}")
    
    # Fallback to basic parsing if AI didn't work
    if not name:
        lines = parsed_text.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 2 and len(line) < 50:
                if not any(c.isdigit() for c in line) and '@' not in line:
                    name = line
                    break
        if not name:
            name = "Unknown Candidate"
    
    if not email:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, parsed_text)
        email = emails[0] if emails else ""
    
    if not phone:
        phone_patterns = [
            r'\+?[\d\s\-\(\)]{10,}',
            r'\d{3}[\s\-]?\d{3}[\s\-]?\d{4}',
            r'\(\d{3}\)\s?\d{3}[\s\-]?\d{4}'
        ]
        for pattern in phone_patterns:
            phones = re.findall(pattern, parsed_text[:1000])
            if phones:
                phone = phones[0].strip()
                break
    
    # Check for duplicates BEFORE creating (unless force_create or merge_target specified)
    if not force_create and not merge_target_id:
        # Run duplicate detection
        duplicates = await _find_duplicates(company_id, email, phone, name)
        
        if duplicates:
            return {
                "status": "duplicate_warning",
                "candidate": None,
                "duplicates": duplicates,
                "extracted_info": {
                    "name": name,
                    "email": email,
                    "phone": phone
                },
                "evidence_preview": [{"type": e["type"], "pages": e.get("pages", [])} for e in evidence_list],
                "message": f"Found {len(duplicates)} potential duplicate(s). Choose to merge, create new, or cancel."
            }
    
    # Handle merge request
    if merge_target_id:
        target = await db.candidates.find_one(
            {"id": merge_target_id, "company_id": company_id}
        )
        if not target:
            raise HTTPException(status_code=404, detail="Merge target candidate not found")
        
        # Append evidence to target
        evidence_to_add = []
        for ev in evidence_list:
            evidence_to_add.append({
                "type": ev["type"],
                "file_name": ev["file_name"],
                "content": ev["content"],
                "uploaded_at": now,
                "source": "merge_upload",
                "pages": ev.get("pages", [])
            })
        
        await db.candidates.update_one(
            {"id": merge_target_id},
            {
                "$push": {"evidence": {"$each": evidence_to_add}},
                "$set": {"updated_at": now}
            }
        )
        
        # Log the merge
        merge_log = {
            "id": str(uuid.uuid4()),
            "action": "evidence_merge",
            "target_id": merge_target_id,
            "target_name": target.get("name", ""),
            "file_name": file.filename,
            "evidence_transferred": len(evidence_to_add),
            "merged_by": current_user["id"],
            "company_id": company_id,
            "merged_at": now
        }
        await db.merge_logs.insert_one(merge_log)
        
        updated = await db.candidates.find_one({"id": merge_target_id}, {"_id": 0})
        return {
            "status": "merged",
            "candidate": CandidateResponse(**updated),
            "evidence_added": len(evidence_to_add),
            "evidence_types": [e["type"] for e in evidence_to_add],
            "message": f"Merged {len(evidence_to_add)} evidence file(s) into existing candidate"
        }
    
    # Create new candidate with split evidence
    new_candidate_id = str(uuid.uuid4())
    
    evidence_to_add = []
    for ev in evidence_list:
        evidence_to_add.append({
            "type": ev["type"],
            "file_name": ev["file_name"],
            "content": ev["content"],
            "uploaded_at": now,
            "source": "pdf_upload",
            "pages": ev.get("pages", [])
        })
    
    candidate = {
        "id": new_candidate_id,
        "company_id": company_id,
        "name": name,
        "email": email,
        "phone": phone,
        "evidence": evidence_to_add,
        "tags": [],
        "deleted_tags": [],
        "created_at": now,
        "updated_at": now
    }
    
    await db.candidates.insert_one(candidate)
    
    # Auto-extract tags if API key is configured
    extracted_tags = []
    if settings.openrouter_api_key:
        try:
            tag_result = await extract_tags_from_evidence(
                evidence_to_add,
                [],  # No deleted tags for new candidate
                settings.openrouter_api_key,
                settings.model_name
            )
            if tag_result.get("tags"):
                extracted_tags = [t.dict() for t in tag_result["tags"]]
                await db.candidates.update_one(
                    {"id": new_candidate_id},
                    {"$set": {"tags": extracted_tags}}
                )
                candidate["tags"] = extracted_tags
        except Exception as e:
            logger.warning(f"Auto tag extraction failed for new candidate: {e}")
    
    return {
        "status": "created",
        "candidate": CandidateResponse(**{**candidate, "tags": candidate.get("tags", []), "deleted_tags": []}),
        "evidence_added": len(evidence_to_add),
        "evidence_types": [e["type"] for e in evidence_to_add],
        "tags_extracted": len(extracted_tags)
    }

# Helper function for duplicate detection
async def _find_duplicates(company_id: str, email: str, phone: str, name: str) -> List[Dict]:
    """Find duplicate candidates based on email, phone, or name+email match."""
    
    duplicates = []
    seen_ids = set()
    
    # Normalize values for comparison
    norm_email = email.lower().strip() if email else ""
    norm_phone = re.sub(r'\D', '', phone) if phone else ""
    norm_name = ' '.join(name.lower().split()) if name else ""
    
    # Get all candidates for this company
    candidates = await db.candidates.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1}
    ).to_list(10000)
    
    for cand in candidates:
        if cand["id"] in seen_ids:
            continue
            
        match_reasons = []
        cand_email = (cand.get("email") or "").lower().strip()
        cand_phone = re.sub(r'\D', '', cand.get("phone") or "")
        cand_name = ' '.join((cand.get("name") or "").lower().split())
        
        # Rule 1: Email match (case-insensitive)
        if norm_email and cand_email and norm_email == cand_email:
            match_reasons.append("email_match")
        
        # Rule 2: Phone match (normalized - check last 7+ digits)
        if norm_phone and cand_phone and len(norm_phone) >= 7 and len(cand_phone) >= 7:
            if norm_phone[-7:] == cand_phone[-7:] or norm_phone == cand_phone:
                match_reasons.append("phone_match")
        
        # Rule 3: Email + Name match
        if norm_email and norm_name and cand_email and cand_name:
            if norm_email == cand_email and norm_name == cand_name:
                if "email_match" not in match_reasons:
                    match_reasons.append("email_match")
                match_reasons.append("name_match")
        
        if match_reasons:
            seen_ids.add(cand["id"])
            
            # Determine confidence
            if "email_match" in match_reasons:
                confidence = "high"
            elif "phone_match" in match_reasons:
                confidence = "medium"
            else:
                confidence = "medium"
            
            duplicates.append({
                "candidate_id": cand["id"],
                "candidate_name": cand.get("name", ""),
                "candidate_email": cand.get("email", ""),
                "candidate_phone": cand.get("phone", ""),
                "match_reasons": match_reasons,
                "confidence": confidence
            })
    
    return duplicates

@api_router.post("/candidates/{candidate_id}/upload-evidence")
async def upload_evidence(
    candidate_id: str,
    file: UploadFile = File(...),
    evidence_type: str = Form("auto"),  # "auto" for automatic detection, or explicit type
    current_user: dict = Depends(get_current_user)
):
    """
    Upload evidence to existing candidate with automatic splitting for PDFs.
    
    If evidence_type="auto" and file is PDF:
    - Split PDF into multiple evidence entries based on content
    - Each section is classified (cv, certificate, diploma, etc.)
    
    If evidence_type is explicit (e.g., "psychotest"):
    - Use that type for all pages (no splitting by type)
    """
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    content = await file.read()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get AI settings for evidence classification
    settings = await get_ai_settings(current_user["id"])
    
    if file.filename.lower().endswith('.pdf'):
        if evidence_type == "auto":
            # Split PDF into evidence types
            evidence_list = await split_pdf_into_evidence(
                content, 
                file.filename,
                settings.openrouter_api_key if settings else None,
                settings.model_name if settings else None
            )
            
            # Add timestamps
            evidence_to_add = []
            for ev in evidence_list:
                evidence_to_add.append({
                    "type": ev["type"],
                    "file_name": ev["file_name"],
                    "content": ev["content"],
                    "uploaded_at": now,
                    "source": "evidence_upload",
                    "pages": ev.get("pages", [])
                })
        else:
            # Use explicit type for entire PDF
            parsed_text = parse_pdf(content)
            evidence_to_add = [{
                "type": evidence_type,
                "file_name": file.filename,
                "content": parsed_text,
                "uploaded_at": now,
                "source": "evidence_upload"
            }]
    else:
        # Non-PDF file
        parsed_text = content.decode('utf-8', errors='ignore')
        evidence_to_add = [{
            "type": evidence_type if evidence_type != "auto" else "other",
            "file_name": file.filename,
            "content": parsed_text,
            "uploaded_at": now,
            "source": "evidence_upload"
        }]
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$push": {"evidence": {"$each": evidence_to_add}},
            "$set": {"updated_at": now}
        }
    )
    
    updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    return {
        "status": "updated",
        "candidate": CandidateResponse(**updated),
        "evidence_added": len(evidence_to_add),
        "evidence_types": [e["type"] for e in evidence_to_add]
    }

@api_router.delete("/candidates/{candidate_id}/evidence/{evidence_index}")
async def delete_evidence(
    candidate_id: str,
    evidence_index: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific evidence item from a candidate by its index.
    """
    candidate = await db.candidates.find_one(
        {"id": candidate_id, "company_id": current_user.get("company_id")},
        {"_id": 0}
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    evidence_list = candidate.get("evidence", [])
    
    if evidence_index < 0 or evidence_index >= len(evidence_list):
        raise HTTPException(status_code=400, detail="Invalid evidence index")
    
    # Remove the evidence at the specified index
    deleted_evidence = evidence_list[evidence_index]
    evidence_list.pop(evidence_index)
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "evidence": evidence_list,
                "updated_at": now
            }
        }
    )
    
    updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    return {
        "status": "deleted",
        "deleted_evidence": {
            "type": deleted_evidence.get("type"),
            "file_name": deleted_evidence.get("file_name")
        },
        "candidate": CandidateResponse(**updated),
        "remaining_evidence": len(evidence_list)
    }

class ReplaceCandidate(BaseModel):
    old_candidate_id: str
    new_name: str
    new_email: str
    new_phone: str = ""
    new_evidence: List[Dict] = []

@api_router.post("/candidates/replace")
async def replace_candidate(
    data: ReplaceCandidate,
    current_user: dict = Depends(get_current_user)
):
    """
    Replace an existing candidate with new data.
    Deletes the old candidate and creates a new one.
    Used for bulk duplicate handling when user chooses 'Replace'.
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    company_id = current_user["company_id"]
    
    # Verify old candidate exists
    old_candidate = await db.candidates.find_one(
        {"id": data.old_candidate_id, "company_id": company_id},
        {"_id": 0}
    )
    if not old_candidate:
        raise HTTPException(status_code=404, detail="Candidate to replace not found")
    
    # Delete old candidate
    await db.candidates.delete_one({"id": data.old_candidate_id})
    
    # Create new candidate
    now = datetime.now(timezone.utc).isoformat()
    new_candidate_id = str(uuid.uuid4())
    
    new_candidate = {
        "id": new_candidate_id,
        "company_id": company_id,
        "name": data.new_name,
        "email": data.new_email,
        "phone": data.new_phone,
        "evidence": data.new_evidence,
        "created_at": now,
        "updated_at": now,
        "replaced_from": data.old_candidate_id
    }
    
    await db.candidates.insert_one(new_candidate)
    
    # Log the replacement
    replace_log = {
        "id": str(uuid.uuid4()),
        "action": "candidate_replace",
        "old_candidate_id": data.old_candidate_id,
        "old_candidate_name": old_candidate.get("name", ""),
        "new_candidate_id": new_candidate_id,
        "new_candidate_name": data.new_name,
        "replaced_by": current_user["id"],
        "company_id": company_id,
        "replaced_at": now
    }
    await db.merge_logs.insert_one(replace_log)
    
    return {
        "status": "replaced",
        "old_candidate_id": data.old_candidate_id,
        "new_candidate": CandidateResponse(**new_candidate)
    }

# ==================== TALENT TAGGING ROUTES ====================

async def extract_tags_from_evidence(
    evidence_list: List[Dict],
    deleted_tags: List[str],
    api_key: str,
    model: str,
    admin_settings: Optional[Dict] = None,
    user_id: Optional[str] = None
) -> Dict:
    """
    Extract structured tags from candidate evidence using AI.
    Respects blacklisted (deleted) tags and layer constraints.
    """
    if not api_key:
        return {"tags": [], "summary": "No API key configured", "evidence_used": []}
    
    # Combine all evidence content
    evidence_texts = []
    evidence_names = []
    for ev in evidence_list:
        if ev.get("content"):
            evidence_texts.append(f"[{ev.get('type', 'unknown').upper()}] {ev.get('file_name', 'unknown')}:\n{ev['content'][:5000]}")
            evidence_names.append(ev.get('file_name', 'unknown'))
    
    if not evidence_texts:
        return {"tags": [], "summary": "No evidence content to analyze", "evidence_used": []}
    
    combined_evidence = "\n\n---\n\n".join(evidence_texts)
    
    # Build the prompt
    prompt = f"""Analyze the following candidate evidence and extract structured tags according to the taxonomy below.

EVIDENCE:
{combined_evidence[:15000]}

TAXONOMY & RULES:

LAYER 1 - Domain/Function (max 3 tags):
Valid values: {', '.join(LAYER_1_TAGS)}
- Select based on the candidate's primary work domain(s)

LAYER 2 - Job Family (max 3 tags):
Valid values: {', '.join(LAYER_2_TAGS)}
- Must be logically consistent with Layer 1 selections
- e.g., if Layer 1 has "ENGINEERING", Layer 2 should have related tags like "SOFTWARE_DEVELOPMENT"

LAYER 3 - Skills/Competencies (max 10 tags):
- Extract specific skills mentioned in evidence
- Normalize skill names (e.g., "MS Excel" → "Excel", "JavaScript/JS" → "JavaScript")
- Only include skills with clear evidence
- Rank by relevance/prominence

LAYER 4 - Scope of Work (max 3 tags):
Valid values: OPERATIONAL, TACTICAL, STRATEGIC
- OPERATIONAL: task execution, routine work, SOP-based, following instructions
- TACTICAL: coordination, optimization, problem-solving, team leadership
- STRATEGIC: decision-making, ownership, direction-setting, executive level
- Infer from responsibility verbs and achievements, NOT job title alone

EXTRACTION RULES:
1. Extraction must be evidence-based - cite specific evidence
2. Job titles alone are NOT sufficient
3. Prefer under-tagging over over-tagging
4. If confidence is low, leave the layer empty
5. Layer 1 and Layer 2 must be logically consistent

BLACKLISTED TAGS (DO NOT include these):
{', '.join(deleted_tags) if deleted_tags else 'None'}

Return a JSON object with this EXACT structure:
{{
    "layer_1": [
        {{"tag": "TAG_VALUE", "confidence": 0.0-1.0, "evidence": "brief citation"}}
    ],
    "layer_2": [
        {{"tag": "TAG_VALUE", "confidence": 0.0-1.0, "evidence": "brief citation"}}
    ],
    "layer_3": [
        {{"tag": "Normalized Skill Name", "confidence": 0.0-1.0, "evidence": "brief citation"}}
    ],
    "layer_4": [
        {{"tag": "TAG_VALUE", "confidence": 0.0-1.0, "evidence": "brief citation"}}
    ],
    "summary": "Brief summary of candidate profile"
}}

Return ONLY the JSON object, no other text."""

    try:
        messages = [{"role": "user", "content": prompt}]
        
        # Use with_usage version if user_id is provided for credit tracking
        if user_id:
            result = await call_openrouter_with_usage(api_key, model, messages, temperature=0.2)
            response = result["content"]
            
            # Deduct credits
            await deduct_credits(
                user_id,
                "tag_extraction",
                result["tokens_used"],
                result["cost"],
                model
            )
        else:
            # Fallback to old version (without credit tracking)
            response = await call_openrouter(api_key, model, messages, temperature=0.2)
        
        # Parse JSON response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(response[json_start:json_end])
        else:
            logger.error(f"Failed to parse tag extraction response: {response[:500]}")
            return {"tags": [], "summary": "Failed to parse AI response", "evidence_used": evidence_names}
        
        now = datetime.now(timezone.utc).isoformat()
        tags = []
        
        # Process Layer 1
        for item in result.get("layer_1", [])[:3]:
            tag_value = item.get("tag", "").upper()
            if tag_value in LAYER_1_TAGS and tag_value not in deleted_tags:
                tags.append(CandidateTag(
                    tag_value=tag_value,
                    layer=1,
                    layer_name="Domain / Function",
                    source="AUTO",
                    confidence_score=float(item.get("confidence", 0.5)),
                    created_at=now
                ))
        
        # Process Layer 2 (check consistency with Layer 1)
        layer_1_values = [t.tag_value for t in tags if t.layer == 1]
        valid_layer_2 = set()
        for l1 in layer_1_values:
            valid_layer_2.update(LAYER_1_TO_2_MAPPING.get(l1, []))
        
        for item in result.get("layer_2", [])[:3]:
            tag_value = item.get("tag", "").upper()
            # Check if tag is valid and consistent with Layer 1
            if tag_value in LAYER_2_TAGS and tag_value not in deleted_tags:
                if not layer_1_values or tag_value in valid_layer_2:
                    tags.append(CandidateTag(
                        tag_value=tag_value,
                        layer=2,
                        layer_name="Job Family",
                        source="AUTO",
                        confidence_score=float(item.get("confidence", 0.5)),
                        created_at=now
                    ))
        
        # Process Layer 3 (skills - free text, normalized)
        for item in result.get("layer_3", [])[:10]:
            tag_value = item.get("tag", "").strip()
            if tag_value and tag_value not in deleted_tags:
                # Normalize common variations
                normalized = tag_value.title()
                tags.append(CandidateTag(
                    tag_value=normalized,
                    layer=3,
                    layer_name="Skill / Competency",
                    source="AUTO",
                    confidence_score=float(item.get("confidence", 0.5)),
                    created_at=now
                ))
        
        # Process Layer 4
        for item in result.get("layer_4", [])[:3]:
            tag_value = item.get("tag", "").upper()
            if tag_value in LAYER_4_TAGS and tag_value not in deleted_tags:
                tags.append(CandidateTag(
                    tag_value=tag_value,
                    layer=4,
                    layer_name="Scope of Work",
                    source="AUTO",
                    confidence_score=float(item.get("confidence", 0.5)),
                    created_at=now
                ))
        
        return {
            "tags": tags,
            "summary": result.get("summary", ""),
            "evidence_used": evidence_names
        }
        
    except Exception as e:
        logger.error(f"Tag extraction error: {e}")
        return {"tags": [], "summary": f"Extraction failed: {str(e)}", "evidence_used": evidence_names}

@api_router.post("/candidates/{candidate_id}/extract-tags")
@limiter.limit("5/minute")
async def extract_candidate_tags(
    request: Request,
    candidate_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Extract tags from candidate evidence using AI.
    Preserves manual tags and respects blacklisted (deleted) tags.
    """
    candidate = await db.candidates.find_one(
        {"id": candidate_id, "company_id": current_user.get("company_id")},
        {"_id": 0}
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check credits first
    credit_check = await check_user_credits(current_user["id"])
    if not credit_check.has_credits:
        raise HTTPException(status_code=402, detail=credit_check.message)
    
    # Get global settings
    global_settings = await get_global_ai_settings()
    if not global_settings.get("openrouter_api_key"):
        raise HTTPException(status_code=400, detail="OpenRouter API key not configured. Please configure in admin settings.")
    
    admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    
    evidence_list = candidate.get("evidence", [])
    deleted_tags = candidate.get("deleted_tags", [])
    existing_tags = candidate.get("tags", [])
    
    # Preserve manual tags
    manual_tags = [t for t in existing_tags if t.get("source") == "MANUAL"]
    
    # Extract new tags (this will handle credit deduction internally)
    result = await extract_tags_from_evidence(
        evidence_list,
        deleted_tags,
        global_settings["openrouter_api_key"],
        global_settings["model_name"],
        admin_settings,
        current_user["id"]  # Pass user_id for credit deduction
    )
    
    # Combine manual tags with new auto tags (manual takes precedence)
    manual_tag_values = {t["tag_value"] for t in manual_tags}
    new_auto_tags = [t for t in result["tags"] if t.tag_value not in manual_tag_values]
    
    # Convert CandidateTag objects to dicts
    all_tags = manual_tags + [t.dict() for t in new_auto_tags]
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update candidate
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "tags": all_tags,
                "updated_at": now
            }
        }
    )
    
    updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    return {
        "status": "success",
        "tags": all_tags,
        "extraction_summary": result["summary"],
        "evidence_used": result["evidence_used"],
        "candidate": CandidateResponse(**{**updated, "tags": updated.get("tags", []), "deleted_tags": updated.get("deleted_tags", [])})
    }

@api_router.get("/candidates/{candidate_id}/tags")
async def get_candidate_tags(
    candidate_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all tags for a candidate."""
    candidate = await db.candidates.find_one(
        {"id": candidate_id, "company_id": current_user.get("company_id")},
        {"_id": 0, "tags": 1, "deleted_tags": 1}
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    tags = candidate.get("tags", [])
    
    # Group by layer
    grouped = {1: [], 2: [], 3: [], 4: []}
    for tag in tags:
        layer = tag.get("layer", 3)
        if layer in grouped:
            grouped[layer].append(tag)
    
    return {
        "tags": tags,
        "grouped": grouped,
        "deleted_tags": candidate.get("deleted_tags", []),
        "layer_info": LAYER_DEFINITIONS
    }

@api_router.post("/candidates/{candidate_id}/tags")
async def add_candidate_tag(
    candidate_id: str,
    data: TagAddRequest,
    current_user: dict = Depends(get_current_user)
):
    """Manually add a tag to a candidate."""
    candidate = await db.candidates.find_one(
        {"id": candidate_id, "company_id": current_user.get("company_id")},
        {"_id": 0}
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    layer = data.layer
    tag_value = data.tag_value.strip()
    
    # Validate layer
    if layer not in [1, 2, 3, 4]:
        raise HTTPException(status_code=400, detail="Invalid layer. Must be 1, 2, 3, or 4.")
    
    # Validate tag value for layers with predefined libraries
    layer_def = LAYER_DEFINITIONS[layer]
    if layer_def["library"]:
        tag_value = tag_value.upper()
        if tag_value not in layer_def["library"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid tag for Layer {layer}. Must be one of: {', '.join(layer_def['library'])}"
            )
    else:
        # Layer 3 - normalize to title case
        tag_value = tag_value.title()
    
    existing_tags = candidate.get("tags", [])
    
    # Check if tag already exists
    if any(t.get("tag_value") == tag_value and t.get("layer") == layer for t in existing_tags):
        raise HTTPException(status_code=400, detail="Tag already exists for this candidate")
    
    # Check max tags per layer
    layer_tags = [t for t in existing_tags if t.get("layer") == layer]
    if len(layer_tags) >= layer_def["max_tags"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Maximum {layer_def['max_tags']} tags allowed for Layer {layer} ({layer_def['name']})"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    new_tag = {
        "tag_value": tag_value,
        "layer": layer,
        "layer_name": layer_def["name"],
        "source": "MANUAL",
        "confidence_score": None,
        "created_at": now
    }
    
    # Remove from deleted_tags if it was blacklisted
    deleted_tags = candidate.get("deleted_tags", [])
    if tag_value in deleted_tags:
        deleted_tags.remove(tag_value)
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$push": {"tags": new_tag},
            "$set": {"deleted_tags": deleted_tags, "updated_at": now}
        }
    )
    
    updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    return {
        "status": "success",
        "tag": new_tag,
        "tags": updated.get("tags", [])
    }

@api_router.delete("/candidates/{candidate_id}/tags/{tag_value}")
async def delete_candidate_tag(
    candidate_id: str,
    tag_value: str,
    layer: int = Query(..., ge=1, le=4),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a tag from a candidate.
    If the tag was auto-generated, it gets blacklisted to prevent re-extraction.
    """
    candidate = await db.candidates.find_one(
        {"id": candidate_id, "company_id": current_user.get("company_id")},
        {"_id": 0}
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    existing_tags = candidate.get("tags", [])
    deleted_tags = candidate.get("deleted_tags", [])
    
    # Find the tag to delete
    tag_to_delete = None
    new_tags = []
    for tag in existing_tags:
        if tag.get("tag_value") == tag_value and tag.get("layer") == layer:
            tag_to_delete = tag
        else:
            new_tags.append(tag)
    
    if not tag_to_delete:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # If it was an AUTO tag, blacklist it
    if tag_to_delete.get("source") == "AUTO" and tag_value not in deleted_tags:
        deleted_tags.append(tag_value)
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "tags": new_tags,
                "deleted_tags": deleted_tags,
                "updated_at": now
            }
        }
    )
    
    return {
        "status": "success",
        "deleted_tag": tag_to_delete,
        "blacklisted": tag_to_delete.get("source") == "AUTO",
        "remaining_tags": new_tags
    }

@api_router.get("/tags/library")
async def get_tag_library(current_user: dict = Depends(get_current_user)):
    """Get the complete tag library for all layers."""
    return {
        "layers": {
            1: {
                "name": "Domain / Function",
                "max_tags": 3,
                "tags": LAYER_1_TAGS
            },
            2: {
                "name": "Job Family",
                "max_tags": 3,
                "tags": LAYER_2_TAGS
            },
            3: {
                "name": "Skill / Competency",
                "max_tags": 10,
                "tags": None,  # Free text
                "description": "Free text skills extracted from evidence"
            },
            4: {
                "name": "Scope of Work",
                "max_tags": 3,
                "tags": LAYER_4_TAGS,
                "definitions": {
                    "OPERATIONAL": "Task execution, routine work, SOP-based, following instructions",
                    "TACTICAL": "Coordination, optimization, problem-solving, team leadership",
                    "STRATEGIC": "Decision-making, ownership, direction-setting, executive level"
                }
            }
        },
        "consistency_rules": LAYER_1_TO_2_MAPPING
    }

# ==================== ANALYSIS ROUTES ====================

@api_router.post("/analysis/run", response_model=List[AnalysisResult])
@limiter.limit("5/minute")
async def run_batch_analysis(request: Request, payload: BatchAnalysisRequest, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": payload.job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.get("playbook"):
        raise HTTPException(status_code=400, detail="Job playbook not configured. Generate a playbook first.")
    
    # Check credits first (estimate for multiple candidates)
    credit_check = await check_user_credits(current_user["id"])
    if not credit_check.has_credits:
        raise HTTPException(status_code=402, detail=credit_check.message)
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    
    # Require company culture/values to be set up before analysis
    if not company or not company.get("values") or len(company.get("values", [])) == 0:
        raise HTTPException(
            status_code=400, 
            detail="Company culture values must be set up before running analysis. Please configure them in Company Settings."
        )
    
    # Get global settings and user language preference
    global_settings = await get_global_ai_settings()
    logger.info(f"Analysis: Retrieved global settings - has_key: {bool(global_settings.get('openrouter_api_key'))}, model: {global_settings.get('model_name')}")
    user_settings = await get_ai_settings(current_user["id"])
    
    results = []
    
    for candidate_id in payload.candidate_ids:
        candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user["company_id"]}, {"_id": 0})
        if not candidate:
            continue
        
        # Serialize to remove any ObjectId
        candidate = serialize_doc(candidate)
        
        # Check if analysis already exists
        existing = await db.analyses.find_one({"job_id": payload.job_id, "candidate_id": candidate_id}, {"_id": 0})
        if existing:
            existing = serialize_doc(existing)
            results.append(AnalysisResult(**existing))
            continue
        
        # Check credits before each analysis
        credit_check = await check_user_credits(current_user["id"])
        if not credit_check.has_credits:
            # If we run out of credits mid-batch, stop and return what we have
            break
        
        # Compile all evidence
        all_evidence = "\n\n".join([
            f"=== {e['type'].upper()} ({e['file_name']}) ===\n{e['content']}"
            for e in candidate.get("evidence", [])
        ])
        
        if not all_evidence:
            continue
        
        lang_instruction = "Respond in English." if user_settings.language == "en" else "Respond in Indonesian (Bahasa Indonesia)."
        
        company_values_text = ""
        if company and company.get("values"):
            company_values_text = "Company Values to evaluate alignment:\n" + "\n".join([
                f"- {v['name']} (Weight: {v['weight']}%): {v['description']}" 
                for v in company["values"]
            ])
        
        playbook = job["playbook"]
        
        # Enhanced prompt for better scoring
        prompt = f"""You are an AI evaluator for candidate-job fit analysis.

JOB POSITION: {job['title']}
Job Description: {job['description']}
Job Requirements: {job['requirements']}

{company_values_text}

CANDIDATE: {candidate['name']}
CANDIDATE EVIDENCE:
{all_evidence}

EVALUATION PLAYBOOK:

CHARACTER TRAITS (evaluate personality, soft skills, cultural fit):
{json.dumps(playbook.get('character', []), indent=2)}

REQUIREMENTS (evaluate education, experience, certifications):
{json.dumps(playbook.get('requirement', []), indent=2)}

SKILLS (evaluate technical abilities, tools, domain expertise):
{json.dumps(playbook.get('skill', []), indent=2)}

{lang_instruction}

SCORING PROCESS:
1. For EACH subcategory in each category, analyze the candidate evidence
2. Assign a score 0-100 based on how well the evidence supports that criterion
3. Provide short reasoning with specific evidence references
4. If evidence is missing or unclear, score lower and note the gap

IMPORTANT RULES:
- Be objective and consistent
- Do NOT hallucinate evidence - only reference what's in the documents
- If evidence is missing for a criterion, assign lower score (20-40) and explain
- Use ONLY the selected output language

Return a JSON object with this EXACT structure:
{{
  "category_scores": [
    {{
      "category": "character",
      "breakdown": [
        {{"item_id": "{playbook.get('character', [{}])[0].get('id', 'id1') if playbook.get('character') else 'id1'}", "item_name": "Name from playbook", "raw_score": 75, "reasoning": "Specific evidence-based justification"}}
      ]
    }},
    {{
      "category": "requirement",
      "breakdown": [...]
    }},
    {{
      "category": "skill", 
      "breakdown": [...]
    }}
  ],
  "overall_reasoning": "2-3 sentence summary of candidate's overall fit for this role",
  "company_values_alignment": {{
    "score": "<integer 0-100>",
    "breakdown": [
      {{"value_name": "Value Name", "score": "<integer 0-100>", "reasoning": "How candidate aligns"}}
    ],
    "notes": "Overall assessment of cultural fit"
  }},
  "strengths": ["List of 2-3 key strengths"],
  "gaps": ["List of 2-3 areas needing improvement or missing evidence"]
}}

Ensure you evaluate ALL items in each category of the playbook. Do not skip any."""

        messages = [{"role": "user", "content": prompt}]
        
        try:
            # Use with_usage version for credit tracking
            result = await call_openrouter_with_usage(
                global_settings["openrouter_api_key"], 
                global_settings["model_name"], 
                messages, 
                temperature=0.3
            )
            
            response = result["content"]
            
            # Deduct credits
            await deduct_credits(
                current_user["id"],
                "candidate_analysis",
                result["tokens_used"],
                result["cost"],
                global_settings["model_name"]
            )
            
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            analysis_data = json.loads(response[json_start:json_end])
            
            # Calculate weighted scores
            category_scores = []
            total_weighted = 0
            total_weight = 0
            
            for cat_data in analysis_data.get("category_scores", []):
                category = cat_data["category"]
                playbook_items = {item["id"]: item for item in playbook.get(category, [])}
                
                breakdown = []
                cat_total = 0
                cat_weight = 0
                
                for item_score in cat_data.get("breakdown", []):
                    item_id = item_score.get("item_id", "")
                    playbook_item = playbook_items.get(item_id, {})
                    weight = playbook_item.get("weight", 20)
                    raw_score = item_score.get("raw_score", 0)
                    weighted = (raw_score * weight) / 100
                    
                    breakdown.append(ScoreBreakdown(
                        item_id=item_id,
                        item_name=item_score.get("item_name", playbook_item.get("name", "")),
                        raw_score=raw_score,
                        weight=weight,
                        weighted_score=weighted,
                        reasoning=item_score.get("reasoning", "")
                    ))
                    
                    cat_total += weighted
                    cat_weight += weight
                
                cat_score = (cat_total / cat_weight * 100) if cat_weight > 0 else 0
                category_scores.append(CategoryScore(
                    category=category,
                    score=round(cat_score, 1),
                    breakdown=breakdown
                ))
                
                total_weighted += cat_score
                total_weight += 1
            
            final_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0
            
            analysis_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            
            analysis = {
                "id": analysis_id,
                "job_id": payload.job_id,
                "candidate_id": candidate_id,
                "candidate_name": candidate["name"],  # Store name for reference
                "final_score": final_score,
                "category_scores": [cs.model_dump() for cs in category_scores],
                "overall_reasoning": analysis_data.get("overall_reasoning", ""),
                "company_values_alignment": analysis_data.get("company_values_alignment"),
                "strengths": analysis_data.get("strengths", []),
                "gaps": analysis_data.get("gaps", []),
                "created_at": now
            }
            
            await db.analyses.insert_one(analysis)
            results.append(AnalysisResult(**analysis))
            
        except Exception as e:
            logger.error(f"Analysis failed for candidate {candidate_id}: {str(e)}")
            # Don't break the batch, continue with next candidate
            continue
    
    return results

# Streaming analysis endpoint for progress tracking
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

@api_router.post("/analysis/run-stream")
@limiter.limit("5/minute")
async def run_streaming_analysis(request: Request, payload: BatchAnalysisRequest, current_user: dict = Depends(get_current_user)):
    """Run analysis with streaming progress updates"""
    job = await db.jobs.find_one({"id": payload.job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.get("playbook"):
        raise HTTPException(status_code=400, detail="Job playbook not configured")
    
    # Check credits first
    credit_check = await check_user_credits(current_user["id"])
    if not credit_check.has_credits:
        raise HTTPException(status_code=402, detail=credit_check.message)
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    
    # Require company culture/values to be set up before analysis
    if not company or not company.get("values") or len(company.get("values", [])) == 0:
        raise HTTPException(
            status_code=400, 
            detail="Company culture values must be set up before running analysis. Please configure them in Company Settings."
        )
    
    # Get global settings and user language preference
    global_settings = await get_global_ai_settings()
    user_settings = await get_ai_settings(current_user["id"])
    logger.info(f"Streaming Analysis: Retrieved global settings - has_key: {bool(global_settings.get('openrouter_api_key'))}, model: {global_settings.get('model_name')}")
    
    # Get prompts from admin settings
    admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    job_fit_prompt_template = admin_settings.get("job_fit_prompt") if admin_settings else None
    
    async def generate_results():
        total = len(payload.candidate_ids)
        
        for idx, candidate_id in enumerate(payload.candidate_ids):
            candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user["company_id"]}, {"_id": 0})
            
            if not candidate:
                yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'status': 'skipped', 'message': 'Candidate not found'})}\n\n"
                continue
            
            # Serialize to ensure no ObjectId
            candidate = serialize_doc(candidate)
            
            # Send progress update - starting
            yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'candidate_name': candidate['name'], 'status': 'analyzing'})}\n\n"
            
            # Check existing
            existing = await db.analyses.find_one({"job_id": payload.job_id, "candidate_id": candidate_id}, {"_id": 0})
            if existing:
                # Serialize to ensure no ObjectId
                existing = serialize_doc(existing)
                yield f"data: {json.dumps({'type': 'result', 'current': idx + 1, 'total': total, 'analysis': existing})}\n\n"
                continue
            
            # Compile evidence
            all_evidence = "\n\n".join([
                f"=== {e['type'].upper()} ({e['file_name']}) ===\n{e['content']}"
                for e in candidate.get("evidence", [])
            ])
            
            if not all_evidence:
                yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'status': 'skipped', 'message': 'No evidence'})}\n\n"
                continue
            
            lang_instruction = "Respond in English." if user_settings.language == "en" else "Respond in Indonesian (Bahasa Indonesia)."
            
            company_values_text = ""
            if company and company.get("values"):
                company_values_text = "Company Values to evaluate alignment:\n" + "\n".join([
                    f"- {v['name']} (Weight: {v['weight']}%): {v['description']}" 
                    for v in company["values"]
                ])
            
            playbook = job["playbook"]
            
            # Use custom prompt if available, otherwise default
            if job_fit_prompt_template:
                prompt = job_fit_prompt_template.format(
                    job_title=job['title'],
                    job_description=job['description'],
                    job_requirements=job['requirements'],
                    company_values=company_values_text,
                    candidate_name=candidate['name'],
                    candidate_evidence=all_evidence,
                    character_playbook=json.dumps(playbook.get('character', []), indent=2),
                    requirement_playbook=json.dumps(playbook.get('requirement', []), indent=2),
                    skill_playbook=json.dumps(playbook.get('skill', []), indent=2),
                    language_instruction=lang_instruction
                )
            else:
                prompt = f"""You are an AI evaluator for candidate-job fit analysis.

JOB POSITION: {job['title']}
Job Description: {job['description']}
Job Requirements: {job['requirements']}

{company_values_text}

CANDIDATE: {candidate['name']}
CANDIDATE EVIDENCE:
{all_evidence}

EVALUATION PLAYBOOK:

CHARACTER TRAITS:
{json.dumps(playbook.get('character', []), indent=2)}

REQUIREMENTS:
{json.dumps(playbook.get('requirement', []), indent=2)}

SKILLS:
{json.dumps(playbook.get('skill', []), indent=2)}

{lang_instruction}

For EACH item in the playbook, score 0-100 with evidence-based reasoning.
If evidence is missing, score lower (20-40) and note the gap.

Return JSON:
{{
  "category_scores": [
    {{"category": "character", "breakdown": [{{"item_id": "id", "item_name": "name", "raw_score": 75, "reasoning": "evidence"}}]}},
    {{"category": "requirement", "breakdown": [...]}},
    {{"category": "skill", "breakdown": [...]}}
  ],
  "overall_reasoning": "Summary",
  "company_values_alignment": {{"score": "<integer 0-100>", "breakdown": [{{"value_name": "name", "score": "<integer 0-100>", "reasoning": "why"}}], "notes": "cultural fit"}},
  "strengths": ["strength1", "strength2"],
  "gaps": ["gap1", "gap2"]
}}"""

            messages = [{"role": "user", "content": prompt}]
            
            try:
                # Check credits before each candidate
                credit_check = await check_user_credits(current_user["id"])
                if not credit_check.has_credits:
                    yield f"data: {json.dumps({'type': 'error', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'message': credit_check.message})}\n\n"
                    break
                
                # Use with_usage version for credit tracking
                result = await call_openrouter_with_usage(
                    global_settings["openrouter_api_key"], 
                    global_settings["model_name"], 
                    messages, 
                    temperature=0.3
                )
                
                response = result["content"]
                
                # Deduct credits
                await deduct_credits(
                    current_user["id"],
                    "candidate_analysis",
                    result["tokens_used"],
                    result["cost"],
                    global_settings["model_name"]
                )
                
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                analysis_data = json.loads(response[json_start:json_end])
                
                # Calculate scores
                category_scores = []
                total_weighted = 0
                total_weight = 0
                
                for cat_data in analysis_data.get("category_scores", []):
                    category = cat_data["category"]
                    playbook_items = {item["id"]: item for item in playbook.get(category, [])}
                    
                    breakdown = []
                    cat_total = 0
                    cat_weight = 0
                    
                    for item_score in cat_data.get("breakdown", []):
                        item_id = item_score.get("item_id", "")
                        playbook_item = playbook_items.get(item_id, {})
                        weight = playbook_item.get("weight", 20)
                        raw_score = item_score.get("raw_score", 0)
                        weighted = (raw_score * weight) / 100
                        
                        breakdown.append({
                            "item_id": item_id,
                            "item_name": item_score.get("item_name", playbook_item.get("name", "")),
                            "raw_score": raw_score,
                            "weight": weight,
                            "weighted_score": weighted,
                            "reasoning": item_score.get("reasoning", "")
                        })
                        
                        cat_total += weighted
                        cat_weight += weight
                    
                    cat_score = (cat_total / cat_weight * 100) if cat_weight > 0 else 0
                    category_scores.append({
                        "category": category,
                        "score": round(cat_score, 1),
                        "breakdown": breakdown
                    })
                    
                    total_weighted += cat_score
                    total_weight += 1
                
                final_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0
                
                analysis_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                
                analysis = {
                    "id": analysis_id,
                    "job_id": payload.job_id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate["name"],  # Store name for reference
                    "final_score": final_score,
                    "category_scores": category_scores,
                    "overall_reasoning": analysis_data.get("overall_reasoning", ""),
                    "company_values_alignment": analysis_data.get("company_values_alignment"),
                    "strengths": analysis_data.get("strengths", []),
                    "gaps": analysis_data.get("gaps", []),
                    "created_at": now
                }
                
                await db.analyses.insert_one(analysis)
                
                # Serialize to ensure no ObjectId before JSON dump
                analysis = serialize_doc(analysis)
                yield f"data: {json.dumps({'type': 'result', 'current': idx + 1, 'total': total, 'analysis': analysis})}\n\n"
                
            except Exception as e:
                logger.error(f"Analysis failed for {candidate_id}: {e}")
                yield f"data: {json.dumps({'type': 'error', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'error': str(e)})}\n\n"
        
        yield f"data: {json.dumps({'type': 'complete', 'total': total})}\n\n"
    
    return FastAPIStreamingResponse(
        generate_results(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@api_router.post("/candidates/check-duplicates")
async def check_duplicate_candidates(
    emails: List[str] = [],
    current_user: dict = Depends(get_current_user)
):
    """Check if candidates with given emails already exist"""
    if not current_user.get("company_id"):
        return {"duplicates": []}
    
    # Find existing candidates with matching emails
    existing = await db.candidates.find(
        {"company_id": current_user["company_id"], "email": {"$in": emails}},
        {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(100)
    
    return {"duplicates": existing}

@api_router.get("/analysis/job/{job_id}", response_model=List[AnalysisResult])
async def get_job_analyses(job_id: str, min_score: Optional[float] = None, current_user: dict = Depends(get_current_user)):
    query = {"job_id": job_id}
    
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if min_score is not None:
        query["final_score"] = {"$gte": min_score}
    
    analyses = await db.analyses.find(query, {"_id": 0}).sort("final_score", -1).to_list(1000)
    # Serialize to ensure no ObjectId in nested structures
    analyses = [serialize_doc(a) for a in analyses]
    return [AnalysisResult(**a) for a in analyses]

@api_router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    analysis = await db.analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    # Serialize to ensure no ObjectId
    analysis = serialize_doc(analysis)
    return AnalysisResult(**analysis)

@api_router.delete("/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.analyses.delete_one({"id": analysis_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Analysis deleted"}

class BulkDeleteRequest(BaseModel):
    ids: List[str]

@api_router.post("/analysis/bulk-delete")
async def bulk_delete_analyses(request: BulkDeleteRequest, current_user: dict = Depends(get_current_user)):
    """Delete multiple analysis results at once"""
    if not request.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")
    
    result = await db.analyses.delete_many({"id": {"$in": request.ids}})
    return {"message": f"Deleted {result.deleted_count} analysis result(s)"}

class PDFReportRequest(BaseModel):
    job_id: str
    candidate_ids: List[str]

@api_router.post("/analysis/generate-pdf")
async def generate_pdf_report(request: PDFReportRequest, current_user: dict = Depends(get_current_user)):
    """Generate PDF report for selected candidates"""
    # Get job details
    job = await db.jobs.find_one({"id": request.job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get company details
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    
    # Get user settings for branding (logo, colors)
    user_settings = await db.settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    
    # Get analyses for selected candidates
    analyses = []
    for candidate_id in request.candidate_ids:
        analysis = await db.analyses.find_one(
            {"job_id": request.job_id, "candidate_id": candidate_id},
            {"_id": 0}
        )
        if analysis:
            # Get candidate details
            candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
            analysis["candidate_name"] = candidate.get("name", "Unknown") if candidate else "Unknown"
            analysis["candidate_email"] = candidate.get("email", "") if candidate else ""
            analyses.append(analysis)
    
    if not analyses:
        raise HTTPException(status_code=404, detail="No analysis results found for selected candidates")
    
    # Generate PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Get colors from settings or use defaults
    primary_color = colors.HexColor(user_settings.get("primary_color", "#6366f1")) if user_settings and user_settings.get("primary_color") else colors.HexColor("#6366f1")
    secondary_color = colors.HexColor(user_settings.get("secondary_color", "#8b5cf6")) if user_settings and user_settings.get("secondary_color") else colors.HexColor("#8b5cf6")
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=primary_color,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=primary_color,
        spaceAfter=12,
        spaceBefore=12
    )
    normal_style = styles['Normal']
    
    story = []
    
    # Page 1: Executive Summary
    story.append(Paragraph(f"<b>{job['title']}</b>", title_style))
    story.append(Paragraph("Candidate Analysis Report", styles['Heading2']))
    story.append(Spacer(1, 0.3*inch))
    
    # Job details
    story.append(Paragraph(f"<b>Job Position:</b> {job['title']}", normal_style))
    story.append(Paragraph(f"<b>Company:</b> {company.get('name', 'N/A') if company else 'N/A'}", normal_style))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", normal_style))
    story.append(Paragraph(f"<b>Candidates Analyzed:</b> {len(analyses)}", normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Top recommendations
    sorted_analyses = sorted(analyses, key=lambda x: x['final_score'], reverse=True)
    story.append(Paragraph("<b>Top Recommendations:</b>", heading_style))
    for idx, analysis in enumerate(sorted_analyses[:3], 1):
        score_color = "green" if analysis['final_score'] >= 70 else "orange" if analysis['final_score'] >= 50 else "red"
        story.append(Paragraph(
            f"{idx}. <b>{analysis['candidate_name']}</b> - "
            f"<font color='{score_color}'>{round(analysis['final_score'])}%</font>",
            normal_style
        ))
    
    story.append(PageBreak())
    
    # Page 2: Job Details
    story.append(Paragraph("<b>Job Details</b>", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    def render_playbook_category(category_name, items):
        if not items:
            return
        
        # Category header
        story.append(Paragraph(f"<b>{category_name.title()} Criteria</b>", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Category items
        for item in items:
            name = item.get('name', '')
            desc = item.get('description', '')
            weight = item.get('weight', 0)
            
            # Formatted list item
            item_text = f"• <b>{name}</b> ({weight}%): {desc}"
            # Render using standard paragraph style with indent if needed
            story.append(Paragraph(item_text, normal_style))
            story.append(Spacer(1, 0.05*inch))
        
        story.append(Spacer(1, 0.2*inch))

    playbook = job.get('playbook', {})
    if playbook:
        story.append(Paragraph("<b>Evaluation Playbook:</b>", title_style))
        story.append(Spacer(1, 0.15*inch))
        
        if playbook.get('requirement'):
            render_playbook_category('Requirement', playbook['requirement'])
            
        if playbook.get('skill'):
            render_playbook_category('Skill', playbook['skill'])
            
        if playbook.get('character'):
            render_playbook_category('Character', playbook['character'])
    else:
        story.append(Paragraph("<i>No evaluation criteria defined for this position.</i>", normal_style))
    
    story.append(PageBreak())
    
    # Individual candidate analyses
    for idx, analysis in enumerate(sorted_analyses, 1):
        story.append(Paragraph(f"<b>Candidate {idx}: {analysis['candidate_name']}</b>", title_style))
        if analysis.get('candidate_email'):
            story.append(Paragraph(f"Email: {analysis['candidate_email']}", normal_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Overall score
        score_color = "green" if analysis['final_score'] >= 70 else "orange" if analysis['final_score'] >= 50 else "red"
        story.append(Paragraph(
            f"<b>Overall Job Fit Score:</b> <font color='{score_color}' size='20'>{round(analysis['final_score'])}%</font>",
            heading_style
        ))
        story.append(Spacer(1, 0.2*inch))
        
        # Summary
        if analysis.get('overall_reasoning'):
            story.append(Paragraph("<b>Summary:</b>", heading_style))
            summary_html = str(analysis['overall_reasoning']).replace('\n', '<br/>')
            story.append(Paragraph(summary_html, normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        # Strengths
        if analysis.get('strengths'):
            story.append(Paragraph("<b>Key Strengths:</b>", heading_style))
            for strength in analysis['strengths']:
                story.append(Paragraph(f"• {strength}", normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        # Gaps
        if analysis.get('gaps'):
            story.append(Paragraph("<b>Development Areas:</b>", heading_style))
            for gap in analysis['gaps']:
                story.append(Paragraph(f"• {gap}", normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        # Company values alignment
        if analysis.get('company_values_alignment'):
            cv_align = analysis['company_values_alignment']
            story.append(Paragraph(f"<b>Company Culture Fit:</b> {round(cv_align.get('score', 0))}%", heading_style))
            if cv_align.get('notes'):
                notes_html = str(cv_align['notes']).replace('\n', '<br/>')
                story.append(Paragraph(notes_html, normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        # Category scores table
        if analysis.get('category_scores'):
            story.append(Paragraph("<b>Category Breakdown:</b>", heading_style))
            table_data = [['Category', 'Score']]
            for cat in analysis['category_scores']:
                table_data.append([cat['category'].capitalize(), f"{round(cat['score'])}%"])
            
            t = Table(table_data, colWidths=[3*inch, 1.5*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            story.append(t)
        
        if idx < len(sorted_analyses):
            story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    pdf_buffer.seek(0)
    
    # Return as streaming response
    filename = f"Analysis_Report_{job['title'].replace(' ', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==================== SETTINGS ROUTES ====================

@api_router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    settings = await db.settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    if settings:
        # Mask API key for security
        if settings.get("openrouter_api_key"):
            key = settings["openrouter_api_key"]
            settings["openrouter_api_key_masked"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "****"
            settings["has_api_key"] = True
        else:
            settings["openrouter_api_key_masked"] = ""
            settings["has_api_key"] = False
        del settings["openrouter_api_key"]
    return settings or {"model_name": "openai/gpt-4o-mini", "language": "en", "has_api_key": False}

@api_router.put("/settings")
async def update_settings(data: SettingsUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    await db.settings.update_one(
        {"user_id": current_user["id"]},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "Settings updated"}

# ==================== ADMIN SETTINGS ROUTES ====================

class AdminSettingsUpdate(BaseModel):
    cv_parse_prompt: Optional[str] = None
    company_values_prompt: Optional[str] = None
    job_desc_title_prompt: Optional[str] = None
    job_desc_narrative_prompt: Optional[str] = None
    playbook_prompt: Optional[str] = None
    job_fit_prompt: Optional[str] = None

@api_router.get("/admin-settings")
async def get_admin_settings(current_user: dict = Depends(get_current_user)):
    """Get all admin/prompt settings"""
    settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    
    # Return defaults if not set
    defaults = {
        "cv_parse_prompt": """Extract contact information from this CV/resume text.

CV TEXT (first 3000 chars):
{cv_text}

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information""",
        
        "company_values_prompt": """Based on this company culture narrative, generate 5-7 structured company values.

Narrative: {narrative}

{language_instruction}

Return a JSON array with this structure:
[
  {{"name": "Value Name", "description": "Brief description of this value", "weight": 15}}
]

Requirements:
- Each value should have a clear, concise name
- Description should be 1-2 sentences
- Weights should total exactly 100
- Values should be distinct and meaningful for candidate evaluation""",
        
        "job_desc_title_prompt": """Generate a professional job description and requirements for the position: {job_title}

{language_instruction}

Return a JSON object with:
{{
  "description": "Full job description including: About the Role, Key Responsibilities (as bullet points), What You'll Do",
  "requirements": "List of requirements including: Required Experience, Required Skills, Qualifications, Nice-to-haves"
}}

Make it professional, detailed, and suitable for attracting qualified candidates.""",
        
        "job_desc_narrative_prompt": """Based on the following job description narrative, generate a professional and structured job description and requirements.

Job Title: {job_title}
Narrative/Context: {narrative}

{language_instruction}

Return a JSON object with:
{{
  "description": "Full job description including: About the Role, Key Responsibilities (as bullet points), What You'll Do",
  "requirements": "List of requirements including: Required Experience, Required Skills, Qualifications, Nice-to-haves"
}}

Make it professional, well-structured, and suitable for attracting qualified candidates. Use the narrative as the primary source of information.""",
        
        "playbook_prompt": """Generate a comprehensive job evaluation playbook/rubric for screening candidates.

Job Title: {job_title}
Job Description: {job_description}
Requirements: {job_requirements}
{company_values}

{language_instruction}

Create evaluation criteria in 3 categories. Each category must have exactly 5 items with weights totaling 100%.

Return a JSON object:
{{
  "character": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ],
  "requirement": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ],
  "skill": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ]
}}

Categories:
- Character: Personality traits, cultural fit, soft skills, work ethic
- Requirement: Education, experience, certifications, mandatory qualifications  
- Skill: Technical abilities, tools, domain expertise

Make criteria specific to this role and measurable from CV/resume review.""",
        
        "job_fit_prompt": """You are an AI evaluator for candidate-job fit analysis.

JOB POSITION: {job_title}
Job Description: {job_description}
Job Requirements: {job_requirements}

{company_values}

CANDIDATE: {candidate_name}
CANDIDATE EVIDENCE:
{candidate_evidence}

EVALUATION PLAYBOOK:

CHARACTER TRAITS:
{character_playbook}

REQUIREMENTS:
{requirement_playbook}

SKILLS:
{skill_playbook}

{language_instruction}

SCORING PROCESS:
1. For EACH subcategory in each category, analyze the candidate evidence
2. Assign a score 0-100 based on how well the evidence supports that criterion
3. Provide short reasoning with specific evidence references
4. If evidence is missing for a criterion, assign lower score (20-40) and explain

IMPORTANT RULES:
- Be objective and consistent
- Do NOT hallucinate evidence - only reference what's in the documents
- If evidence is missing, score lower and note the gap
- Use ONLY the selected output language

Return JSON:
{{
  "category_scores": [
    {{"category": "character", "breakdown": [{{"item_id": "id", "item_name": "name", "raw_score": 75, "reasoning": "evidence"}}]}},
    {{"category": "requirement", "breakdown": [...]}},
    {{"category": "skill", "breakdown": [...]}}
  ],
  "overall_reasoning": "Summary",
  "company_values_alignment": {{"score": "<integer 0-100>", "breakdown": [{{"value_name": "name", "score": "<integer 0-100>", "reasoning": "why"}}], "notes": "cultural fit"}},
  "strengths": ["strength1", "strength2"],
  "gaps": ["gap1", "gap2"]
}}"""
    }
    
    if settings:
        # Merge with defaults
        for key in defaults:
            if key not in settings or not settings[key]:
                settings[key] = defaults[key]
        return settings
    
    return defaults

@api_router.put("/admin-settings")
async def update_admin_settings(data: AdminSettingsUpdate, current_user: dict = Depends(get_current_user)):
    """Update admin/prompt settings"""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["user_id"] = current_user["id"]
    
    await db.admin_settings.update_one(
        {"user_id": current_user["id"]},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "Admin settings updated"}

@api_router.post("/admin-settings/reset/{prompt_key}")
async def reset_admin_prompt(prompt_key: str, current_user: dict = Depends(get_current_user)):
    """Reset a specific prompt to default"""
    valid_keys = ["cv_parse_prompt", "company_values_prompt", "job_desc_title_prompt", 
                  "job_desc_narrative_prompt", "playbook_prompt", "job_fit_prompt"]
    
    if prompt_key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid prompt key. Valid keys: {valid_keys}")
    
    await db.admin_settings.update_one(
        {"user_id": current_user["id"]},
        {"$unset": {prompt_key: ""}}
    )
    
    return {"message": f"{prompt_key} reset to default"}

# ==================== CANDIDATE UPDATE ROUTE ====================

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

@api_router.put("/candidates/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(candidate_id: str, data: CandidateUpdate, current_user: dict = Depends(get_current_user)):
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.candidates.update_one({"id": candidate_id}, {"$set": update_data})
    
    updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    return CandidateResponse(**updated)

# Re-parse candidate CV with AI
@api_router.post("/candidates/{candidate_id}/reparse")
async def reparse_candidate_cv(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Re-parse candidate info from CV using AI"""
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Find CV evidence
    cv_evidence = next((e for e in candidate.get("evidence", []) if e["type"] == "cv"), None)
    if not cv_evidence:
        raise HTTPException(status_code=400, detail="No CV found for this candidate")
    
    settings = await get_ai_settings(current_user["id"])
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=400, detail="Configure OpenRouter API key first")
    
    admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    cv_parse_prompt = admin_settings.get("cv_parse_prompt") if admin_settings else None
    
    parsed_text = cv_evidence["content"]
    
    if cv_parse_prompt:
        prompt = cv_parse_prompt.format(cv_text=parsed_text[:3000])
    else:
        prompt = f"""Extract contact information from this CV/resume text.

CV TEXT (first 3000 chars):
{parsed_text[:3000]}

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information"""

    messages = [{"role": "user", "content": prompt}]
    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.1)
    
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start >= 0 and json_end > json_start:
        contact_info = json.loads(response[json_start:json_end])
        
        update_data = {
            "name": contact_info.get("name", candidate["name"]).strip() or candidate["name"],
            "email": contact_info.get("email", candidate["email"]).strip() or candidate["email"],
            "phone": contact_info.get("phone", candidate["phone"]).strip() or candidate["phone"],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.candidates.update_one({"id": candidate_id}, {"$set": update_data})
        
        updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
        return CandidateResponse(**updated)
    
    raise HTTPException(status_code=500, detail="Failed to parse CV")

# ==================== DASHBOARD ROUTES ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    company_id = current_user.get("company_id")
    if not company_id:
        return {
            "total_candidates": 0,
            "open_jobs": 0,
            "analyses_completed": 0,
            "avg_score": 0
        }
    
    total_candidates = await db.candidates.count_documents({"company_id": company_id})
    open_jobs = await db.jobs.count_documents({"company_id": company_id, "status": "open"})
    
    # Get all job IDs for this company
    jobs = await db.jobs.find({"company_id": company_id}, {"id": 1}).to_list(1000)
    job_ids = [j["id"] for j in jobs]
    
    analyses_completed = await db.analyses.count_documents({"job_id": {"$in": job_ids}})
    
    # Calculate average score
    pipeline = [
        {"$match": {"job_id": {"$in": job_ids}}},
        {"$group": {"_id": None, "avg_score": {"$avg": "$final_score"}}}
    ]
    avg_result = await db.analyses.aggregate(pipeline).to_list(1)
    avg_score = round(avg_result[0]["avg_score"], 1) if avg_result else 0
    
    return {
        "total_candidates": total_candidates,
        "open_jobs": open_jobs,
        "analyses_completed": analyses_completed,
        "avg_score": avg_score
    }

@api_router.get("/dashboard/recent-activity")
async def get_recent_activity(current_user: dict = Depends(get_current_user)):
    company_id = current_user.get("company_id")
    if not company_id:
        return []
    
    activities = []
    
    # Recent candidates
    recent_candidates = await db.candidates.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "name": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    for c in recent_candidates:
        activities.append({
            "type": "candidate_added",
            "message": f"New candidate: {c['name']}",
            "timestamp": c["created_at"]
        })
    
    # Recent jobs
    recent_jobs = await db.jobs.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "title": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    for j in recent_jobs:
        activities.append({
            "type": "job_created",
            "message": f"New job: {j['title']}",
            "timestamp": j["created_at"]
        })
    
    # Sort by timestamp
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    return activities[:10]

# ==================== EXTENSION: ZIP UPLOAD & DUPLICATE DETECTION ====================
# NOTE: These endpoints are ADDITIVE and do not modify existing flows
# Existing upload-cv and check-duplicates endpoints remain unchanged

import zipfile
import re

# Helper: Normalize phone number for comparison (strip all non-digits)
def normalize_phone(phone: str) -> str:
    """Normalize phone number by removing all non-digit characters"""
    if not phone:
        return ""
    return re.sub(r'\D', '', phone)

# Helper: Normalize email for comparison (lowercase, strip whitespace)
def normalize_email(email: str) -> str:
    """Normalize email for comparison"""
    if not email:
        return ""
    return email.lower().strip()

# Helper: Normalize name for comparison (lowercase, strip extra whitespace)
def normalize_name(name: str) -> str:
    """Normalize name for comparison"""
    if not name:
        return ""
    return ' '.join(name.lower().split())

# Models for new endpoints
class DuplicateDetectionRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None

class DuplicateMatch(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_phone: str
    match_reasons: List[str]
    confidence: str  # "high", "medium"

class DuplicateDetectionResponse(BaseModel):
    has_duplicates: bool
    matches: List[DuplicateMatch]

class MergeRequest(BaseModel):
    source_candidate_id: str
    target_candidate_id: str

class MergeLogEntry(BaseModel):
    action: str
    source_id: str
    target_id: str
    source_name: str
    target_name: str
    evidence_transferred: int
    merged_by: str
    merged_at: str

@api_router.post("/candidates/detect-duplicates", response_model=DuplicateDetectionResponse)
async def detect_duplicates(
    data: DuplicateDetectionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Enhanced duplicate detection using hard rules.
    
    Checks for duplicates based on:
    1. Email match (case-insensitive)
    2. Phone match (normalized - digits only)
    3. Email + Name match combination
    
    Returns potential duplicates with match reasons for HR decision.
    Does NOT auto-merge - waits for explicit merge request.
    """
    if not current_user.get("company_id"):
        return DuplicateDetectionResponse(has_duplicates=False, matches=[])
    
    company_id = current_user["company_id"]
    matches = []
    
    # Normalize input values
    input_email = normalize_email(data.email) if data.email else ""
    input_phone = normalize_phone(data.phone) if data.phone else ""
    input_name = normalize_name(data.name) if data.name else ""
    
    # Skip if no data provided
    if not input_email and not input_phone and not input_name:
        return DuplicateDetectionResponse(has_duplicates=False, matches=[])
    
    # Get all candidates for this company
    candidates = await db.candidates.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1}
    ).to_list(10000)
    
    for candidate in candidates:
        match_reasons = []
        
        cand_email = normalize_email(candidate.get("email", ""))
        cand_phone = normalize_phone(candidate.get("phone", ""))
        cand_name = normalize_name(candidate.get("name", ""))
        
        # Rule 1: Email match (case-insensitive)
        if input_email and cand_email and input_email == cand_email:
            match_reasons.append("email_match")
        
        # Rule 2: Phone match (normalized)
        if input_phone and cand_phone and len(input_phone) >= 7 and len(cand_phone) >= 7:
            # Match if last 7+ digits are the same (handles country code differences)
            if input_phone[-7:] == cand_phone[-7:] or input_phone == cand_phone:
                match_reasons.append("phone_match")
        
        # Rule 3: Email + Name combination match
        if input_email and input_name and cand_email and cand_name:
            if input_email == cand_email and input_name == cand_name:
                if "email_match" not in match_reasons:
                    match_reasons.append("email_match")
                match_reasons.append("name_match")
        
        if match_reasons:
            # Determine confidence
            if "email_match" in match_reasons and ("phone_match" in match_reasons or "name_match" in match_reasons):
                confidence = "high"
            elif "email_match" in match_reasons:
                confidence = "high"
            elif "phone_match" in match_reasons:
                confidence = "medium"
            else:
                confidence = "medium"
            
            matches.append(DuplicateMatch(
                candidate_id=candidate["id"],
                candidate_name=candidate.get("name", ""),
                candidate_email=candidate.get("email", ""),
                candidate_phone=candidate.get("phone", ""),
                match_reasons=match_reasons,
                confidence=confidence
            ))
    
    return DuplicateDetectionResponse(
        has_duplicates=len(matches) > 0,
        matches=matches
    )

@api_router.post("/candidates/merge")
async def merge_candidates(
    data: MergeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Merge two candidates.
    
    - Appends all evidence from source candidate to target candidate
    - Does NOT overwrite any existing target candidate fields
    - Logs the merge action for audit purposes
    - Deletes the source candidate after successful merge
    
    Returns the updated target candidate.
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    company_id = current_user["company_id"]
    
    # Fetch source candidate
    source = await db.candidates.find_one(
        {"id": data.source_candidate_id, "company_id": company_id},
        {"_id": 0}
    )
    if not source:
        raise HTTPException(status_code=404, detail="Source candidate not found")
    
    # Fetch target candidate
    target = await db.candidates.find_one(
        {"id": data.target_candidate_id, "company_id": company_id},
        {"_id": 0}
    )
    if not target:
        raise HTTPException(status_code=404, detail="Target candidate not found")
    
    # Prevent self-merge
    if data.source_candidate_id == data.target_candidate_id:
        raise HTTPException(status_code=400, detail="Cannot merge candidate with itself")
    
    now = datetime.now(timezone.utc).isoformat()
    source_evidence = source.get("evidence", [])
    
    # Append source evidence to target (do NOT overwrite existing)
    if source_evidence:
        # Mark transferred evidence with merge metadata
        for ev in source_evidence:
            ev["merged_from"] = data.source_candidate_id
            ev["merged_at"] = now
        
        await db.candidates.update_one(
            {"id": data.target_candidate_id},
            {
                "$push": {"evidence": {"$each": source_evidence}},
                "$set": {"updated_at": now}
            }
        )
    
    # Create merge log entry
    merge_log = {
        "id": str(uuid.uuid4()),
        "action": "candidate_merge",
        "source_id": data.source_candidate_id,
        "target_id": data.target_candidate_id,
        "source_name": source.get("name", ""),
        "target_name": target.get("name", ""),
        "source_email": source.get("email", ""),
        "target_email": target.get("email", ""),
        "evidence_transferred": len(source_evidence),
        "merged_by": current_user["id"],
        "merged_by_name": current_user.get("name", ""),
        "company_id": company_id,
        "merged_at": now
    }
    await db.merge_logs.insert_one(merge_log)
    
    # Delete source candidate
    await db.candidates.delete_one({"id": data.source_candidate_id})
    
    # Fetch and return updated target
    updated_target = await db.candidates.find_one({"id": data.target_candidate_id}, {"_id": 0})
    
    logger.info(f"Merged candidate {data.source_candidate_id} into {data.target_candidate_id}")
    
    return {
        "message": "Candidates merged successfully",
        "target_candidate": CandidateResponse(**updated_target),
        "evidence_transferred": len(source_evidence),
        "merge_log_id": merge_log["id"]
    }

class ZipUploadResponse(BaseModel):
    status: str  # "created", "duplicate_warning", "error"
    candidate: Optional[CandidateResponse] = None
    duplicates: Optional[List[DuplicateMatch]] = None
    message: str
    files_processed: int
    evidence_attached: int

@api_router.post("/candidates/upload-zip", response_model=ZipUploadResponse)
async def upload_zip(
    file: UploadFile = File(...),
    force_create: bool = Form(False),
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Upload a ZIP file containing candidate evidence.
    
    One ZIP file = one candidate
    
    Expected ZIP structure:
    - CV/resume PDF (required): looked for in root or cv/ folder
    - Additional evidence: psychotest/, knowledge_test/, or evidence/ folders
    
    Process:
    1. Extract ZIP contents
    2. Find and parse CV to get candidate info
    3. Run duplicate detection BEFORE creating candidate
    4. If duplicates found and force_create=False: return warning
    5. If no duplicates or force_create=True: create candidate with all evidence
    
    Reuses existing PDF parsing logic.
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    
    company_id = current_user["company_id"]
    content = await file.read()
    
    try:
        zip_buffer = io.BytesIO(content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            
            # Find CV file (PDF in root or cv/ folder)
            cv_file = None
            cv_content = None
            evidence_files = []
            
            for fname in file_list:
                # Skip directories and hidden files
                if fname.endswith('/') or fname.startswith('__MACOSX') or '/.' in fname:
                    continue
                
                lower_fname = fname.lower()
                base_name = fname.split('/')[-1].lower()
                
                # Identify CV file
                if lower_fname.endswith('.pdf'):
                    # Priority: files in root or cv/ folder, or with cv/resume in name
                    is_cv = (
                        '/' not in fname or  # Root level
                        fname.lower().startswith('cv/') or
                        fname.lower().startswith('resume/') or
                        'cv' in base_name or
                        'resume' in base_name
                    )
                    
                    if is_cv and cv_file is None:
                        cv_file = fname
                        cv_content = zf.read(fname)
                    else:
                        # Treat as additional evidence
                        evidence_files.append({
                            "name": fname,
                            "content": zf.read(fname),
                            "type": categorize_evidence(fname)
                        })
                elif lower_fname.endswith(('.txt', '.doc', '.docx')):
                    # Other document types as evidence
                    evidence_files.append({
                        "name": fname,
                        "content": zf.read(fname),
                        "type": categorize_evidence(fname)
                    })
            
            if not cv_file or not cv_content:
                raise HTTPException(
                    status_code=400, 
                    detail="No CV/resume PDF found in ZIP. Please include a PDF file in the root or cv/ folder."
                )
            
            # Parse CV using existing function
            parsed_text = parse_pdf(cv_content)
            if not parsed_text:
                raise HTTPException(status_code=400, detail="Could not extract text from CV PDF")
            
            # Extract candidate info (reuse existing AI/fallback logic)
            settings = await get_ai_settings(current_user["id"])
            admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
            
            name = ""
            email = ""
            phone = ""
            
            # AI parsing
            if settings.openrouter_api_key:
                try:
                    cv_parse_prompt = admin_settings.get("cv_parse_prompt") if admin_settings else None
                    
                    if cv_parse_prompt:
                        prompt = cv_parse_prompt.format(cv_text=parsed_text[:3000])
                    else:
                        prompt = f"""Extract contact information from this CV/resume text.

CV TEXT (first 3000 chars):
{parsed_text[:3000]}

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information"""

                    messages = [{"role": "user", "content": prompt}]
                    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.1)
                    
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        contact_info = json.loads(response[json_start:json_end])
                        name = contact_info.get("name", "").strip()
                        email = contact_info.get("email", "").strip()
                        phone = contact_info.get("phone", "").strip()
                except Exception as e:
                    logger.warning(f"AI CV parsing failed in ZIP upload, using fallback: {e}")
            
            # Fallback parsing (same as existing upload-cv)
            if not name:
                lines = parsed_text.split('\n')
                for line in lines[:10]:
                    line = line.strip()
                    if line and len(line) > 2 and len(line) < 50:
                        if not any(c.isdigit() for c in line) and '@' not in line:
                            name = line
                            break
                if not name:
                    name = "Unknown Candidate"
            
            if not email:
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                emails = re.findall(email_pattern, parsed_text)
                email = emails[0] if emails else ""
            
            if not phone:
                phone_patterns = [
                    r'\+?[\d\s\-\(\)]{10,}',
                    r'\d{3}[\s\-]?\d{3}[\s\-]?\d{4}',
                    r'\(\d{3}\)\s?\d{3}[\s\-]?\d{4}'
                ]
                for pattern in phone_patterns:
                    phones = re.findall(pattern, parsed_text[:1000])
                    if phones:
                        phone = phones[0].strip()
                        break
            
            # Run duplicate detection BEFORE creating
            if not force_create:
                duplicates = await _find_duplicates(company_id, email, phone, name)
                
                if duplicates:
                    return ZipUploadResponse(
                        status="duplicate_warning",
                        candidate=None,
                        duplicates=[DuplicateMatch(**d) for d in duplicates],
                        message=f"Found {len(duplicates)} potential duplicate(s). Review and choose to merge or create new.",
                        files_processed=1 + len(evidence_files),
                        evidence_attached=0
                    )
            
            # Create candidate
            now = datetime.now(timezone.utc).isoformat()
            candidate_id = str(uuid.uuid4())
            
            # Build evidence list - use evidence splitting for CV
            cv_evidence = await split_pdf_into_evidence(
                cv_content, 
                cv_file.split('/')[-1],
                settings.openrouter_api_key if settings else None,
                settings.model_name if settings else None
            )
            
            evidence_list = []
            for ev in cv_evidence:
                evidence_list.append({
                    "type": ev["type"],
                    "file_name": ev["file_name"],
                    "content": ev["content"],
                    "uploaded_at": now,
                    "source": "zip_upload",
                    "pages": ev.get("pages", [])
                })
            
            # Add additional evidence files (with splitting for PDFs)
            for ev_file in evidence_files:
                if ev_file["content"]:
                    if ev_file["name"].lower().endswith('.pdf'):
                        try:
                            # Split this PDF too
                            split_evidence = await split_pdf_into_evidence(
                                ev_file["content"],
                                ev_file["name"].split('/')[-1],
                                settings.openrouter_api_key if settings else None,
                                settings.model_name if settings else None
                            )
                            for sev in split_evidence:
                                evidence_list.append({
                                    "type": sev["type"],
                                    "file_name": sev["file_name"],
                                    "content": sev["content"],
                                    "uploaded_at": now,
                                    "source": "zip_upload",
                                    "pages": sev.get("pages", [])
                                })
                        except Exception:
                            # Fallback: use original categorization
                            try:
                                ev_content = parse_pdf(ev_file["content"])
                                evidence_list.append({
                                    "type": ev_file["type"],
                                    "file_name": ev_file["name"].split('/')[-1],
                                    "content": ev_content,
                                    "uploaded_at": now,
                                    "source": "zip_upload"
                                })
                            except Exception:
                                pass
                    else:
                        try:
                            ev_content = ev_file["content"].decode('utf-8', errors='ignore')
                        except Exception:
                            ev_content = "[Binary content]"
                        
                        evidence_list.append({
                            "type": ev_file["type"],
                            "file_name": ev_file["name"].split('/')[-1],
                            "content": ev_content,
                            "uploaded_at": now,
                            "source": "zip_upload"
                        })
            
            candidate = {
                "id": candidate_id,
                "company_id": company_id,
                "name": name,
                "email": email,
                "phone": phone,
                "evidence": evidence_list,
                "tags": [],
                "deleted_tags": [],
                "created_at": now,
                "updated_at": now,
                "upload_source": "zip"
            }
            
            await db.candidates.insert_one(candidate)
            
            # Auto-extract tags if API key is configured
            if settings.openrouter_api_key:
                try:
                    tag_result = await extract_tags_from_evidence(
                        evidence_list,
                        [],
                        settings.openrouter_api_key,
                        settings.model_name
                    )
                    if tag_result.get("tags"):
                        extracted_tags = [t.dict() for t in tag_result["tags"]]
                        await db.candidates.update_one(
                            {"id": candidate_id},
                            {"$set": {"tags": extracted_tags}}
                        )
                        candidate["tags"] = extracted_tags
                except Exception as e:
                    logger.warning(f"Auto tag extraction failed for ZIP upload: {e}")
            
            logger.info(f"Created candidate {candidate_id} from ZIP upload with {len(evidence_list)} evidence files")
            
            return ZipUploadResponse(
                status="created",
                candidate=CandidateResponse(**{**candidate, "tags": candidate.get("tags", []), "deleted_tags": []}),
                duplicates=None,
                message=f"Candidate created successfully with {len(evidence_list)} evidence file(s)",
                files_processed=1 + len(evidence_files),
                evidence_attached=len(evidence_list)
            )
    
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ZIP upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process ZIP file: {str(e)}")

def categorize_evidence(filename: str) -> str:
    """Helper: Categorize evidence file based on path/name"""
    lower = filename.lower()
    
    if 'psycho' in lower or 'personality' in lower or 'assessment' in lower:
        return 'psychotest'
    elif 'knowledge' in lower or 'test' in lower or 'exam' in lower or 'quiz' in lower:
        return 'knowledge_test'
    elif 'cert' in lower or 'certificate' in lower or 'diploma' in lower:
        return 'certificate'
    elif 'portfolio' in lower or 'work' in lower or 'sample' in lower:
        return 'portfolio'
    elif 'reference' in lower or 'recommendation' in lower:
        return 'reference'
    else:
        return 'other'
# ==================== PHASE 1: COMPETENCY LIBRARY ====================

@api_router.post("/competencies", response_model=Competency)
async def create_competency(
    comp: CompetencyCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
        
    if len(comp.levels) != 5:
        raise HTTPException(status_code=400, detail="A competency must have exactly 5 levels (1-5).")
        
    sorted_levels = sorted(comp.levels, key=lambda x: x.level)
    for i, level in enumerate(sorted_levels):
        if level.level != i + 1:
            raise HTTPException(status_code=400, detail="Competency levels must be exactly 1, 2, 3, 4, and 5.")
            
    now = datetime.now(timezone.utc).isoformat()
    comp_data = comp.model_dump()
    comp_data["company_id"] = company_id  # Override from token
    comp_obj = Competency(**comp_data, created_at=now, updated_at=now)
    await db.competencies.insert_one(comp_obj.model_dump())
    return comp_obj

@api_router.get("/competencies", response_model=List[Competency])
async def list_competencies(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    cursor = db.competencies.find({"company_id": company_id})
    return [Competency(**doc) async for doc in cursor]

@api_router.get("/competencies/{comp_id}", response_model=Competency)
async def get_competency(
    comp_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    doc = await db.competencies.find_one({"id": comp_id, "company_id": company_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Competency not found")
    return Competency(**doc)

@api_router.put("/competencies/{comp_id}", response_model=Competency)
async def update_competency(
    comp_id: str,
    comp_update: CompetencyCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    
    if len(comp_update.levels) != 5:
        raise HTTPException(status_code=400, detail="A competency must have exactly 5 levels (1-5).")
        
    sorted_levels = sorted(comp_update.levels, key=lambda x: x.level)
    for i, level in enumerate(sorted_levels):
        if level.level != i + 1:
            raise HTTPException(status_code=400, detail="Competency levels must be exactly 1, 2, 3, 4, and 5.")
            
    result = await db.competencies.update_one(
        {"id": comp_id, "company_id": company_id},
        {"$set": {
            "name": comp_update.name,
            "description": comp_update.description,
            "type": comp_update.type.value,
            "levels": [lvl.model_dump() for lvl in comp_update.levels],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Competency not found")
        
    doc = await db.competencies.find_one({"id": comp_id, "company_id": company_id})
    return Competency(**doc)

@api_router.delete("/competencies/{comp_id}")
async def delete_competency(
    comp_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    result = await db.competencies.delete_one({"id": comp_id, "company_id": company_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Competency not found")
    return {"message": "Competency deleted successfully"}

@api_router.post("/competencies/seed")
async def seed_competencies(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    """Seed the database with a default PLN/Astra competency template."""
    company_id = get_company_id(current_user)
    existing_count = await db.competencies.count_documents({"company_id": company_id})
    if existing_count > 0:
        return {"message": "Company already has competencies. Skipping seed.", "seeded": 0}
        
    template = [
        {
            "name": "Analytical Thinking",
            "description": "Kemampuan menganalisis situasi kompleks dan mengambil keputusan logis.",
            "type": "hard_skill",
            "levels": [
                {"level": 1, "description": "Membutuhkan panduan untuk menganalisis masalah sederhana."},
                {"level": 2, "description": "Menganalisis masalah sederhana secara mandiri."},
                {"level": 3, "description": "Menganalisis masalah kompleks dan mengidentifikasi akar penyebab."},
                {"level": 4, "description": "Mengantisipasi masalah kompleks dan merancang strategi preventif."},
                {"level": 5, "description": "Menciptakan kerangka analitis baru untuk organisasi."}
            ]
        },
        {
            "name": "Effective Communication",
            "description": "Kemampuan mengartikulasikan ide dengan jelas dan mendengarkan secara aktif.",
            "type": "soft_skill",
            "levels": [
                {"level": 1, "description": "Kesulitan mengartikulasikan pikiran dengan jelas."},
                {"level": 2, "description": "Mengomunikasikan ide dasar dengan cukup baik."},
                {"level": 3, "description": "Mengomunikasikan ide kompleks secara jelas dan mendengarkan saran."},
                {"level": 4, "description": "Mampu mempersuasi dan memengaruhi orang lain secara efektif."},
                {"level": 5, "description": "Negosiator dan orator ulung di tingkat strategis/eksekutif."}
            ]
        },
        {
            "name": "Achievement Orientation",
            "description": "Dorongan untuk bekerja dengan baik atau melampaui standar prestasi yang ditetapkan.",
            "type": "soft_skill",
            "levels": [
                {"level": 1, "description": "Bekerja sekadar memenuhi target minimal."},
                {"level": 2, "description": "Bekerja melampaui target yang ditetapkan sendiri."},
                {"level": 3, "description": "Meningkatkan performansi untuk efisiensi sistem."},
                {"level": 4, "description": "Menetapkan dan mencapai tujuan menantang bagi unit kerjanya."},
                {"level": 5, "description": "Membuat keputusan bisnis berisiko demi pertumbuhan organisasi."}
            ]
        }
    ]
    
    seeded_count = 0
    now = datetime.now(timezone.utc).isoformat()
    for comp_data in template:
        comp_id = str(uuid.uuid4())
        levels = [CompetencyLevel(**lvl) for lvl in comp_data["levels"]]
        comp_obj = Competency(
            id=comp_id,
            company_id=company_id,
            name=comp_data["name"],
            description=comp_data["description"],
            type=CompetencyType(comp_data["type"]),
            levels=levels,
            created_at=now,
            updated_at=now
        )
        await db.competencies.insert_one(comp_obj.model_dump())
        seeded_count += 1
        
    return {
        "message": f"Seed successful for company {company_id}", 
        "seeded": seeded_count,
        "template": "PLN/Astra Default Core"
    }

# ==================== PHASE 1: POSITIONS ====================

@api_router.post("/positions", response_model=Position)
async def create_position(
    pos: PositionCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
        
    now = datetime.now(timezone.utc).isoformat()
    pos_id = str(uuid.uuid4())
    pos_data = pos.model_dump()
    pos_data["company_id"] = company_id  # Override from token
    pos_obj = Position(
        id=pos_id,
        **pos_data,
        created_at=now,
        updated_at=now
    )
    await db.positions.insert_one(pos_obj.model_dump())
    return pos_obj

@api_router.get("/positions", response_model=List[Position])
async def list_positions(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    cursor = db.positions.find({"company_id": company_id})
    return [Position(**doc) async for doc in cursor]

@api_router.get("/positions/{pos_id}", response_model=Position)
async def get_position(
    pos_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    doc = await db.positions.find_one({"id": pos_id, "company_id": company_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Position not found")
    return Position(**doc)

@api_router.put("/positions/{pos_id}", response_model=Position)
async def update_position(
    pos_id: str,
    pos_update: PositionCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    # This fully replaces required_competencies array
    result = await db.positions.update_one(
        {"id": pos_id, "company_id": company_id},
        {"$set": {
            "title": pos_update.title,
            "department": pos_update.department,
            "level": pos_update.level,
            "required_competencies": [comp.model_dump() for comp in pos_update.required_competencies],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Position not found")
        
    doc = await db.positions.find_one({"id": pos_id, "company_id": company_id})
    return Position(**doc)

@api_router.delete("/positions/{pos_id}")
async def delete_position(
    pos_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    result = await db.positions.delete_one({"id": pos_id, "company_id": company_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"message": "Position deleted successfully"}

@api_router.post("/positions/seed")
async def seed_positions(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    """Seed the database with default positions (Golongan 1-6) using existing competencies."""
    company_id = get_company_id(current_user)
    
    # 1. Dependency check: competencies must exist
    comps_cursor = db.competencies.find({"company_id": company_id})
    competencies = [Competency(**doc) async for doc in comps_cursor]
    
    if not competencies:
        raise HTTPException(status_code=400, detail="Cannot seed positions. No competencies found for this company. Seed competencies first.")
        
    # 2. Idempotency check: skip if positions already exist
    existing_count = await db.positions.count_documents({"company_id": company_id})
    if existing_count > 0:
        return {"message": "Company already has positions. Skipping seed.", "seeded": 0}
        
    # 3. Create positions Golongan 1 to 6
    seeded_count = 0
    now = datetime.now(timezone.utc).isoformat()
    
    positions_data = [
        {"title": "Staff / Pelaksana", "level": 1, "department": "General"},
        {"title": "Supervisor Dasar", "level": 2, "department": "General"},
        {"title": "Supervisor Lanjutan", "level": 3, "department": "General"},
        {"title": "Manajer Dasar", "level": 4, "department": "General"},
        {"title": "Manajer Menengah", "level": 5, "department": "General"},
        {"title": "Manajer Atas / Eksekutif", "level": 6, "department": "General"}
    ]
    
    demo_samples = []
    
    for pos_info in positions_data:
        # Calculate standard minimum based on level
        lvl = pos_info["level"]
        std_min = min(lvl, 5) # Cap at level 5
        
        req_comps = []
        for comp in competencies:
            req_comps.append(
                PositionCompetencyRequirement(
                    competency_id=comp.id,
                    rubric_id=None,
                    standard_minimum=std_min,
                    weight_evidence=50,
                    weight_roleplay=50
                )
            )
            
        pos_id = str(uuid.uuid4())
        pos_obj = Position(
            id=pos_id,
            company_id=company_id,
            title=pos_info["title"],
            department=pos_info["department"],
            level=lvl,
            required_competencies=req_comps,
            created_at=now,
            updated_at=now
        )
        await db.positions.insert_one(pos_obj.model_dump())
        seeded_count += 1
        
        if lvl in [1, 6]:
            demo_samples.append(pos_obj.model_dump())
        
    return {
        "message": f"Seed successful for company {company_id}",
        "seeded": seeded_count,
        "template": "Golongan 1-6 Core",
        "demo_samples": demo_samples
    }

# ==================== PHASE 1: EVALUATION RUBRICS ====================

@api_router.post("/rubrics", response_model=EvaluationRubric)
async def create_rubric(
    rubric: EvaluationRubricCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
        
    now = datetime.now(timezone.utc).isoformat()
    rubric_id = str(uuid.uuid4())
    rubric_data = rubric.model_dump()
    rubric_data["company_id"] = company_id  # Override from token
    rubric_obj = EvaluationRubric(
        id=rubric_id,
        **rubric_data,
        created_at=now,
        updated_at=now
    )
    await db.evaluation_rubrics.insert_one(rubric_obj.model_dump())
    return rubric_obj

@api_router.get("/rubrics", response_model=List[EvaluationRubric])
async def list_rubrics(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    cursor = db.evaluation_rubrics.find({"company_id": company_id})
    return [EvaluationRubric(**doc) async for doc in cursor]

@api_router.get("/rubrics/{rubric_id}", response_model=EvaluationRubric)
async def get_rubric(
    rubric_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    doc = await db.evaluation_rubrics.find_one({"id": rubric_id, "company_id": company_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return EvaluationRubric(**doc)

@api_router.put("/rubrics/{rubric_id}", response_model=EvaluationRubric)
async def update_rubric(
    rubric_id: str,
    rubric_update: EvaluationRubricCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    result = await db.evaluation_rubrics.update_one(
        {"id": rubric_id, "company_id": company_id},
        {"$set": {
            "name": rubric_update.name,
            "evidence_mapping": rubric_update.evidence_mapping,
            "roleplay_mapping": rubric_update.roleplay_mapping,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rubric not found")
        
    doc = await db.evaluation_rubrics.find_one({"id": rubric_id, "company_id": company_id})
    return EvaluationRubric(**doc)

@api_router.delete("/rubrics/{rubric_id}")
async def delete_rubric(
    rubric_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    result = await db.evaluation_rubrics.delete_one({"id": rubric_id, "company_id": company_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return {"message": "Rubric deleted successfully"}

@api_router.post("/rubrics/seed")
async def seed_rubrics(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    """Seed the database with an example baseline Evaluation Rubric."""
    company_id = get_company_id(current_user)
    
    # Needs to match against competencies, let's fetch a soft-skill for roleplay and hard-skill for evidence if possible
    comps_cursor = db.competencies.find({"company_id": company_id})
    competencies = [Competency(**doc) async for doc in comps_cursor]
    
    if not competencies:
        raise HTTPException(status_code=400, detail="Seed competencies first.")
        
    existing_count = await db.evaluation_rubrics.count_documents({"company_id": company_id})
    if existing_count > 0:
        return {"message": "Company already has rubrics. Skipping seed.", "seeded": 0}
        
    # We will pick 1 competency for Roleplay and 1 for Evidence as an example
    # Since we use the PLN template, Analytical Thinking is likely present.
    sample_comp_1 = competencies[0].id
    sample_comp_2 = competencies[1].id if len(competencies) > 1 else sample_comp_1
    
    now = datetime.now(timezone.utc).isoformat()
    rubric_id = str(uuid.uuid4())
    
    # Demonstrate dynamic configuration arrays without hardcoded variables
    evidence_map = [
        {
            "category": "leadership_experience", 
            "maps_to_competency_id": sample_comp_1,
            "weight_in_evidence": 50
        },
        {
            "category": "technical_certifications",
            "maps_to_competency_id": sample_comp_2,
            "weight_in_evidence": 50
        }
    ]
    
    roleplay_map = [
        {
            "dimension": "problem_solving",
            "maps_to_competency_id": sample_comp_1,
            "weight_in_roleplay": 100
        }
    ]
    
    rubric_obj = EvaluationRubric(
        id=rubric_id,
        company_id=company_id,
        name="Baseline Standard Rubric",
        evidence_mapping=evidence_map,
        roleplay_mapping=roleplay_map,
        created_at=now,
        updated_at=now
    )
    
    await db.evaluation_rubrics.insert_one(rubric_obj.model_dump())
    
    return {
        "message": f"Seed successful for company {company_id}",
        "seeded": 1,
        "sample": rubric_obj.model_dump()
    }

# Include router and middleware
app.include_router(api_router)

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
    client.close()
