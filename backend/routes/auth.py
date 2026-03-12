
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query, status, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any, Union
import uuid
from datetime import datetime, timezone, timedelta
import io
import json
import logging
from bson import ObjectId
import traceback

from backend.config import db, logger, limiter, JWT_SECRET, JWT_ALGORITHM, ADMIN_JWT_SECRET
from backend.auth.dependencies import hash_password, verify_password, create_token, get_current_user, RequireRole, get_company_id
from backend.auth.admin import create_admin_token, get_current_admin
from backend.services.credit import deduct_credits, check_user_credits
from backend.services.ai_service import get_ai_settings, call_openrouter, call_openrouter_with_usage
from backend.services.evidence import parse_pdf, parse_pdf_by_pages, split_pdf_into_evidence, classify_page_by_keywords, classify_page_with_ai, serialize_doc

from backend.models.user import UserRole, UserCreate, UserLogin, UserResponse, TokenResponse, ApproveUserRequest, UserUpdateByAdmin
from backend.models.company import CompanyValue, CompanyCreate, CompanyUpdate, CompanyResponse, AdminCompanyCreate, AdminCompanyUpdate, AdminCompanyResponse
from backend.models.job import PlaybookItem, JobPlaybook, JobCreate, JobUpdate, JobResponse
from backend.models.candidate import CandidateEvidence, CandidateCreate, CandidateTag, TagAddRequest, TagExtractionResponse, CandidateResponse, ScoreBreakdown, CategoryScore, AnalysisResult, BatchAnalysisRequest, LAYER_1_TAGS, LAYER_2_TAGS, LAYER_4_TAGS, LAYER_DEFINITIONS, LAYER_1_TO_2_MAPPING, CandidateUpdate, ReplaceCandidate
from backend.models.admin import AdminLogin, AdminTokenResponse, AdminDashboardStats, CreditTopupRequest, CreditEstimateResponse, GlobalSettingsUpdate, CreditRatesUpdate, AdminSettingsUpdate, SettingsUpdate
from backend.models.common import BulkDeleteRequest, PDFReportRequest, ZipUploadResponse, DuplicateDetectionRequest, DuplicateDetectionResponse, DuplicateMatch, MergeRequest, MergeLogEntry
from backend.models.assessment import Competency, CompetencyCreate, Position, PositionCreate, EvaluationRubric, EvaluationRubricCreate, AssessmentSession, AssessmentSessionCreate, AssessmentStatus, AssessmentPurpose, AIRecommendation, FinalOutcome, CompetencyProfile, CompetencyProfileCreate

router = APIRouter()


# ==================== AUTH ROUTES ====================


@router.post("/auth/register", response_model=TokenResponse)
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

@router.post("/auth/login", response_model=TokenResponse)
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

@router.get("/auth/me", response_model=UserResponse)
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

