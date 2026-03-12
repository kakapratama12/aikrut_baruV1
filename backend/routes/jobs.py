
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


# ==================== JOB ROUTES ====================


@router.post("/jobs", response_model=JobResponse)
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

@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return []
    
    jobs = await db.jobs.find({"company_id": current_user["company_id"]}, {"_id": 0}).to_list(1000)
    return [JobResponse(**job) for job in jobs]

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job)

@router.put("/jobs/{job_id}", response_model=JobResponse)
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

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.jobs.delete_one({"id": job_id, "company_id": current_user.get("company_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted"}

@router.post("/jobs/generate-description")
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

@router.post("/jobs/{job_id}/generate-playbook")
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

