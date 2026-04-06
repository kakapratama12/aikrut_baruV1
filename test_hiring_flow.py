import os, sys, json, asyncio
from datetime import datetime, timezone

# Mock env for testing
os.environ["JWT_SECRET"] = "dummy"
os.environ["ADMIN_JWT_SECRET"] = "dummy"
os.environ["SUPER_ADMIN_PASSWORD"] = "dummy"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config import db
from backend.models.user import UserRole
import uuid

# Mock user dependency
mock_hr = {"id": "hr_001", "role": UserRole.hr_admin, "company_id": "company_001"}

from backend.models.assessment import AssessmentBatchCreate, AssessmentPurpose, BatchStatus, AIRecommendation, FinalOutcome, AssessmentStatus
from backend.routes.employees import bulk_create_employees
from backend.models.employee import EmployeeBulkCreate, EmployeeCreate, EmploymentType
from backend.routes.assessment import (
    create_assessment_batch,
    add_candidates_to_batch,
    update_session_status,
    hr_upload_evidence,
    analyze_session_evidence,
    assign_session_roleplay,
    get_session_roleplay_result,
    complete_session,
    review_session,
    get_batch_comparison,
    StatusTransitionRequest,
    CandidateEnrollment,
    AssignRoleplayReq,
    SessionCompleteReq,
    SessionReviewReq
)

# We mock UploadFile locally for tests
from fastapi import UploadFile
import tempfile

class MockUploadFile:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content
    async def read(self):
        return self.content

async def run_hiring_flow():
    print("=" * 60)
    print("PHASE 2 TASK 7: HIRING FLOW E2E TESTS")
    print("=" * 60)

    company_id = "company_001"
    
    # Pre-setup Clean DB
    await db.assessment_batches.delete_many({"company_id": company_id})
    await db.assessment_sessions.delete_many({"company_id": company_id})
    await db.competency_profiles.delete_many({"company_id": company_id})
    await db.employees.delete_many({"company_id": company_id})
    await db.users.delete_many({"id": "hr_001"})
    
    # Insert HR mock so credit system doesn't crash
    await db.users.insert_one({
        "id": "hr_001",
        "company_id": company_id,
        "role": "hr_admin",
        "credits": 99999.0,
        "is_approved": True,
        "is_active": True
    })

    # Find or create a position for the batch
    target_pos = await db.positions.find_one({"company_id": company_id})
    if not target_pos:
        target_pos = {
            "id": "pos_001",
            "company_id": company_id,
            "title": "Software Engineer",
            "department": "Engineering",
            "level": 3,
            "required_competencies": [
                {
                    "competency_id": "leadership",
                    "standard_minimum": 3,
                    "weight_evidence": 50,
                    "weight_roleplay": 50
                },
                {
                    "competency_id": "communication",
                    "standard_minimum": 4,
                    "weight_evidence": 50,
                    "weight_roleplay": 50
                }
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.positions.insert_one(target_pos)
        
    print("\n[Step 1] POST /api/employees/bulk (External Candidates)...")
    bulk_data = EmployeeBulkCreate(
        employees=[
            EmployeeCreate(
                company_id=company_id,
                name="Alice External",
                email="alice.ext@test.com",
                current_position="",
                employment_type=EmploymentType.external
            ),
            EmployeeCreate(
                company_id=company_id,
                name="Bob External",
                email="bob.ext@test.com",
                current_position="",
                employment_type=EmploymentType.external
            )
        ]
    )
    res_bulk = await bulk_create_employees(bulk_data, company_id=company_id, current_user=mock_hr)
    alice_id = res_bulk["created"][0]["id"]
    bob_id = res_bulk["created"][1]["id"]
    print(f"✅ Created 2 external employees. IDs: {alice_id}, {bob_id}")

    print("\n[Step 2] POST /api/assessment/batches (Purpose: Hiring)...")
    batch_req = AssessmentBatchCreate(
        company_id=company_id,
        target_position_id=target_pos["id"],
        purpose=AssessmentPurpose.hiring
    )
    res_batch = await create_assessment_batch(batch_req, current_user=mock_hr)
    batch_id = res_batch["id"]
    print(f"✅ Batch created with purpose 'hiring'. ID: {batch_id}")
    assert res_batch["purpose"] == "hiring"

    print("\n[Step 3] POST /api/assessment/batches/{id}/candidates ...")
    enroll_req = CandidateEnrollment(person_ids=[alice_id, bob_id])
    res_enroll = await add_candidates_to_batch(batch_id, enroll_req, current_user=mock_hr)
    sessions = res_enroll["sessions"]
    sess_alice = sessions[0]["id"]
    sess_bob = sessions[1]["id"]
    print(f"✅ Created 2 sessions. Purpose from DB: {sessions[0]['purpose']}")
    assert sessions[0]["purpose"] == "hiring"

    print("\n[Step 4] Running Full Engine Flow for sessions...")
    for s_id in [sess_alice, sess_bob]:
        # in_progress
        await update_session_status(s_id, StatusTransitionRequest(new_status="in_progress"), current_user=mock_hr)
        
        # Upload CV
        mock_pdf = MockUploadFile("cv.txt", b"This is a dummy CV for testing competency analysis.")
        await hr_upload_evidence(s_id, mock_pdf, "cv", current_user=mock_hr)
        
        # Analyze
        await analyze_session_evidence(s_id, current_user=mock_hr)
        
        # Roleplay Assign
        await assign_session_roleplay(s_id, AssignRoleplayReq(), current_user=mock_hr)
        
        # RP Fetch Result
        await get_session_roleplay_result(s_id, current_user=mock_hr)
        
        # Complete
        await complete_session(s_id, SessionCompleteReq(), current_user=mock_hr)
        
    print("✅ All sessions completed via engine")

    print("\n[Step 5] GET /api/assessment/batches/{id}/comparison")
    res_comp = await get_batch_comparison(batch_id, current_user=mock_hr)
    candidates = res_comp["candidates"]
    
    # Verifying AI Recommendation string is hire/not_yet, not promote
    for c in candidates:
        ai_rec = c["ai_recommendation"]
        print(f"  -> Candidate {c['name']} AI Rec: {ai_rec}")
        assert ai_rec in ["hire", "not_yet", "no"], f"Failed: Recommendation was {ai_rec}"
        
    print("✅ Comparison View Output Verified.")

    print("\n[Step 6] POST review for Alice: 'hired'")
    res_alice_rev = await review_session(
        sess_alice, 
        SessionReviewReq(decision="approved", final_outcome="hired", reviewer_notes="Looks great"), 
        current_user=mock_hr
    )
    print(f"✅ Alice final outcome: {res_alice_rev['final_outcome']}")
    assert res_alice_rev["final_outcome"] == "hired"

    print("\n[Step 7] POST review for Bob: 'not_yet'")
    res_bob_rev = await review_session(
        sess_bob,
        SessionReviewReq(decision="overridden", final_outcome="not_yet", reviewer_notes="Needs more exp", override_reason="Pengalaman kurang"),
        current_user=mock_hr
    )
    print(f"✅ Bob final outcome: {res_bob_rev['final_outcome']}")
    assert res_bob_rev["final_outcome"] == "not_yet"

    print("\n" + "=" * 60)
    print("ALL 7 HIRING FLOW STEPS PASSED ✅")

if __name__ == "__main__":
    asyncio.run(run_hiring_flow())
