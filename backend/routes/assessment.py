
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


