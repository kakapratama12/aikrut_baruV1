
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


# ==================== CANDIDATE ROUTES ====================


@router.post("/candidates", response_model=CandidateResponse)
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

@router.get("/candidates", response_model=List[CandidateResponse])
async def list_candidates(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return []
    
    candidates = await db.candidates.find({"company_id": current_user["company_id"]}, {"_id": 0}).to_list(1000)
    return [CandidateResponse(**c) for c in candidates]

# Candidate search/pagination endpoint - MUST be before {candidate_id} route
@router.get("/candidates/search")
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
@router.get("/candidates/merge-logs")
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

@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse(**candidate)

@router.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.candidates.delete_one({"id": candidate_id, "company_id": current_user.get("company_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"message": "Candidate deleted"}

@router.post("/candidates/upload-cv")
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

@router.post("/candidates/{candidate_id}/upload-evidence")
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

@router.delete("/candidates/{candidate_id}/evidence/{evidence_index}")
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



@router.post("/candidates/replace")
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

@router.post("/candidates/{candidate_id}/extract-tags")
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

@router.get("/candidates/{candidate_id}/tags")
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

@router.post("/candidates/{candidate_id}/tags")
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

@router.delete("/candidates/{candidate_id}/tags/{tag_value}")
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

@router.get("/tags/library")
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


# ==================== CANDIDATE UPDATE ROUTE ====================




@router.put("/candidates/{candidate_id}", response_model=CandidateResponse)
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
@router.post("/candidates/{candidate_id}/reparse")
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










@router.post("/candidates/detect-duplicates", response_model=DuplicateDetectionResponse)
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

@router.post("/candidates/merge")
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



@router.post("/candidates/upload-zip", response_model=ZipUploadResponse)
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
