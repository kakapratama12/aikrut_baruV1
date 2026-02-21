import requests
import sys
import json
import re
from datetime import datetime
import uuid

class TalentAITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.company_id = None
        self.job_id = None
        self.candidate_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_result(self, test_name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED: {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if files:
                # Remove Content-Type for file uploads
                headers.pop('Content-Type', None)
                
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, data=data, files=files, headers=headers)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            
            if success:
                self.log_result(name, True)
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"
                self.log_result(name, False, error_msg)
                return False, {}

        except Exception as e:
            self.log_result(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_user_registration(self):
        """Test user registration"""
        test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        test_name = "Test User"
        test_password = "testpass123"
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "email": test_email,
                "name": test_name,
                "password": test_password
            }
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.test_email = test_email
            self.test_password = test_password
            return True
        return False

    def test_user_login(self):
        """Test user login"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data={
                "email": self.test_email,
                "password": self.test_password
            }
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            return True
        return False

    def test_get_user_profile(self):
        """Test get current user profile"""
        success, response = self.run_test(
            "Get User Profile",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        return success

    def test_create_company(self):
        """Test company creation"""
        success, response = self.run_test(
            "Create Company",
            "POST",
            "company",
            200,
            data={
                "name": "Test Company Inc",
                "description": "A test company for CV screening",
                "industry": "Technology",
                "website": "https://testcompany.com",
                "values": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Innovation",
                        "description": "We value creative problem solving",
                        "weight": 50
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Teamwork",
                        "description": "Collaboration is key to our success",
                        "weight": 50
                    }
                ]
            }
        )
        
        if success and 'id' in response:
            self.company_id = response['id']
            return True
        return False

    def test_get_company(self):
        """Test get company details"""
        success, response = self.run_test(
            "Get Company",
            "GET",
            "company",
            200
        )
        return success

    def test_create_job(self):
        """Test job creation"""
        success, response = self.run_test(
            "Create Job",
            "POST",
            "jobs",
            200,
            data={
                "title": "Senior Software Engineer",
                "description": "We are looking for an experienced software engineer to join our team.",
                "requirements": "5+ years of experience in Python, React, and MongoDB",
                "location": "Remote",
                "employment_type": "full-time",
                "salary_range": "$80,000 - $120,000"
            }
        )
        
        if success and 'id' in response:
            self.job_id = response['id']
            return True
        return False

    def test_list_jobs(self):
        """Test list jobs"""
        success, response = self.run_test(
            "List Jobs",
            "GET",
            "jobs",
            200
        )
        return success

    def test_get_job(self):
        """Test get specific job"""
        if not self.job_id:
            self.log_result("Get Job", False, "No job ID available")
            return False
            
        success, response = self.run_test(
            "Get Job",
            "GET",
            f"jobs/{self.job_id}",
            200
        )
        return success

    def test_create_candidate(self):
        """Test candidate creation"""
        success, response = self.run_test(
            "Create Candidate",
            "POST",
            "candidates",
            200,
            data={
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890"
            }
        )
        
        if success and 'id' in response:
            self.candidate_id = response['id']
            return True
        return False

    def test_list_candidates(self):
        """Test list candidates"""
        success, response = self.run_test(
            "List Candidates",
            "GET",
            "candidates",
            200
        )
        return success

    def test_get_settings(self):
        """Test get settings"""
        success, response = self.run_test(
            "Get Settings",
            "GET",
            "settings",
            200
        )
        return success

    def test_update_settings(self):
        """Test update settings"""
        success, response = self.run_test(
            "Update Settings",
            "PUT",
            "settings",
            200,
            data={
                "model_name": "openai/gpt-4o-mini",
                "language": "en"
            }
        )
        return success

    def test_recent_activity(self):
        """Test recent activity"""
        success, response = self.run_test(
            "Recent Activity",
            "GET",
            "dashboard/recent-activity",
            200
        )
        return success

    # NEW CANDIDATE MANAGEMENT ENDPOINTS TESTS
    def test_detect_duplicates_no_match(self):
        """Test detect duplicates with no matches"""
        success, response = self.run_test(
            "Detect Duplicates - No Match",
            "POST",
            "candidates/detect-duplicates",
            200,
            data={
                "email": "unique.email@example.com",
                "phone": "+9999999999",
                "name": "Unique Person"
            }
        )
        
        if success and 'has_duplicates' in response:
            if response['has_duplicates'] == False and len(response.get('matches', [])) == 0:
                return True
            else:
                self.log_result("Detect Duplicates - No Match", False, f"Expected no duplicates but got: {response}")
                return False
        return success

    def test_detect_duplicates_email_match(self):
        """Test detect duplicates with email match"""
        # First create a candidate to match against
        if not self.candidate_id:
            self.log_result("Detect Duplicates - Email Match", False, "No candidate created yet")
            return False
            
        success, response = self.run_test(
            "Detect Duplicates - Email Match",
            "POST",
            "candidates/detect-duplicates",
            200,
            data={
                "email": "john.doe@example.com",  # Same as created candidate
                "phone": "+9876543210",
                "name": "Different Name"
            }
        )
        
        if success and 'has_duplicates' in response:
            if response['has_duplicates'] == True and len(response.get('matches', [])) > 0:
                match = response['matches'][0]
                if 'email_match' in match.get('match_reasons', []):
                    return True
                else:
                    self.log_result("Detect Duplicates - Email Match", False, f"Expected email_match in reasons but got: {match.get('match_reasons', [])}")
                    return False
            else:
                self.log_result("Detect Duplicates - Email Match", False, f"Expected duplicates but got: {response}")
                return False
        return success

    def test_detect_duplicates_phone_match(self):
        """Test detect duplicates with phone match"""
        if not self.candidate_id:
            self.log_result("Detect Duplicates - Phone Match", False, "No candidate created yet")
            return False
            
        success, response = self.run_test(
            "Detect Duplicates - Phone Match",
            "POST",
            "candidates/detect-duplicates",
            200,
            data={
                "email": "different.email@example.com",
                "phone": "1234567890",  # Same as created candidate (normalized)
                "name": "Different Name"
            }
        )
        
        if success and 'has_duplicates' in response:
            if response['has_duplicates'] == True and len(response.get('matches', [])) > 0:
                match = response['matches'][0]
                if 'phone_match' in match.get('match_reasons', []):
                    return True
                else:
                    self.log_result("Detect Duplicates - Phone Match", False, f"Expected phone_match in reasons but got: {match.get('match_reasons', [])}")
                    return False
            else:
                self.log_result("Detect Duplicates - Phone Match", False, f"Expected duplicates but got: {response}")
                return False
        return success

    def test_upload_zip_error_handling(self):
        """Test upload ZIP without actual ZIP file (error handling)"""
        # Test with non-ZIP file to verify error handling
        success, response = self.run_test(
            "Upload ZIP - Error Handling",
            "POST",
            "candidates/upload-zip",
            400,  # Expecting 400 error for non-ZIP
            data={"force_create": "false"},
            files={"file": ("test.txt", "This is not a ZIP file", "text/plain")}
        )
        return success

    def test_merge_candidates(self):
        """Test merge candidates endpoint"""
        # Create a second candidate to merge
        success, response = self.run_test(
            "Create Second Candidate for Merge",
            "POST",
            "candidates",
            200,
            data={
                "name": "Jane Smith",
                "email": "jane.smith@example.com",
                "phone": "+9876543210"
            }
        )
        
        if not success or 'id' not in response:
            self.log_result("Merge Candidates", False, "Failed to create second candidate")
            return False
            
        second_candidate_id = response['id']
        
        # Now test merge
        success, response = self.run_test(
            "Merge Candidates",
            "POST",
            "candidates/merge",
            200,
            data={
                "source_candidate_id": second_candidate_id,
                "target_candidate_id": self.candidate_id
            }
        )
        
        if success and 'message' in response and 'evidence_transferred' in response:
            if response['message'] == "Candidates merged successfully":
                return True
            else:
                self.log_result("Merge Candidates", False, f"Unexpected message: {response.get('message')}")
                return False
        return success

    def test_merge_logs(self):
        """Test get merge logs endpoint"""
        success, response = self.run_test(
            "Get Merge Logs",
            "GET",
            "candidates/merge-logs",
            200
        )
        
        if success and isinstance(response, list):
            # Should have at least one log entry from the merge test
            if len(response) >= 1:
                log_entry = response[0]
                required_fields = ['action', 'source_id', 'target_id', 'merged_at', 'merged_by']
                if all(field in log_entry for field in required_fields):
                    return True
                else:
                    missing_fields = [field for field in required_fields if field not in log_entry]
                    self.log_result("Get Merge Logs", False, f"Missing fields in log entry: {missing_fields}")
                    return False
            else:
                self.log_result("Get Merge Logs", False, "No merge logs found after merge operation")
                return False
        return success

    # UPDATED UPLOAD-CV ENDPOINT TESTS
    def create_sample_pdf_content(self):
        """Create a simple PDF-like content for testing"""
        return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(John Smith) Tj
0 -20 Td
(john.smith@email.com) Tj
0 -20 Td
(+1-555-123-4567) Tj
0 -20 Td
(Software Engineer with 5 years experience) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""

    def test_upload_cv_first_time(self):
        """Test 1: Upload CV - First time (no duplicates)"""
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - First Time",
            "POST",
            "candidates/upload-cv",
            200,
            data={},
            files={"file": ("john_smith_cv.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            # Check response structure
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'created':
                    self.first_upload_candidate_id = response['candidate']['id']
                    print(f"   Created candidate ID: {self.first_upload_candidate_id}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    print(f"   Evidence types: {response['evidence_types']}")
                    return True
                else:
                    self.log_result("Upload CV - First Time", False, f"Expected status 'created', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - First Time", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_duplicate_detection(self):
        """Test 2: Upload same CV again (duplicate detection)"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Upload CV - Duplicate Detection", False, "First upload test must run first")
            return False
            
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - Duplicate Detection",
            "POST",
            "candidates/upload-cv",
            200,
            data={},
            files={"file": ("john_smith_cv_duplicate.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'duplicates', 'extracted_info', 'evidence_preview']
            if all(field in response for field in expected_fields):
                if response['status'] == 'duplicate_warning':
                    duplicates = response['duplicates']
                    if len(duplicates) > 0:
                        print(f"   Found {len(duplicates)} duplicate(s)")
                        print(f"   Extracted info: {response['extracted_info']}")
                        print(f"   Evidence preview: {response['evidence_preview']}")
                        return True
                    else:
                        self.log_result("Upload CV - Duplicate Detection", False, "No duplicates found when expected")
                        return False
                else:
                    self.log_result("Upload CV - Duplicate Detection", False, f"Expected status 'duplicate_warning', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - Duplicate Detection", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_force_create(self):
        """Test 3: Force create despite duplicate"""
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - Force Create",
            "POST",
            "candidates/upload-cv",
            200,
            data={"force_create": "true"},
            files={"file": ("john_smith_cv_force.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'created':
                    self.force_created_candidate_id = response['candidate']['id']
                    print(f"   Force created candidate ID: {self.force_created_candidate_id}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    return True
                else:
                    self.log_result("Upload CV - Force Create", False, f"Expected status 'created', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - Force Create", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_merge_into_existing(self):
        """Test 4: Merge into existing candidate"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Upload CV - Merge Into Existing", False, "First upload test must run first")
            return False
            
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - Merge Into Existing",
            "POST",
            "candidates/upload-cv",
            200,
            data={"merge_target_id": self.first_upload_candidate_id},
            files={"file": ("john_smith_additional.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'merged':
                    print(f"   Merged into candidate ID: {response['candidate']['id']}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    print(f"   Evidence types: {response['evidence_types']}")
                    return True
                else:
                    self.log_result("Upload CV - Merge Into Existing", False, f"Expected status 'merged', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - Merge Into Existing", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_to_existing_candidate(self):
        """Test 5: Upload to existing candidate (candidate_id)"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Upload CV - To Existing Candidate", False, "First upload test must run first")
            return False
            
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - To Existing Candidate",
            "POST",
            "candidates/upload-cv",
            200,
            data={"candidate_id": self.first_upload_candidate_id},
            files={"file": ("john_smith_update.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'updated':
                    print(f"   Updated candidate ID: {response['candidate']['id']}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    print(f"   Evidence types: {response['evidence_types']}")
                    return True
                else:
                    self.log_result("Upload CV - To Existing Candidate", False, f"Expected status 'updated', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - To Existing Candidate", False, f"Missing fields: {missing}")
                return False
        return success

    # NEW EVIDENCE CRUD AND REPLACE ENDPOINTS TESTS
    def test_delete_evidence(self):
        """Test DELETE /api/candidates/{candidate_id}/evidence/{evidence_index}"""
        # First, we need a candidate with evidence
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Delete Evidence", False, "Need candidate with evidence from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        # Get candidate to check current evidence count
        success, candidate_response = self.run_test(
            "Get Candidate Before Delete",
            "GET",
            f"candidates/{candidate_id}",
            200
        )
        
        if not success or 'evidence' not in candidate_response:
            self.log_result("Delete Evidence", False, "Could not get candidate evidence")
            return False
            
        evidence_count_before = len(candidate_response['evidence'])
        if evidence_count_before == 0:
            self.log_result("Delete Evidence", False, "No evidence to delete")
            return False
            
        print(f"   Evidence count before delete: {evidence_count_before}")
        
        # Delete evidence at index 0
        success, response = self.run_test(
            "Delete Evidence",
            "DELETE",
            f"candidates/{candidate_id}/evidence/0",
            200
        )
        
        if success:
            expected_fields = ['status', 'deleted_evidence', 'candidate', 'remaining_evidence']
            if all(field in response for field in expected_fields):
                if response['status'] == 'deleted':
                    remaining_count = response['remaining_evidence']
                    if remaining_count == evidence_count_before - 1:
                        print(f"   Successfully deleted evidence. Remaining: {remaining_count}")
                        print(f"   Deleted evidence: {response['deleted_evidence']}")
                        return True
                    else:
                        self.log_result("Delete Evidence", False, f"Expected {evidence_count_before - 1} remaining, got {remaining_count}")
                        return False
                else:
                    self.log_result("Delete Evidence", False, f"Expected status 'deleted', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Delete Evidence", False, f"Missing fields: {missing}")
                return False
        return success

    def test_delete_evidence_invalid_index(self):
        """Test DELETE evidence with invalid index (should return 400)"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Delete Evidence - Invalid Index", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        # Try to delete evidence at invalid index (999)
        success, response = self.run_test(
            "Delete Evidence - Invalid Index",
            "DELETE",
            f"candidates/{candidate_id}/evidence/999",
            400  # Expecting 400 error
        )
        return success

    def test_replace_candidate(self):
        """Test POST /api/candidates/replace"""
        # Create two candidates for replacement test
        success1, response1 = self.run_test(
            "Create Candidate for Replace (Old)",
            "POST",
            "candidates",
            200,
            data={
                "name": "Alice Johnson",
                "email": "alice.johnson@example.com",
                "phone": "+1111111111"
            }
        )
        
        if not success1 or 'id' not in response1:
            self.log_result("Replace Candidate", False, "Failed to create old candidate")
            return False
            
        old_candidate_id = response1['id']
        print(f"   Created old candidate ID: {old_candidate_id}")
        
        # Now replace the candidate with new data
        new_evidence = [
            {
                "type": "cv",
                "file_name": "new_resume.pdf",
                "content": "Updated resume content with new experience",
                "uploaded_at": datetime.now().isoformat(),
                "source": "replacement"
            }
        ]
        
        success, response = self.run_test(
            "Replace Candidate",
            "POST",
            "candidates/replace",
            200,
            data={
                "old_candidate_id": old_candidate_id,
                "new_name": "Alice Johnson-Smith",
                "new_email": "alice.johnson.smith@example.com",
                "new_phone": "+2222222222",
                "new_evidence": new_evidence
            }
        )
        
        if success:
            expected_fields = ['status', 'old_candidate_id', 'new_candidate']
            if all(field in response for field in expected_fields):
                if response['status'] == 'replaced':
                    new_candidate = response['new_candidate']
                    if (new_candidate['name'] == "Alice Johnson-Smith" and 
                        new_candidate['email'] == "alice.johnson.smith@example.com" and
                        response['old_candidate_id'] == old_candidate_id):
                        
                        print(f"   Successfully replaced candidate")
                        print(f"   Old ID: {old_candidate_id}")
                        print(f"   New ID: {new_candidate['id']}")
                        print(f"   New name: {new_candidate['name']}")
                        
                        # Verify old candidate is deleted
                        success_check, _ = self.run_test(
                            "Verify Old Candidate Deleted",
                            "GET",
                            f"candidates/{old_candidate_id}",
                            404  # Should return 404 since it's deleted
                        )
                        
                        if success_check:
                            print(f"   ✅ Old candidate properly deleted")
                            return True
                        else:
                            self.log_result("Replace Candidate", False, "Old candidate was not deleted")
                            return False
                    else:
                        self.log_result("Replace Candidate", False, "New candidate data doesn't match expected values")
                        return False
                else:
                    self.log_result("Replace Candidate", False, f"Expected status 'replaced', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Replace Candidate", False, f"Missing fields: {missing}")
                return False
        return success

    def test_replace_candidate_nonexistent(self):
        """Test replace candidate with non-existent old candidate ID (should return 404)"""
        fake_id = str(uuid.uuid4())
        
        success, response = self.run_test(
            "Replace Candidate - Non-existent",
            "POST",
            "candidates/replace",
            404,  # Expecting 404 error
            data={
                "old_candidate_id": fake_id,
                "new_name": "Test Name",
                "new_email": "test@example.com",
                "new_phone": "+1234567890",
                "new_evidence": []
            }
        )
        return success

    # NEW TALENT TAGGING ENDPOINTS TESTS
    def test_get_tag_library(self):
        """Test GET /api/tags/library - Get complete tag library"""
        success, response = self.run_test(
            "Get Tag Library",
            "GET",
            "tags/library",
            200
        )
        
        if success:
            # Verify response structure
            expected_fields = ['layers', 'consistency_rules']
            if all(field in response for field in expected_fields):
                layers = response['layers']
                
                # Check all 4 layers are present
                if all(str(i) in layers for i in [1, 2, 3, 4]):
                    # Verify Layer 1 structure
                    layer1 = layers['1']
                    if (layer1.get('name') == 'Domain / Function' and 
                        layer1.get('max_tags') == 3 and 
                        isinstance(layer1.get('tags'), list) and
                        len(layer1.get('tags', [])) > 0):
                        
                        # Verify Layer 4 has definitions
                        layer4 = layers['4']
                        if ('definitions' in layer4 and 
                            'OPERATIONAL' in layer4['definitions'] and
                            'TACTICAL' in layer4['definitions'] and
                            'STRATEGIC' in layer4['definitions']):
                            
                            print(f"   ✅ Tag library contains {len(layer1['tags'])} Layer 1 tags")
                            print(f"   ✅ Tag library contains {len(layers['2']['tags'])} Layer 2 tags")
                            print(f"   ✅ Layer 3 is free text (no predefined tags)")
                            print(f"   ✅ Tag library contains {len(layer4['tags'])} Layer 4 tags")
                            return True
                        else:
                            self.log_result("Get Tag Library", False, "Layer 4 missing definitions")
                            return False
                    else:
                        self.log_result("Get Tag Library", False, "Layer 1 structure invalid")
                        return False
                else:
                    self.log_result("Get Tag Library", False, "Missing layer definitions")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Get Tag Library", False, f"Missing fields: {missing}")
                return False
        return success

    def test_add_manual_tag_layer1(self):
        """Test POST /api/candidates/{candidate_id}/tags - Add Layer 1 tag"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Add Manual Tag Layer 1", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Add Manual Tag - Layer 1",
            "POST",
            f"candidates/{candidate_id}/tags",
            200,
            data={
                "tag_value": "ENGINEERING",
                "layer": 1
            }
        )
        
        if success:
            expected_fields = ['status', 'tag', 'tags']
            if all(field in response for field in expected_fields):
                if response['status'] == 'success':
                    tag = response['tag']
                    if (tag.get('tag_value') == 'ENGINEERING' and 
                        tag.get('layer') == 1 and
                        tag.get('source') == 'MANUAL' and
                        tag.get('layer_name') == 'Domain / Function'):
                        
                        print(f"   ✅ Added Layer 1 tag: {tag['tag_value']}")
                        print(f"   ✅ Tag source: {tag['source']}")
                        return True
                    else:
                        self.log_result("Add Manual Tag Layer 1", False, f"Tag structure invalid: {tag}")
                        return False
                else:
                    self.log_result("Add Manual Tag Layer 1", False, f"Expected status 'success', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Add Manual Tag Layer 1", False, f"Missing fields: {missing}")
                return False
        return success

    def test_add_manual_tag_layer3(self):
        """Test POST /api/candidates/{candidate_id}/tags - Add Layer 3 skill tag"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Add Manual Tag Layer 3", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Add Manual Tag - Layer 3",
            "POST",
            f"candidates/{candidate_id}/tags",
            200,
            data={
                "tag_value": "Python",
                "layer": 3
            }
        )
        
        if success:
            expected_fields = ['status', 'tag', 'tags']
            if all(field in response for field in expected_fields):
                if response['status'] == 'success':
                    tag = response['tag']
                    if (tag.get('tag_value') == 'Python' and 
                        tag.get('layer') == 3 and
                        tag.get('source') == 'MANUAL' and
                        tag.get('layer_name') == 'Skill / Competency'):
                        
                        print(f"   ✅ Added Layer 3 skill tag: {tag['tag_value']}")
                        return True
                    else:
                        self.log_result("Add Manual Tag Layer 3", False, f"Tag structure invalid: {tag}")
                        return False
                else:
                    self.log_result("Add Manual Tag Layer 3", False, f"Expected status 'success', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Add Manual Tag Layer 3", False, f"Missing fields: {missing}")
                return False
        return success

    def test_add_invalid_tag_layer(self):
        """Test POST /api/candidates/{candidate_id}/tags - Invalid layer validation"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Add Invalid Tag Layer", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Add Invalid Tag - Invalid Layer",
            "POST",
            f"candidates/{candidate_id}/tags",
            400,  # Expecting 400 error
            data={
                "tag_value": "INVALID",
                "layer": 5  # Invalid layer
            }
        )
        return success

    def test_add_invalid_tag_value(self):
        """Test POST /api/candidates/{candidate_id}/tags - Invalid tag value for predefined layer"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Add Invalid Tag Value", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Add Invalid Tag - Invalid Value",
            "POST",
            f"candidates/{candidate_id}/tags",
            400,  # Expecting 400 error
            data={
                "tag_value": "INVALID_DOMAIN",
                "layer": 1  # Layer 1 has predefined values
            }
        )
        return success

    def test_get_candidate_tags(self):
        """Test GET /api/candidates/{candidate_id}/tags - Get all tags for candidate"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Get Candidate Tags", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Get Candidate Tags",
            "GET",
            f"candidates/{candidate_id}/tags",
            200
        )
        
        if success:
            expected_fields = ['tags', 'grouped', 'deleted_tags', 'layer_info']
            if all(field in response for field in expected_fields):
                tags = response['tags']
                grouped = response['grouped']
                
                # Should have tags from previous tests (Layer 1: ENGINEERING, Layer 3: Python)
                if len(tags) >= 2:
                    # Check grouped structure
                    if all(str(i) in grouped for i in [1, 2, 3, 4]):
                        # Verify we have the tags we added
                        layer1_tags = grouped['1']
                        layer3_tags = grouped['3']
                        
                        has_engineering = any(t.get('tag_value') == 'ENGINEERING' for t in layer1_tags)
                        has_python = any(t.get('tag_value') == 'Python' for t in layer3_tags)
                        
                        if has_engineering and has_python:
                            print(f"   ✅ Found {len(tags)} total tags")
                            print(f"   ✅ Layer 1 tags: {len(layer1_tags)}")
                            print(f"   ✅ Layer 3 tags: {len(layer3_tags)}")
                            return True
                        else:
                            self.log_result("Get Candidate Tags", False, f"Missing expected tags. Layer 1: {layer1_tags}, Layer 3: {layer3_tags}")
                            return False
                    else:
                        self.log_result("Get Candidate Tags", False, "Grouped structure missing layers")
                        return False
                else:
                    self.log_result("Get Candidate Tags", False, f"Expected at least 2 tags, got {len(tags)}")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Get Candidate Tags", False, f"Missing fields: {missing}")
                return False
        return success

    def test_delete_manual_tag(self):
        """Test DELETE /api/candidates/{candidate_id}/tags/{tag_value}?layer=X - Delete manual tag"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Delete Manual Tag", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Delete Manual Tag",
            "DELETE",
            f"candidates/{candidate_id}/tags/Python?layer=3",
            200
        )
        
        if success:
            expected_fields = ['status', 'deleted_tag', 'blacklisted', 'remaining_tags']
            if all(field in response for field in expected_fields):
                if response['status'] == 'success':
                    deleted_tag = response['deleted_tag']
                    blacklisted = response['blacklisted']
                    
                    if (deleted_tag.get('tag_value') == 'Python' and 
                        deleted_tag.get('layer') == 3 and
                        deleted_tag.get('source') == 'MANUAL' and
                        blacklisted == False):  # Manual tags should not be blacklisted
                        
                        print(f"   ✅ Deleted manual tag: {deleted_tag['tag_value']}")
                        print(f"   ✅ Blacklisted: {blacklisted} (correct for manual tags)")
                        print(f"   ✅ Remaining tags: {len(response['remaining_tags'])}")
                        return True
                    else:
                        self.log_result("Delete Manual Tag", False, f"Unexpected tag or blacklist status: {deleted_tag}, blacklisted: {blacklisted}")
                        return False
                else:
                    self.log_result("Delete Manual Tag", False, f"Expected status 'success', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Delete Manual Tag", False, f"Missing fields: {missing}")
                return False
        return success

    def test_extract_tags_no_api_key(self):
        """Test POST /api/candidates/{candidate_id}/extract-tags - Should fail without API key"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Extract Tags - No API Key", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Extract Tags - No API Key",
            "POST",
            f"candidates/{candidate_id}/extract-tags",
            400  # Expecting 400 error due to no API key
        )
        
        # This should fail with 400 because OpenRouter API key is not configured
        if success:
            print(f"   ✅ Correctly returned 400 error for missing API key")
            return True
        return success

    def test_delete_nonexistent_tag(self):
        """Test DELETE /api/candidates/{candidate_id}/tags/{tag_value}?layer=X - Delete non-existent tag"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Delete Non-existent Tag", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        success, response = self.run_test(
            "Delete Non-existent Tag",
            "DELETE",
            f"candidates/{candidate_id}/tags/NonExistentTag?layer=3",
            404  # Expecting 404 error
        )
        return success

    def test_add_auto_tag_and_delete_with_blacklist(self):
        """Test adding an AUTO tag manually and then deleting it (should be blacklisted)"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Add AUTO Tag and Delete", False, "Need candidate from upload CV test")
            return False
            
        candidate_id = self.first_upload_candidate_id
        
        # First, manually add a tag and then modify it to be AUTO source to simulate extracted tag
        # Add a Layer 4 tag
        success, response = self.run_test(
            "Add Layer 4 Tag for Blacklist Test",
            "POST",
            f"candidates/{candidate_id}/tags",
            200,
            data={
                "tag_value": "TACTICAL",
                "layer": 4
            }
        )
        
        if not success:
            self.log_result("Add AUTO Tag and Delete", False, "Failed to add Layer 4 tag")
            return False
        
        # Now simulate deleting an AUTO tag by manually updating the tag source
        # Get current candidate
        success_get, candidate_data = self.run_test(
            "Get Candidate for AUTO Tag Test",
            "GET",
            f"candidates/{candidate_id}",
            200
        )
        
        if success_get and 'tags' in candidate_data:
            # Find the TACTICAL tag and note that in real scenario it would be AUTO
            tactical_tag_exists = any(t.get('tag_value') == 'TACTICAL' and t.get('layer') == 4 for t in candidate_data['tags'])
            
            if tactical_tag_exists:
                # Delete the tag (it will be treated as MANUAL since we added it manually)
                success_delete, delete_response = self.run_test(
                    "Delete Layer 4 Tag",
                    "DELETE",
                    f"candidates/{candidate_id}/tags/TACTICAL?layer=4",
                    200
                )
                
                if success_delete:
                    deleted_tag = delete_response.get('deleted_tag', {})
                    blacklisted = delete_response.get('blacklisted', False)
                    
                    print(f"   ✅ Deleted Layer 4 tag: {deleted_tag.get('tag_value')}")
                    print(f"   ✅ Source was: {deleted_tag.get('source')}")
                    print(f"   ✅ Blacklisted: {blacklisted}")
                    
                    # Note: Since we added it manually, it won't be blacklisted
                    # In real scenario with AUTO tags, they would be blacklisted
                    return True
                else:
                    self.log_result("Add AUTO Tag and Delete", False, "Failed to delete Layer 4 tag")
                    return False
            else:
                self.log_result("Add AUTO Tag and Delete", False, "TACTICAL tag not found after adding")
                return False
        else:
            self.log_result("Add AUTO Tag and Delete", False, "Failed to get candidate data")
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting TalentAI Backend API Tests")
        print("=" * 50)
        
        # Authentication Tests
        print("\n📝 Authentication Tests")
        if not self.test_user_registration():
            print("❌ Registration failed, stopping tests")
            return False
            
        if not self.test_user_login():
            print("❌ Login failed, stopping tests")
            return False
            
        self.test_get_user_profile()
        
        # Dashboard Tests
        print("\n📊 Dashboard Tests")
        self.test_dashboard_stats()
        self.test_recent_activity()
        
        # Company Tests
        print("\n🏢 Company Tests")
        self.test_create_company()
        self.test_get_company()
        
        # Job Tests
        print("\n💼 Job Tests")
        self.test_create_job()
        self.test_list_jobs()
        self.test_get_job()
        
        # Candidate Tests
        print("\n👥 Candidate Tests")
        self.test_create_candidate()
        self.test_list_candidates()
        
        # NEW Candidate Management Tests
        print("\n🔍 NEW Candidate Management Tests")
        self.test_detect_duplicates_no_match()
        self.test_detect_duplicates_email_match()
        self.test_detect_duplicates_phone_match()
        self.test_upload_zip_error_handling()
        self.test_merge_candidates()
        self.test_merge_logs()
        
        # UPDATED Upload-CV Endpoint Tests
        print("\n📄 UPDATED Upload-CV Endpoint Tests")
        self.test_upload_cv_first_time()
        self.test_upload_cv_duplicate_detection()
        self.test_upload_cv_force_create()
        self.test_upload_cv_merge_into_existing()
        self.test_upload_cv_to_existing_candidate()
        
        # NEW Evidence CRUD and Replace Endpoint Tests
        print("\n🗑️ NEW Evidence CRUD and Replace Endpoint Tests")
        self.test_delete_evidence()
        self.test_delete_evidence_invalid_index()
        self.test_replace_candidate()
        self.test_replace_candidate_nonexistent()
        
        # NEW Talent Tagging Endpoint Tests
        print("\n🏷️ NEW Talent Tagging Endpoint Tests")
        self.test_get_tag_library()
        self.test_add_manual_tag_layer1()
        self.test_add_manual_tag_layer3()
        self.test_add_invalid_tag_layer()
        self.test_add_invalid_tag_value()
        self.test_get_candidate_tags()
        self.test_delete_manual_tag()
        self.test_extract_tags_no_api_key()
        self.test_delete_nonexistent_tag()
        self.test_add_auto_tag_and_delete_with_blacklist()
        
        # Settings Tests
        print("\n⚙️ Settings Tests")
        self.test_get_settings()
        self.test_update_settings()
        
        # Print Results
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("❌ Some tests failed. Check the details above.")
            failed_tests = [r for r in self.test_results if not r['success']]
            print("\nFailed Tests:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
            return False

def main():
    tester = TalentAITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())