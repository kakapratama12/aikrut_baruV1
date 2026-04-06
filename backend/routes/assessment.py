
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
from backend.services.evidence import parse_pdf, parse_pdf_by_pages, split_pdf_into_evidence, classify_page_by_keywords, classify_page_with_ai, serialize_doc, parse_file_content, VALID_EVIDENCE_TYPES, HR_ONLY_EVIDENCE_TYPES, EMPLOYEE_ALLOWED_TYPES
from backend.services.roleplay import RoleplaySessionInput, RoleplaySessionOutput, create_roleplay_session, get_roleplay_result
from backend.services.session import validate_transition, transition_session_status, notify_employee, VALID_TRANSITIONS

DEFAULT_WEIGHTS = {
    "behavioral": {"evidence": 30, "roleplay": 70},
    "technical":  {"evidence": 60, "roleplay": 40},
    "default":    {"evidence": 50, "roleplay": 50},
}

from backend.models.user import UserRole, UserCreate, UserLogin, UserResponse, TokenResponse, ApproveUserRequest, UserUpdateByAdmin
from backend.models.company import CompanyValue, CompanyCreate, CompanyUpdate, CompanyResponse, AdminCompanyCreate, AdminCompanyUpdate, AdminCompanyResponse
from backend.models.job import PlaybookItem, JobPlaybook, JobCreate, JobUpdate, JobResponse
from backend.models.candidate import CandidateEvidence, CandidateCreate, CandidateTag, TagAddRequest, TagExtractionResponse, CandidateResponse, ScoreBreakdown, CategoryScore, AnalysisResult, BatchAnalysisRequest, LAYER_1_TAGS, LAYER_2_TAGS, LAYER_4_TAGS, LAYER_DEFINITIONS, LAYER_1_TO_2_MAPPING, CandidateUpdate, ReplaceCandidate
from backend.models.admin import AdminLogin, AdminTokenResponse, AdminDashboardStats, CreditTopupRequest, CreditEstimateResponse, GlobalSettingsUpdate, CreditRatesUpdate, AdminSettingsUpdate, SettingsUpdate
from backend.models.common import BulkDeleteRequest, PDFReportRequest, ZipUploadResponse, DuplicateDetectionRequest, DuplicateDetectionResponse, DuplicateMatch, MergeRequest, MergeLogEntry
from backend.models.assessment import Competency, CompetencyCreate, Position, PositionCreate, EvaluationRubric, EvaluationRubricCreate, AssessmentSession, AssessmentSessionCreate, AssessmentStatus, AssessmentPurpose, AIRecommendation, FinalOutcome, CompetencyProfile, CompetencyProfileCreate, AssessmentBatch, AssessmentBatchCreate, BatchStatus

router = APIRouter()


# ==================== PHASE 1: COMPETENCY LIBRARY ====================


@router.post("/competencies", response_model=Competency)
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

@router.get("/competencies", response_model=List[Competency])
async def list_competencies(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    cursor = db.competencies.find({"company_id": company_id})
    return [Competency(**doc) async for doc in cursor]

@router.get("/competencies/{comp_id}", response_model=Competency)
async def get_competency(
    comp_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    doc = await db.competencies.find_one({"id": comp_id, "company_id": company_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Competency not found")
    return Competency(**doc)

@router.put("/competencies/{comp_id}", response_model=Competency)
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

@router.delete("/competencies/{comp_id}")
async def delete_competency(
    comp_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    result = await db.competencies.delete_one({"id": comp_id, "company_id": company_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Competency not found")
    return {"message": "Competency deleted successfully"}

@router.post("/competencies/seed")
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


@router.post("/positions", response_model=Position)
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

@router.get("/positions", response_model=List[Position])
async def list_positions(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    cursor = db.positions.find({"company_id": company_id})
    return [Position(**doc) async for doc in cursor]

@router.get("/positions/{pos_id}", response_model=Position)
async def get_position(
    pos_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    doc = await db.positions.find_one({"id": pos_id, "company_id": company_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Position not found")
    return Position(**doc)

@router.put("/positions/{pos_id}", response_model=Position)
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

@router.delete("/positions/{pos_id}")
async def delete_position(
    pos_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    result = await db.positions.delete_one({"id": pos_id, "company_id": company_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"message": "Position deleted successfully"}

@router.post("/positions/seed")
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


@router.post("/rubrics", response_model=EvaluationRubric)
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

@router.get("/rubrics", response_model=List[EvaluationRubric])
async def list_rubrics(
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    cursor = db.evaluation_rubrics.find({"company_id": company_id})
    return [EvaluationRubric(**doc) async for doc in cursor]

@router.get("/rubrics/{rubric_id}", response_model=EvaluationRubric)
async def get_rubric(
    rubric_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager, UserRole.viewer))
):
    company_id = get_company_id(current_user)
    doc = await db.evaluation_rubrics.find_one({"id": rubric_id, "company_id": company_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return EvaluationRubric(**doc)

@router.put("/rubrics/{rubric_id}", response_model=EvaluationRubric)
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

@router.delete("/rubrics/{rubric_id}")
async def delete_rubric(
    rubric_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    result = await db.evaluation_rubrics.delete_one({"id": rubric_id, "company_id": company_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return {"message": "Rubric deleted successfully"}

@router.post("/rubrics/seed")
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



# ==================== PHASE 2: ROLEPLAY ENGINE ====================

@router.post("/roleplay/sessions")
async def start_roleplay_session(
    input_data: RoleplaySessionInput,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    # Credit consumption checks
    credit_check = await check_user_credits(current_user["id"])
    if not credit_check.has_credits:
        raise HTTPException(status_code=402, detail=credit_check.message)

    # Proceed to create the session
    try:
        session_result = await create_roleplay_session(input_data)
        
        # Deduct credits after confirmed creation
        await deduct_credits(
            user_id=current_user["id"],
            operation_type="roleplay_session",
            tokens_used=0,        # mock: 0, actual: dari Elwyn response
            openrouter_cost=0.0,  # mock: 0, actual: dari Elwyn response
            model_used="elwyn-mock"
        )
        
        return session_result
    except Exception as e:
        logger.error(f"Failed to create roleplay session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize roleplay engine")

@router.get("/roleplay/sessions/{session_id}/result", response_model=RoleplaySessionOutput)
async def fetch_roleplay_result(
    session_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    try:
        return await get_roleplay_result(session_id)
    except Exception as e:
        logger.error(f"Failed to fetch roleplay result: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve roleplay results")


# ==================== PHASE 2: ASSESSMENT SESSION MANAGEMENT ====================


class StatusTransitionRequest(BaseModel):
    new_status: str
    override_reason: Optional[str] = None
    reviewer_notes: Optional[str] = None


@router.post("/sessions")
async def create_assessment_session(
    session_data: AssessmentSessionCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    """HR Admin creates a new assessment session. Status starts at 'pending'."""
    company_id = get_company_id(current_user)

    # Validate target_position exists for this company
    position = await db.positions.find_one({
        "id": session_data.target_position_id,
        "company_id": company_id
    })
    if not position:
        raise HTTPException(status_code=404, detail="Target position not found")

    now = datetime.now(timezone.utc).isoformat()
    session_id = str(uuid.uuid4())

    session_obj = AssessmentSession(
        id=session_id,
        company_id=company_id,
        person_id=session_data.person_id,
        target_position_id=session_data.target_position_id,
        purpose=session_data.purpose,
        status=AssessmentStatus.pending,
        created_at=now
    )

    await db.assessment_sessions.insert_one(session_obj.model_dump())

    return session_obj.model_dump()


@router.get("/sessions")
async def list_assessment_sessions(
    status: Optional[str] = None,
    purpose: Optional[str] = None,
    person_id: Optional[str] = None,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    """List all sessions for this company, with optional filters."""
    company_id = get_company_id(current_user)

    query = {"company_id": company_id}
    if status:
        query["status"] = status
    if purpose:
        query["purpose"] = purpose
    if person_id:
        query["person_id"] = person_id

    sessions = await db.assessment_sessions.find(query).to_list(None)
    # Remove MongoDB _id from response
    for s in sessions:
        s.pop("_id", None)
    return sessions


@router.get("/sessions/my")
async def get_my_sessions(
    current_user: dict = Depends(RequireRole(UserRole.employee))
):
    """Employee views only their own assigned sessions."""
    person_id = current_user.get("id")
    company_id = get_company_id(current_user)

    sessions = await db.assessment_sessions.find({
        "person_id": person_id,
        "company_id": company_id
    }).to_list(None)

    for s in sessions:
        s.pop("_id", None)
    return sessions


@router.get("/sessions/{session_id}")
async def get_assessment_session(
    session_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    """Get a single session detail."""
    company_id = get_company_id(current_user)

    session = await db.assessment_sessions.find_one({
        "id": session_id,
        "company_id": company_id
    })
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.pop("_id", None)
    return session


@router.patch("/sessions/{session_id}/status")
async def update_session_status(
    session_id: str,
    body: StatusTransitionRequest,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    """
    Trigger a validated state transition.
    State machine enforces that no state can be skipped.
    """
    company_id = get_company_id(current_user)

    updated = await transition_session_status(
        session_id=session_id,
        new_status=body.new_status,
        company_id=company_id,
        override_reason=body.override_reason,
        reviewer_id=current_user.get("id")
    )

    # Update reviewer_notes if provided
    if body.reviewer_notes:
        await db.assessment_sessions.update_one(
            {"id": session_id},
            {"$set": {"reviewer_notes": body.reviewer_notes}}
        )
        updated["reviewer_notes"] = body.reviewer_notes

    # Trigger notification when session becomes in_progress
    if body.new_status == "in_progress":
        await notify_employee(
            person_id=updated.get("person_id"),
            session_id=session_id,
            notification_type="assessment_assigned"
        )

    updated.pop("_id", None)
    return updated


# ==================== PHASE 2: EVIDENCE INPUT EXPANSION ====================


@router.post("/sessions/{session_id}/evidence/upload")
async def employee_upload_evidence(
    session_id: str,
    file: UploadFile = File(...),
    evidence_type: str = Form(...),
    current_user: dict = Depends(RequireRole(UserRole.employee))
):
    """
    Employee uploads evidence to their own assessment session.
    Restricted to employee-allowed types only.
    Session must be in_progress.
    """
    person_id = current_user.get("id")
    company_id = get_company_id(current_user)

    # Validate session belongs to this employee
    session = await db.assessment_sessions.find_one({
        "id": session_id,
        "person_id": person_id,
        "company_id": company_id
    })
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate session status
    if session.get("status") != "in_progress":
        raise HTTPException(
            status_code=400,
            detail="Evidence can only be uploaded to sessions that are in progress"
        )

    # Enforce ownership — block HR-only types
    if evidence_type in HR_ONLY_EVIDENCE_TYPES:
        raise HTTPException(
            status_code=403,
            detail=f"Evidence type '{evidence_type}' can only be uploaded by HR"
        )

    if evidence_type not in EMPLOYEE_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid evidence type '{evidence_type}'. Allowed: {EMPLOYEE_ALLOWED_TYPES}"
        )

    # Parse file content
    content = await file.read()
    parsed_text = parse_file_content(content, file.filename)
    if not parsed_text:
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    now = datetime.now(timezone.utc).isoformat()

    evidence_entry = {
        "evidence_type": evidence_type,
        "file_name": file.filename,
        "content": parsed_text,
        "uploaded_by": "employee",
        "uploaded_by_id": person_id,
        "uploaded_at": now,
        "source": "self_upload"
    }

    await db.assessment_sessions.update_one(
        {"id": session_id},
        {
            "$push": {"session_evidence": evidence_entry},
            "$set": {"updated_at": now}
        }
    )

    return {
        "status": "uploaded",
        "session_id": session_id,
        "evidence_type": evidence_type,
        "file_name": file.filename,
        "source": "self_upload"
    }


@router.post("/sessions/{session_id}/evidence/hr-upload")
async def hr_upload_evidence(
    session_id: str,
    file: UploadFile = File(...),
    evidence_type: str = Form(...),
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    """
    HR Admin uploads evidence to any assessment session in their company.
    Can upload all types including HR-only (psychotest, knowledge_test, supplementary_notes).
    """
    company_id = get_company_id(current_user)

    session = await db.assessment_sessions.find_one({
        "id": session_id,
        "company_id": company_id
    })
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("status") not in ["in_progress", "pending"]:
        raise HTTPException(
            status_code=400,
            detail="Evidence can only be uploaded to sessions that are pending or in progress"
        )

    if evidence_type not in VALID_EVIDENCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid evidence type '{evidence_type}'. Allowed: {VALID_EVIDENCE_TYPES}"
        )

    # Parse file content
    content = await file.read()
    parsed_text = parse_file_content(content, file.filename)
    if not parsed_text:
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    now = datetime.now(timezone.utc).isoformat()

    evidence_entry = {
        "evidence_type": evidence_type,
        "file_name": file.filename,
        "content": parsed_text,
        "uploaded_by": "hr",
        "uploaded_by_id": current_user.get("id"),
        "uploaded_at": now,
        "source": "hr_upload"
    }

    await db.assessment_sessions.update_one(
        {"id": session_id},
        {
            "$push": {"session_evidence": evidence_entry},
            "$set": {"updated_at": now}
        }
    )

    return {
        "status": "uploaded",
        "session_id": session_id,
        "evidence_type": evidence_type,
        "file_name": file.filename,
        "source": "hr_upload"
    }


@router.get("/sessions/{session_id}/profile")
async def get_competency_profile(
    session_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    """
    Retrieve competency profile for an assessment session.
    Includes gap analysis per competency.
    """
    company_id = get_company_id(current_user)
    
    # Verify session belongs to company
    session = await db.assessment_sessions.find_one({
        "id": session_id,
        "company_id": company_id
    })
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    profile = await db.competency_profiles.find_one({
        "session_id": session_id,
        "company_id": company_id
    }, {"_id": 0})
    
    if not profile:
        raise HTTPException(status_code=404, detail="Competency profile not found for this session")
        
    return profile


# ==================== PHASE 2 TASK 6: PROMOTION FLOW & BATCH ASSESSMENT ====================

@router.post("/batches")
async def create_assessment_batch(
    batch_data: AssessmentBatchCreate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    batch_data.company_id = company_id
    
    # Validate position exists
    pos = await db.positions.find_one({"id": batch_data.target_position_id, "company_id": company_id})
    if not pos:
        raise HTTPException(status_code=400, detail="Target position not found")
        
    batch = AssessmentBatch(**batch_data.model_dump(), created_by=current_user.get("id"))
    await db.assessment_batches.insert_one(batch.model_dump())
    
    return batch.model_dump(exclude={"_id"})

@router.get("/batches")
async def list_assessment_batches(
    status: Optional[str] = None,
    purpose: Optional[str] = None,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    company_id = get_company_id(current_user)
    query = {"company_id": company_id}
    if status:
        query["status"] = status
    if purpose:
        query["purpose"] = purpose
        
    cursor = db.assessment_batches.find(query)
    batches = []
    async for b in cursor:
        b.pop("_id", None)
        b["candidate_count"] = len(b.get("session_ids", []))
        batches.append(b)
    return batches

@router.get("/batches/{batch_id}")
async def get_assessment_batch(
    batch_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    company_id = get_company_id(current_user)
    batch = await db.assessment_batches.find_one({"id": batch_id, "company_id": company_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    batch.pop("_id", None)
    
    # Get all sessions
    session_ids = batch.get("session_ids", [])
    if session_ids:
        cursor = db.assessment_sessions.find({"id": {"$in": session_ids}})
        sessions = [s async for s in cursor]
        for s in sessions:
            s.pop("_id", None)
        batch["sessions"] = sessions
    else:
        batch["sessions"] = []
        
    return batch

class BatchStatusUpdate(BaseModel):
    status: BatchStatus

@router.patch("/batches/{batch_id}/status")
async def update_batch_status(
    batch_id: str,
    status_update: BatchStatusUpdate,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    batch = await db.assessment_batches.find_one({"id": batch_id, "company_id": company_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    current_status = batch.get("status")
    new_status = status_update.status
    
    # Valid transitions
    valid = False
    if current_status == BatchStatus.open and new_status == BatchStatus.in_progress: valid = True
    elif current_status == BatchStatus.in_progress and new_status == BatchStatus.closed: valid = True
    elif current_status == BatchStatus.closed and new_status == BatchStatus.decided: valid = True
    
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid batch transition: {current_status} -> {new_status}")
        
    now = datetime.now(timezone.utc).isoformat()
    update_data = {"status": new_status, "updated_at": now}
    
    if new_status == BatchStatus.closed:
        update_data["closed_at"] = now
    elif new_status == BatchStatus.decided:
        update_data["decided_at"] = now
        
    await db.assessment_batches.update_one({"id": batch_id}, {"$set": update_data})
    return {"status": "success", "new_status": new_status}

class CandidateEnrollment(BaseModel):
    person_ids: List[str]

@router.post("/batches/{batch_id}/candidates")
async def add_candidates_to_batch(
    batch_id: str,
    enrollment: CandidateEnrollment,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    batch = await db.assessment_batches.find_one({"id": batch_id, "company_id": company_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    if batch.get("status") not in [BatchStatus.open, BatchStatus.in_progress]:
        raise HTTPException(status_code=400, detail="Cannot add candidates to closed or decided batch")
        
    new_sessions = []
    new_session_ids = []
    now = datetime.now(timezone.utc).isoformat()
    
    for pid in enrollment.person_ids:
        # Validate person exists
        person = await db.employees.find_one({"id": pid, "company_id": company_id})
        if not person:
            # Maybe it's a candidate (for hiring)
            person = await db.candidates.find_one({"id": pid, "company_id": company_id})
            if not person:
                continue # Skip invalid
                
        # Create session
        sess = AssessmentSession(
            company_id=company_id,
            person_id=pid,
            target_position_id=batch.get("target_position_id"),
            batch_id=batch_id,
            purpose=batch.get("purpose"),
            status=AssessmentStatus.pending,
            created_at=now
        )
        sess_dict = sess.model_dump()
        new_sessions.append(sess_dict)
        new_session_ids.append(sess.id)
        
    if new_sessions:
        await db.assessment_sessions.insert_many(new_sessions)
        await db.assessment_batches.update_one(
            {"id": batch_id},
            {"$push": {"session_ids": {"$each": new_session_ids}}}
        )
        
    for s in new_sessions:
        s.pop("_id", None)
    return {"added": len(new_sessions), "sessions": new_sessions}

@router.get("/batches/{batch_id}/comparison")
async def get_batch_comparison(
    batch_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    company_id = get_company_id(current_user)
    batch = await db.assessment_batches.find_one({"id": batch_id, "company_id": company_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    pos = await db.positions.find_one({"id": batch.get("target_position_id")})
    if not pos:
        raise HTTPException(status_code=500, detail="Target position not found")
        
    pos.pop("_id", None)
    
    # get sessions that are pending_review or final
    session_ids = batch.get("session_ids", [])
    if not session_ids:
        return {"batch_id": batch_id, "target_position": pos, "candidates": []}
        
    cursor = db.assessment_sessions.find({
        "id": {"$in": session_ids},
        "status": {"$in": ["pending_review", "approved", "overridden"]}
    })
    
    candidates = []
    async for s in cursor:
        profile = await db.competency_profiles.find_one({"session_id": s.get("id")})
        
        person = await db.employees.find_one({"id": s.get("person_id")})
        if not person:
            person = await db.candidates.find_one({"id": s.get("person_id")})
            
        if not person or not profile:
            continue
            
        scores = profile.get("competency_scores", [])
        overall_score = sum(c.get("score_normalized", 0) for c in scores) / len(scores) if scores else 0
        meets_count = sum(1 for c in scores if c.get("meets_standard"))
        
        candidates.append({
            "person_id": person.get("id"),
            "name": person.get("name"),
            "current_position": person.get("current_position", ""),
            "session_id": s.get("id"),
            "session_status": s.get("status"),
            "overall_score": round(float(overall_score), 2) if overall_score else 0.0,
            "meets_standard_count": meets_count,
            "total_competencies": len(scores),
            "ai_recommendation": s.get("ai_recommendation"),
            "ai_confidence": s.get("ai_confidence", "high"), # Set based on rules in complete
            "competency_scores": scores,
            "note": "Rekomendasi AI berdasarkan competency assessment. Keputusan final ada di tangan reviewer."
        })
        
    # Sort by overall score desc
    candidates.sort(key=lambda x: x["overall_score"], reverse=True)
    
    return {
        "batch_id": batch_id,
        "target_position": pos,
        "candidates": candidates
    }

# --- Individual Session Actions ---

@router.post("/sessions/{session_id}/analyze-evidence")
async def analyze_session_evidence(
    session_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    session = await db.assessment_sessions.find_one({"id": session_id, "company_id": company_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.get("status") != "in_progress":
        raise HTTPException(status_code=400, detail="Session must be in progress")
        
    evidence = session.get("session_evidence", [])
    if not evidence:
        raise HTTPException(status_code=400, detail="No evidence uploaded for this session")
        
    user_id = current_user.get("id")
    await check_user_credits(user_id, 1)
    
    # Mock analysis since Task 1 Tahap 2 is not completed for full prompt
    # and we proved abstraction works
    await deduct_credits(user_id, "evidence_analysis", 1000, 0.01, "mock")
    
    mock_result = {
        "category_scores": [
            {"competency_id": "leadership", "score": 85},
            {"competency_id": "communication", "score": 90}
        ]
    }
    
    await db.assessment_sessions.update_one(
        {"id": session_id},
        {"$set": {"evidence_result": mock_result}}
    )
    
    return {"status": "success", "message": "Evidence analyzed"}

class AssignRoleplayReq(BaseModel):
    rubric_id: Optional[str] = None

@router.post("/sessions/{session_id}/assign-roleplay")
async def assign_session_roleplay(
    session_id: str,
    req: AssignRoleplayReq,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    session = await db.assessment_sessions.find_one({"id": session_id, "company_id": company_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    user_id = current_user.get("id")
    await check_user_credits(user_id, 3) 
    
    # Mock roleplay creation
    roleplay_session_id = str(uuid.uuid4())
    session_url = f"https://roleplay.aikrut.id/session/{roleplay_session_id}"
    
    await db.assessment_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "roleplay_session_id": roleplay_session_id,
            "roleplay_session_url": session_url
        }}
    )
    
    await deduct_credits(user_id, "roleplay_session", 3000, 0.03, "mock")
    return {"session_url": session_url, "roleplay_session_id": roleplay_session_id}

@router.get("/sessions/{session_id}/roleplay-result")
async def get_session_roleplay_result(
    session_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    session = await db.assessment_sessions.find_one({"id": session_id, "company_id": company_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Mock result fetching
    mock_result = {
        "overall_score_percent": 75,
        "competency_metrics": [
            {"competency_id": "leadership", "score_percent": 80, "score_1_to_5": 4},
            {"competency_id": "communication", "score_percent": 70, "score_1_to_5": 3}
        ]
    }
    
    await db.assessment_sessions.update_one(
        {"id": session_id},
        {"$set": {"roleplay_result": mock_result}}
    )
    
    return mock_result

class SessionCompleteReq(BaseModel):
    skip_roleplay: bool = False
    skip_reason: Optional[str] = None

@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    req: SessionCompleteReq,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin))
):
    company_id = get_company_id(current_user)
    session = await db.assessment_sessions.find_one({"id": session_id, "company_id": company_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if not session.get("evidence_result"):
        raise HTTPException(status_code=400, detail="Evidence analysis must be complete first")
        
    if not req.skip_roleplay and not session.get("roleplay_result"):
        raise HTTPException(status_code=400, detail="Roleplay result missing. Provide skip=True to override.")
        
    if req.skip_roleplay and not req.skip_reason:
        raise HTTPException(status_code=400, detail="skip_reason is required when skipping roleplay")
        
    # Compute recommendation
    from backend.services.scoring import compute_overall_recommendation, compute_competency_profile
    
    # This will generate profile temporarily, but session isn't completed yet
    # We let transition handle the permanent generation so logic is centralized
    temp_profile = await compute_competency_profile(session_id, company_id)
    purpose = session.get("purpose", "promotion")
    rec_result = compute_overall_recommendation(temp_profile, purpose=purpose)
    
    await db.assessment_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "ai_recommendation": rec_result["recommendation"],
            "ai_confidence": rec_result["confidence"]
        }}
    )
    
    new_session = await transition_session_status(session_id, "completed", company_id)
    return new_session

class SessionReviewReq(BaseModel):
    decision: str
    final_outcome: str
    reviewer_notes: str
    override_reason: Optional[str] = None

@router.post("/sessions/{session_id}/review")
async def review_session(
    session_id: str,
    req: SessionReviewReq,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    company_id = get_company_id(current_user)
    
    session = await db.assessment_sessions.find_one({"id": session_id, "company_id": company_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    purpose = session.get("purpose", "promotion")
    if purpose == "promotion":
        if req.final_outcome not in ["promoted", "not_yet", "no"]:
            raise HTTPException(status_code=400, detail=f"Invalid final_outcome '{req.final_outcome}' for promotion purpose")
    elif purpose == "hiring":
        if req.final_outcome not in ["hired", "not_yet", "no"]:
            raise HTTPException(status_code=400, detail=f"Invalid final_outcome '{req.final_outcome}' for hiring purpose")
            
    # Store outcome info first before validating transition so the validator 
    # has access to the newly requested outcome info
    await db.assessment_sessions.update_one(
        {"id": session_id, "company_id": company_id},
        {"$set": {
            "final_outcome": req.final_outcome,
            "reviewer_notes": req.reviewer_notes
        }}
    )
    
    # Trigger transition
    new_sess = await transition_session_status(
        session_id=session_id,
        new_status=req.decision,
        company_id=company_id,
        override_reason=req.override_reason,
        reviewer_id=current_user.get("id")
    )
    
    # Sanitize and return
    new_sess.pop("_id", None)
    return new_sess

@router.get("/sessions/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    current_user: dict = Depends(RequireRole(UserRole.hr_admin, UserRole.manager))
):
    company_id = get_company_id(current_user)
    session = await db.assessment_sessions.find_one({"id": session_id, "company_id": company_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.pop("_id", None)
    
    profile = await db.competency_profiles.find_one({"session_id": session_id})
    if profile:
        profile.pop("_id", None)
        
    person = await db.employees.find_one({"id": session.get("person_id")})
    if not person:
        person = await db.candidates.find_one({"id": session.get("person_id")})
        
    if person:
        person.pop("_id", None)
        
    pos = await db.positions.find_one({"id": session.get("target_position_id")})
    if pos:
        pos.pop("_id", None)
        
    return {
        "session": session,
        "person": person,
        "target_position": pos,
        "competency_profile": profile,
        "note": "Rekomendasi AI berdasarkan competency assessment. Keputusan final ada di tangan reviewer." if session.get("ai_recommendation") else None
    }

