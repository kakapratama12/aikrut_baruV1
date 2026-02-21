"""
Backend API Tests for Bug Fixes - Iteration 2
Testing:
1. ObjectId serialization in analysis endpoints
2. Bulk delete analysis results
3. Check duplicates endpoint
4. Analysis endpoints returning proper JSON
"""

import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8000')

# Test credentials
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test123"

# Test data from main agent context
TEST_COMPANY_ID = "9d99af96-14f0-4067-822b-6aa8b69fed66"
TEST_JOB_ID = "6c444042-8563-404a-870e-e4fe4de4c7a8"
TEST_CANDIDATE_1_ID = "1cd921fd-f86c-41d1-a4f8-86c6997884ad"  # John Developer
TEST_CANDIDATE_2_ID = "9abc294e-ff3a-491f-a2ab-b183a6820a68"  # Jane Coder


class TestAuthAndSetup:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"✓ Login successful for {TEST_EMAIL}")


class TestAnalysisEndpoints:
    """Test analysis endpoints for ObjectId serialization bug fix"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_get_job_analyses_no_objectid_error(self, auth_headers):
        """
        Test /api/analysis/job/{job_id} endpoint
        Should NOT throw 'ObjectId is not JSON serializable' error
        """
        response = requests.get(
            f"{BASE_URL}/api/analysis/job/{TEST_JOB_ID}",
            headers=auth_headers
        )
        
        # Should return 200 or 404 (if job not found), NOT 500
        assert response.status_code != 500, f"Server error (possible ObjectId serialization issue): {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list), "Response should be a list"
            print(f"✓ GET /api/analysis/job/{TEST_JOB_ID} returned {len(data)} results without ObjectId error")
            
            # Verify each result is properly serialized
            for result in data:
                assert "id" in result, "Result should have 'id' field"
                assert "job_id" in result, "Result should have 'job_id' field"
                assert "candidate_id" in result, "Result should have 'candidate_id' field"
                # Check no _id field (MongoDB ObjectId)
                assert "_id" not in result, "Result should NOT have '_id' field (ObjectId)"
        elif response.status_code == 404:
            print(f"✓ Job not found (404) - endpoint working correctly")
        else:
            print(f"Response status: {response.status_code}")
    
    def test_analysis_run_stream_endpoint_exists(self, auth_headers):
        """
        Test /api/analysis/run-stream endpoint exists and accepts requests
        Note: Actual AI analysis will fail due to no API key - that's expected
        """
        response = requests.post(
            f"{BASE_URL}/api/analysis/run-stream",
            headers=auth_headers,
            json={"job_id": TEST_JOB_ID, "candidate_ids": [TEST_CANDIDATE_1_ID]},
            stream=True
        )
        
        # Should NOT return 500 with ObjectId error
        # Expected: 200 (streaming), 400 (no playbook), or 404 (job not found)
        assert response.status_code != 500 or "ObjectId" not in response.text, \
            f"ObjectId serialization error detected: {response.text}"
        
        print(f"✓ POST /api/analysis/run-stream returned status {response.status_code}")
        
        # If streaming, read some data
        if response.status_code == 200:
            content = ""
            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                if chunk:
                    content += chunk
                    # Check for ObjectId error in stream
                    assert "ObjectId" not in content, f"ObjectId error in stream: {content}"
                    if len(content) > 500:  # Read enough to verify
                        break
            print(f"✓ Stream content received without ObjectId errors")
    
    def test_bulk_delete_endpoint(self, auth_headers):
        """
        Test /api/analysis/bulk-delete endpoint
        """
        # First, get existing analyses
        response = requests.get(
            f"{BASE_URL}/api/analysis/job/{TEST_JOB_ID}",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            analyses = response.json()
            if len(analyses) > 0:
                # Try to delete with empty list (should return 400)
                response = requests.post(
                    f"{BASE_URL}/api/analysis/bulk-delete",
                    headers=auth_headers,
                    json={"ids": []}
                )
                assert response.status_code == 400, "Empty ids should return 400"
                print("✓ Bulk delete with empty ids returns 400 as expected")
                
                # Try with non-existent IDs (should succeed with 0 deleted)
                response = requests.post(
                    f"{BASE_URL}/api/analysis/bulk-delete",
                    headers=auth_headers,
                    json={"ids": ["non-existent-id-1", "non-existent-id-2"]}
                )
                assert response.status_code == 200, f"Bulk delete failed: {response.text}"
                data = response.json()
                assert "message" in data
                print(f"✓ Bulk delete endpoint working: {data['message']}")
            else:
                print("✓ No analyses to test bulk delete with")
        else:
            print(f"✓ Could not get analyses (status {response.status_code}), skipping bulk delete test")


class TestCandidateEndpoints:
    """Test candidate endpoints including duplicate check"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_check_duplicates_endpoint(self, auth_headers):
        """
        Test /api/candidates/check-duplicates endpoint
        """
        # Test with empty list
        response = requests.post(
            f"{BASE_URL}/api/candidates/check-duplicates",
            headers=auth_headers,
            json=[]
        )
        assert response.status_code == 200, f"Check duplicates failed: {response.text}"
        data = response.json()
        assert "duplicates" in data
        assert isinstance(data["duplicates"], list)
        print("✓ Check duplicates with empty list works")
        
        # Test with some emails
        response = requests.post(
            f"{BASE_URL}/api/candidates/check-duplicates",
            headers=auth_headers,
            json=["test@example.com", "john@developer.com"]
        )
        assert response.status_code == 200, f"Check duplicates failed: {response.text}"
        data = response.json()
        assert "duplicates" in data
        print(f"✓ Check duplicates returned {len(data['duplicates'])} matches")
    
    def test_list_candidates(self, auth_headers):
        """Test listing candidates"""
        response = requests.get(
            f"{BASE_URL}/api/candidates",
            headers=auth_headers
        )
        assert response.status_code == 200, f"List candidates failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} candidates")
        
        # Verify no ObjectId in response
        for candidate in data:
            assert "_id" not in candidate, "Candidate should not have _id field"
    
    def test_search_candidates(self, auth_headers):
        """Test candidate search endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/candidates/search",
            headers=auth_headers,
            params={"q": "", "page": 1, "limit": 10}
        )
        assert response.status_code == 200, f"Search candidates failed: {response.text}"
        data = response.json()
        assert "candidates" in data
        assert "total" in data
        assert "pages" in data
        print(f"✓ Search returned {data['total']} total candidates")


class TestJobEndpoints:
    """Test job endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_list_jobs(self, auth_headers):
        """Test listing jobs"""
        response = requests.get(
            f"{BASE_URL}/api/jobs",
            headers=auth_headers
        )
        assert response.status_code == 200, f"List jobs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} jobs")
        
        # Verify no ObjectId in response
        for job in data:
            assert "_id" not in job, "Job should not have _id field"
    
    def test_get_specific_job(self, auth_headers):
        """Test getting specific job"""
        response = requests.get(
            f"{BASE_URL}/api/jobs/{TEST_JOB_ID}",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "_id" not in data, "Job should not have _id field"
            assert "id" in data
            assert "playbook" in data
            print(f"✓ Got job: {data.get('title', 'Unknown')}")
        elif response.status_code == 404:
            print("✓ Job not found (404) - endpoint working")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}")


class TestSerializationIntegrity:
    """Test that all endpoints properly serialize MongoDB documents"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_company_endpoint_serialization(self, auth_headers):
        """Test company endpoint returns properly serialized data"""
        response = requests.get(
            f"{BASE_URL}/api/company",
            headers=auth_headers
        )
        
        if response.status_code == 200 and response.json():
            data = response.json()
            assert "_id" not in data, "Company should not have _id field"
            print("✓ Company endpoint properly serialized")
        else:
            print("✓ No company data (null response is valid)")
    
    def test_settings_endpoint_serialization(self, auth_headers):
        """Test settings endpoint returns properly serialized data"""
        response = requests.get(
            f"{BASE_URL}/api/settings",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Settings failed: {response.text}"
        data = response.json()
        assert "_id" not in data, "Settings should not have _id field"
        print("✓ Settings endpoint properly serialized")
    
    def test_dashboard_stats_serialization(self, auth_headers):
        """Test dashboard stats endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        assert "_id" not in data, "Dashboard stats should not have _id field"
        print(f"✓ Dashboard stats: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
