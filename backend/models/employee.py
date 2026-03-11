import uuid
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field

class EmploymentType(str, Enum):
    internal = "internal"
    external = "external"

class EmployeeCreate(BaseModel):
    company_id: str
    name: str
    email: str
    current_position: str
    employment_type: EmploymentType = EmploymentType.internal
    status: str = "aktif"

class Employee(EmployeeCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str
    updated_at: str
