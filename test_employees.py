import os, sys, json, asyncio
from datetime import datetime, timezone

# Mock env for testing
os.environ["JWT_SECRET"] = "dummy"
os.environ["ADMIN_JWT_SECRET"] = "dummy"
os.environ["SUPER_ADMIN_PASSWORD"] = "dummy"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config import db
from backend.models.employee import EmployeeCreate, EmployeeUpdate, EmploymentType
from backend.routes.employees import create_employee, list_employees, get_employee, update_employee, delete_employee
from backend.models.user import UserRole
import uuid

# Mock user dependency
mock_hr = {"id": "hr_001", "role": UserRole.hr_admin, "company_id": "company_001"}

async def run_tests():
    print("=" * 60)
    print("TESTING EMPLOYEE ENDPOINTS (Task 4.1)")
    print("=" * 60)

    # 0. Setup
    company_id = "company_001"
    await db.employees.delete_many({"company_id": company_id})

    # 1. Create a new employee
    print("\n[Step 1] Creating a new Employee...")
    req_create = EmployeeCreate(
        company_id=company_id,
        name="John Doe",
        email="john.doe@example.com",
        current_position="Software Engineer",
        employment_type=EmploymentType.internal
    )
    res_create = await create_employee(req_create, company_id=company_id, current_user=mock_hr)
    employee_id = res_create["id"]
    print(f"✅ Created Employee {employee_id} - Email: {res_create['email']}")

    # 2. Duplicate Create (Should return existing)
    print("\n[Step 2] Testing duplicate creation by email...")
    res_duplicate = await create_employee(req_create, company_id=company_id, current_user=mock_hr)
    print(f"✅ Returned Existing Employee ID: {res_duplicate['id']}")
    assert res_duplicate["id"] == employee_id

    # 3. List
    print("\n[Step 3] Testing list employees...")
    res_list = await list_employees(company_id=company_id, current_user=mock_hr)
    print(f"✅ Listed {len(res_list)} employees")
    assert len(res_list) == 1

    # 4. Update
    print("\n[Step 4] Testing update employee...")
    req_update = EmployeeUpdate(name="John Doe Updated", current_position="Senior Software Engineer")
    res_update = await update_employee(employee_id, req_update, company_id=company_id, current_user=mock_hr)
    print(f"✅ Updated Employee: Name -> {res_update['name']}, Position -> {res_update['current_position']}")
    assert res_update["name"] == "John Doe Updated"

    # 5. Get Detail
    print("\n[Step 5] Testing get employee detail...")
    res_get = await get_employee(employee_id, company_id=company_id, current_user=mock_hr)
    print(f"✅ Fetched detail: {res_get['name']}")
    assert res_get["id"] == employee_id

    # 6. Delete
    print("\n[Step 6] Testing delete employee...")
    res_del = await delete_employee(employee_id, company_id=company_id, current_user=mock_hr)
    print(f"✅ Delete response: {res_del}")
    
    # 7. List empty
    res_list_end = await list_employees(company_id=company_id, current_user=mock_hr)
    assert len(res_list_end) == 0
    print(f"✅ Final list count: 0")

    print("\n" + "=" * 60)
    print("ALL EMPLOYEE TESTS PASSED ✅")

if __name__ == "__main__":
    asyncio.run(run_tests())
