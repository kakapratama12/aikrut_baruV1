from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr

# Candidate Models
class CandidateEvidence(BaseModel):
    type: str  # cv, psychotest, knowledge_test
    file_name: str
    content: str  # parsed text content
    uploaded_at: str

class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""

class ReplaceCandidate(BaseModel):
    # Same as candidate create, but used for replace logic
    name: str
    email: EmailStr
    phone: Optional[str] = ""

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

# ==================== TALENT TAGGING MODELS & CONSTANTS ====================

# Layer 1: Domain / Function (max 3)
LAYER_1_TAGS = [
    "OPERATIONS", "HUMAN_RESOURCES", "FINANCE", "ACCOUNTING", 
    "INFORMATION_TECHNOLOGY", "DATA_ANALYTICS", "PRODUCT", "ENGINEERING",
    "SALES", "MARKETING", "CUSTOMER_SUPPORT", "LEGAL", 
    "PROCUREMENT", "SUPPLY_CHAIN", "LOGISTICS"
]

# Layer 2: Job Family (max 3)
LAYER_2_TAGS = [
    # Operations & Admin
    "GENERAL_OPERATIONS", "GENERAL_ADMINISTRATION", "HR_OPERATIONS",
    "TALENT_ACQUISITION", "LEARNING_DEVELOPMENT", "PAYROLL_COMPLIANCE",
    "ACCOUNTING_SUPPORT", "FINANCIAL_REPORTING", "FINANCIAL_CONTROL",
    "PROCUREMENT_VENDOR_MANAGEMENT", "LEGAL_COMPLIANCE",
    # Tech
    "SOFTWARE_DEVELOPMENT", "IT_OPERATIONS", "PROJECT_MANAGEMENT",
    "PRODUCT_MANAGEMENT", "QA_TESTING", "DATA_ANALYTICS", "DATA_ENGINEERING",
    "DEVOPS_CLOUD", "UI_UX_DESIGN",
    # Sales & Marketing
    "B2B_SALES", "B2C_SALES", "KEY_ACCOUNT_MANAGEMENT", "DIGITAL_MARKETING",
    "PERFORMANCE_MARKETING", "BRAND_CONTENT", "CUSTOMER_SUPPORT", "CUSTOMER_SUCCESS",
    # Supply Chain & Engineering
    "SUPPLY_CHAIN_MANAGEMENT", "LOGISTICS_OPERATIONS", "NON_IT_ENGINEERING",
    "RESEARCH_DEVELOPMENT"
]

# Layer 4: Scope of Work (max 3)
LAYER_4_TAGS = ["OPERATIONAL", "TACTICAL", "STRATEGIC"]

# Layer definitions with metadata
LAYER_DEFINITIONS = {
    1: {"name": "Domain / Function", "max_tags": 3, "library": LAYER_1_TAGS},
    2: {"name": "Job Family", "max_tags": 3, "library": LAYER_2_TAGS},
    3: {"name": "Skill / Competency", "max_tags": 10, "library": None},  # Free text, AI normalized
    4: {"name": "Scope of Work", "max_tags": 3, "library": LAYER_4_TAGS}
}

# Logical consistency mapping: Layer 1 -> valid Layer 2 tags
LAYER_1_TO_2_MAPPING = {
    "OPERATIONS": ["GENERAL_OPERATIONS", "GENERAL_ADMINISTRATION"],
    "HUMAN_RESOURCES": ["HR_OPERATIONS", "TALENT_ACQUISITION", "LEARNING_DEVELOPMENT", "PAYROLL_COMPLIANCE"],
    "FINANCE": ["FINANCIAL_REPORTING", "FINANCIAL_CONTROL"],
    "ACCOUNTING": ["ACCOUNTING_SUPPORT", "FINANCIAL_REPORTING"],
    "INFORMATION_TECHNOLOGY": ["SOFTWARE_DEVELOPMENT", "IT_OPERATIONS", "DEVOPS_CLOUD", "QA_TESTING"],
    "DATA_ANALYTICS": ["DATA_ANALYTICS", "DATA_ENGINEERING"],
    "PRODUCT": ["PRODUCT_MANAGEMENT", "UI_UX_DESIGN"],
    "ENGINEERING": ["SOFTWARE_DEVELOPMENT", "NON_IT_ENGINEERING", "RESEARCH_DEVELOPMENT", "QA_TESTING"],
    "SALES": ["B2B_SALES", "B2C_SALES", "KEY_ACCOUNT_MANAGEMENT"],
    "MARKETING": ["DIGITAL_MARKETING", "PERFORMANCE_MARKETING", "BRAND_CONTENT"],
    "CUSTOMER_SUPPORT": ["CUSTOMER_SUPPORT", "CUSTOMER_SUCCESS"],
    "LEGAL": ["LEGAL_COMPLIANCE"],
    "PROCUREMENT": ["PROCUREMENT_VENDOR_MANAGEMENT"],
    "SUPPLY_CHAIN": ["SUPPLY_CHAIN_MANAGEMENT"],
    "LOGISTICS": ["LOGISTICS_OPERATIONS"]
}

class CandidateTag(BaseModel):
    tag_value: str
    layer: int  # 1, 2, 3, or 4
    layer_name: str
    source: str  # "AUTO" or "MANUAL"
    confidence_score: Optional[float] = None  # For AUTO tags, 0.0-1.0
    created_at: str

class TagAddRequest(BaseModel):
    tag_value: str
    layer: int

class TagExtractionResponse(BaseModel):
    tags: List[CandidateTag]
    extraction_summary: str
    evidence_used: List[str]

class CandidateResponse(BaseModel):
    id: str
    company_id: str
    name: str
    email: str
    phone: str
    evidence: List[CandidateEvidence]
    tags: Optional[List[CandidateTag]] = []
    deleted_tags: Optional[List[str]] = []  # Blacklisted tag values
    created_at: str
    updated_at: str

# Analysis Models
class ScoreBreakdown(BaseModel):
    item_id: str
    item_name: str
    raw_score: float  # 0-100
    weight: float
    weighted_score: float
    reasoning: str

class CategoryScore(BaseModel):
    category: str  # character, requirement, skill
    score: float
    breakdown: List[ScoreBreakdown]

class AnalysisResult(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    candidate_name: Optional[str] = None  # Store name for when candidate is deleted
    final_score: float
    category_scores: List[CategoryScore]
    overall_reasoning: str
    company_values_alignment: Optional[Dict[str, Any]] = None
    strengths: Optional[List[str]] = []
    gaps: Optional[List[str]] = []
    created_at: str

class BatchAnalysisRequest(BaseModel):
    job_id: str
    candidate_ids: List[str]
