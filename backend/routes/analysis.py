
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


# ==================== ANALYSIS ROUTES ====================


@router.post("/analysis/run", response_model=List[AnalysisResult])
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

@router.post("/analysis/run-stream")
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

@router.post("/candidates/check-duplicates")
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

@router.get("/analysis/job/{job_id}", response_model=List[AnalysisResult])
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

@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    analysis = await db.analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    # Serialize to ensure no ObjectId
    analysis = serialize_doc(analysis)
    return AnalysisResult(**analysis)

@router.delete("/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.analyses.delete_one({"id": analysis_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Analysis deleted"}



@router.post("/analysis/bulk-delete")
async def bulk_delete_analyses(request: BulkDeleteRequest, current_user: dict = Depends(get_current_user)):
    """Delete multiple analysis results at once"""
    if not request.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")
    
    result = await db.analyses.delete_many({"id": {"$in": request.ids}})
    return {"message": f"Deleted {result.deleted_count} analysis result(s)"}



@router.post("/analysis/generate-pdf")
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

