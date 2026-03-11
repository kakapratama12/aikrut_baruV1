import uuid
from typing import Optional, List, Union, Dict
from pydantic import BaseModel, Field

class PlaybookItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    weight: float  # 0-100, total per category must equal 100

class JobPlaybook(BaseModel):
    character: List[PlaybookItem] = []
    requirement: List[PlaybookItem] = []
    skill: List[PlaybookItem] = []

class JobCreate(BaseModel):
    title: str
    description: Union[dict, str]
    requirements: Union[dict, str]
    location: Optional[str] = ""
    employment_type: Optional[str] = "full-time"
    salary_range: Optional[str] = ""
    playbook: Optional[JobPlaybook] = None

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[Union[dict, str]] = None
    requirements: Optional[Union[dict, str]] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_range: Optional[str] = None
    playbook: Optional[JobPlaybook] = None
    status: Optional[str] = None

class JobResponse(BaseModel):
    id: str
    company_id: str
    title: str
    description: Union[dict, str]
    requirements: Union[dict, str]
    location: str
    employment_type: str
    salary_range: str
    playbook: Optional[JobPlaybook]
    status: str
    created_at: str
    updated_at: str
