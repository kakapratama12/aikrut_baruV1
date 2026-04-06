from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone

from backend.config import db
from backend.auth.dependencies import get_current_user, get_company_id, RequireRole
from backend.models.user import UserRole
from backend.models.employee import Employee, EmployeeCreate, EmployeeUpdate, EmployeeBulkCreate, EmployeeBulkResponse

router = APIRouter()

@router.post("")
async def create_employee(
    employee: EmployeeCreate,
    company_id: str = Depends(get_company_id),
    current_user: dict = Depends(RequireRole([UserRole.hr_admin]))
):
    """Create a new employee. If email already exists for this company, return the existing record instead of throwing an error."""
    # Force company_id to match token
    employee.company_id = company_id
    
    # Check for duplicate by email + company_id
    existing_employee = await db.employees.find_one({
        "email": employee.email,
        "company_id": company_id
    }, {"_id": 0})
    
    if existing_employee:
        return existing_employee
        
    new_employee = Employee(
        **employee.model_dump(),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat()
    )
    
    await db.employees.insert_one(new_employee.model_dump())
    return new_employee.model_dump()

@router.post("/bulk")
async def bulk_create_employees(
    bulk_req: EmployeeBulkCreate,
    company_id: str = Depends(get_company_id),
    current_user: dict = Depends(RequireRole([UserRole.hr_admin]))
):
    """Bulk input employees. Used heavily for hiring external candidates."""
    created_list = []
    existing_list = []
    
    for emp_data in bulk_req.employees:
        emp_data.company_id = company_id
        
        existing = await db.employees.find_one({
            "email": emp_data.email,
            "company_id": company_id
        }, {"_id": 0})
        
        if existing:
            existing_list.append(existing)
        else:
            new_employee = Employee(
                **emp_data.model_dump(),
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat()
            )
            created_list.append(new_employee.model_dump())
            
    if created_list:
        await db.employees.insert_many(created_list)
        
    return {
        "created": created_list,
        "existing": existing_list,
        "total": len(created_list) + len(existing_list)
    }

@router.get("")
async def list_employees(
    company_id: str = Depends(get_company_id),
    current_user: dict = Depends(get_current_user)
):
    """List all employees within a company"""
    employees = await db.employees.find({"company_id": company_id}, {"_id": 0}).to_list(length=None)
    return employees

@router.get("/{employee_id}")
async def get_employee(
    employee_id: str,
    company_id: str = Depends(get_company_id),
    current_user: dict = Depends(get_current_user)
):
    employee = await db.employees.find_one({"id": employee_id, "company_id": company_id}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.patch("/{employee_id}")
async def update_employee(
    employee_id: str,
    update_data: EmployeeUpdate,
    company_id: str = Depends(get_company_id),
    current_user: dict = Depends(RequireRole([UserRole.hr_admin]))
):
    employee = await db.employees.find_one({"id": employee_id, "company_id": company_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    
    if update_dict:
        # If email is updated, make sure it doesn't conflict
        if "email" in update_dict and update_dict["email"] != employee.get("email"):
            existing_email = await db.employees.find_one({
                "email": update_dict["email"], 
                "company_id": company_id, 
                "id": {"$ne": employee_id}
            })
            if existing_email:
                raise HTTPException(status_code=400, detail="Another employee with this email already exists")

        update_data_to_save = {}
        for k, v in update_dict.items():
            update_data_to_save[str(k)] = v
        
        update_data_to_save["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.employees.update_one(
            {"id": employee_id, "company_id": company_id},
            {"$set": update_data_to_save}
        )
        
    updated_employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    return updated_employee

@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: str,
    company_id: str = Depends(get_company_id),
    current_user: dict = Depends(RequireRole([UserRole.hr_admin]))
):
    # Verify employee exists
    employee = await db.employees.find_one({"id": employee_id, "company_id": company_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # DELETE guard: Prevent deletion if employee has linked assessment sessions
    linked_session = await db.assessment_sessions.find_one({
        "person_id": employee_id, 
        "company_id": company_id
    })
    
    if linked_session:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete employee with existing assessment sessions. Please review or archive their sessions first."
        )
        
    await db.employees.delete_one({"id": employee_id, "company_id": company_id})
    return {"message": "Employee deleted successfully"}
