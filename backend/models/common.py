from pydantic import BaseModel
from typing import List, Optional

class BulkDeleteRequest(BaseModel):
    ids: List[str]

class PDFReportRequest(BaseModel):
    include_company_values: bool = True
    include_raw_evidence: bool = False
    language: str = "id"

class DuplicateDetectionRequest(BaseModel):
    candidate_id: str

class DuplicateMatch(BaseModel):
    candidate_id: str
    name: str
    email: str
    similarity_score: float
    matched_fields: List[str]

class DuplicateDetectionResponse(BaseModel):
    is_duplicate: bool
    matches: List[DuplicateMatch]

class MergeRequest(BaseModel):
    source_candidate_id: str
    target_candidate_id: str
    fields_to_merge: List[str]

class MergeLogEntry(BaseModel):
    id: str
    source_candidate_id: str
    target_candidate_id: str
    merged_fields: List[str]
    merged_by: str
    merged_at: str

class ZipUploadResponse(BaseModel):
    job_id: str
    total_files: int
    successful: int
    failed: int
    duplicates: int
    errors: List[str]
