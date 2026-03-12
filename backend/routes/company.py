
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


# ==================== COMPANY ROUTES ====================


@router.post("/company", response_model=CompanyResponse)
async def create_company(data: CompanyCreate, current_user: dict = Depends(get_current_user)):
    """DEPRECATED: Company creation is now admin-managed only. Use /api/admin/companies."""
    raise HTTPException(
        status_code=410,
        detail="Self-service company creation has been disabled. Contact your platform administrator."
    )

@router.get("/company", response_model=Optional[CompanyResponse])
async def get_company(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return None
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    if not company:
        return None
    
    return CompanyResponse(**company)

@router.put("/company", response_model=CompanyResponse)
async def update_company(data: CompanyUpdate, current_user: dict = Depends(get_current_user)):
    """DEPRECATED: Company updates are now admin-managed only. Use /api/admin/companies/{id}."""
    raise HTTPException(
        status_code=410,
        detail="Self-service company updates have been disabled. Contact your platform administrator."
    )

@router.post("/company/generate-values")
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

