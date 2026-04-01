from enum import Enum
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator

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

class AssessmentStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    pending_review = "pending_review"
    approved = "approved"
    overridden = "overridden"
    request_more_info = "request_more_info"

class BatchStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    closed = "closed"
    decided = "decided"

class AssessmentPurpose(str, Enum):
    promotion = "promotion"
    hiring = "hiring"

class AssessmentBatchCreate(BaseModel):
    company_id: str
    target_position_id: str
    purpose: AssessmentPurpose
    notes: Optional[str] = None

from datetime import datetime, timezone
class AssessmentBatch(AssessmentBatchCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: BatchStatus = BatchStatus.open
    session_ids: List[str] = []
    created_by: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    closed_at: Optional[str] = None
    decided_at: Optional[str] = None

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
    batch_id: Optional[str] = None
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
