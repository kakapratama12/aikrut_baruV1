
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

from backend.config import db, logger, limiter, JWT_SECRET, JWT_ALGORITHM, ADMIN_JWT_SECRET, SUPER_ADMIN_USERNAME, SUPER_ADMIN_PASSWORD
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


# ==================== ADMIN ROUTES ====================


@router.post("/admin/login", response_model=AdminTokenResponse)
async def admin_login(credentials: AdminLogin):
    if credentials.username != SUPER_ADMIN_USERNAME or credentials.password != SUPER_ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    
    token = create_admin_token(credentials.username)
    return AdminTokenResponse(
        access_token=token,
        username=credentials.username
    )

@router.get("/admin/dashboard", response_model=AdminDashboardStats)
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

@router.get("/admin/users")
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

@router.put("/admin/users/{user_id}")
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

@router.post("/admin/users/{user_id}/approve")
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

@router.post("/admin/users/{user_id}/reject")
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




# Fixed credit cost table (BUMN-friendly: predictable numbers for PO/budgeting)
# Editable via Super Admin in a future release — for now, derived from DEFAULT_CREDIT_RATES
CREDIT_COST_TABLE = {
    "evidence_analysis": 10,    # credits per session
    "roleplay_session": 25,     # credits per session
    "competency_scoring": 5,    # credits per session
}

@router.post("/admin/users/{user_id}/credits/topup")
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

@router.get("/admin/users/{user_id}/credits/history")
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

@router.get("/admin/companies/{company_id}/credits/usage")
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


@router.get("/credits/estimate", response_model=CreditEstimateResponse)
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



@router.post("/admin/companies", response_model=AdminCompanyResponse)
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

@router.get("/admin/companies")
async def admin_list_companies(
    admin: dict = Depends(get_current_admin)
):
    """List all companies (Super Admin only)."""
    cursor = db.companies.find({}, {"_id": 0})
    companies = await cursor.to_list(1000)
    return {"companies": companies, "total": len(companies)}

@router.get("/admin/companies/{company_id}", response_model=AdminCompanyResponse)
async def admin_get_company(
    company_id: str,
    admin: dict = Depends(get_current_admin)
):
    """Get company detail (Super Admin only)."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return AdminCompanyResponse(**company)

@router.put("/admin/companies/{company_id}", response_model=AdminCompanyResponse)
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

@router.delete("/admin/companies/{company_id}")
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




@router.get("/admin/settings")
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

@router.put("/admin/settings")
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

@router.get("/admin/credit-rates")
async def get_credit_rates(admin: dict = Depends(get_current_admin)):
    """Get credit rate multipliers for different operations."""
    rates = await db.admin_settings.find_one({"type": "credit_rates"}, {"_id": 0})
    if not rates:
        return {"rates": DEFAULT_CREDIT_RATES}
    return rates

@router.put("/admin/credit-rates")
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

@router.get("/admin/usage-logs")
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


# ==================== ADMIN SETTINGS ROUTES ====================




@router.get("/admin-settings")
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

@router.put("/admin-settings")
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

@router.post("/admin-settings/reset/{prompt_key}")
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

