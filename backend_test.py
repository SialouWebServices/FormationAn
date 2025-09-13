#!/usr/bin/env python3
"""
RIAN Learning Platform Backend API Tests
Tests all backend endpoints comprehensively
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Backend URL from environment
BACKEND_URL = "https://alphanum-learn.preview.emergentagent.com/api"

class RIANBackendTester:
    def __init__(self):
        self.session = None
        self.session_token = None
        self.user_data = None
        self.competences = []
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: any = None):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        if response_data and not success:
            print(f"   Response: {response_data}")
        print()
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    async def test_init_data(self):
        """Test 1: Data Initialization - /api/init-data"""
        print("🧪 Testing Data Initialization...")
        
        try:
            async with self.session.post(f"{BACKEND_URL}/init-data") as response:
                data = await response.json()
                
                if response.status == 200:
                    if "competences" in data.get("message", "").lower():
                        self.log_test("Data Initialization", True, f"Successfully initialized RIAN curriculum data: {data['message']}")
                    else:
                        self.log_test("Data Initialization", True, f"Data already exists: {data['message']}")
                else:
                    self.log_test("Data Initialization", False, f"HTTP {response.status}", data)
                    
        except Exception as e:
            self.log_test("Data Initialization", False, f"Exception: {str(e)}")
    
    async def test_competences_api(self):
        """Test 2: Competences Management API"""
        print("🧪 Testing Competences API...")
        
        # Test get all competences
        try:
            async with self.session.get(f"{BACKEND_URL}/competences") as response:
                if response.status == 200:
                    competences = await response.json()
                    self.competences = competences
                    
                    if len(competences) == 10:
                        # Verify RIAN curriculum structure
                        comp_titles = [c.get("title", "") for c in competences]
                        expected_keywords = ["familiariser", "Communiquer", "santé", "numérique", "Planifier", "Animer", "Évaluer", "entrepreneuriale", "emploi", "intégrer"]
                        
                        found_keywords = sum(1 for keyword in expected_keywords if any(keyword.lower() in title.lower() for title in comp_titles))
                        
                        if found_keywords >= 8:  # Allow some flexibility
                            total_hours = sum(c.get("duration_hours", 0) for c in competences)
                            if total_hours == 720:
                                self.log_test("Get All Competences", True, f"Found {len(competences)} competences with correct 720h total duration")
                            else:
                                self.log_test("Get All Competences", False, f"Total duration {total_hours}h != 720h expected")
                        else:
                            self.log_test("Get All Competences", False, f"RIAN curriculum structure not matching - found {found_keywords}/10 expected keywords")
                    else:
                        self.log_test("Get All Competences", False, f"Expected 10 competences, got {len(competences)}")
                else:
                    data = await response.json()
                    self.log_test("Get All Competences", False, f"HTTP {response.status}", data)
                    
        except Exception as e:
            self.log_test("Get All Competences", False, f"Exception: {str(e)}")
        
        # Test get individual competence
        if self.competences:
            try:
                first_comp = self.competences[0]
                comp_id = first_comp.get("id")
                
                async with self.session.get(f"{BACKEND_URL}/competences/{comp_id}") as response:
                    if response.status == 200:
                        competence = await response.json()
                        required_fields = ["id", "title", "description", "duration_hours", "learning_objectives", "evaluation_method"]
                        
                        if all(field in competence for field in required_fields):
                            self.log_test("Get Individual Competence", True, f"Retrieved competence '{competence['title']}'")
                        else:
                            missing = [f for f in required_fields if f not in competence]
                            self.log_test("Get Individual Competence", False, f"Missing fields: {missing}")
                    else:
                        data = await response.json()
                        self.log_test("Get Individual Competence", False, f"HTTP {response.status}", data)
                        
            except Exception as e:
                self.log_test("Get Individual Competence", False, f"Exception: {str(e)}")
    
    async def test_auth_endpoints(self):
        """Test 3: Authentication Flow (without actual OAuth)"""
        print("🧪 Testing Authentication Endpoints...")
        
        # Test /auth/me without authentication
        try:
            async with self.session.get(f"{BACKEND_URL}/auth/me") as response:
                if response.status == 401:
                    self.log_test("Auth Me (Unauthenticated)", True, "Correctly returns 401 for unauthenticated request")
                else:
                    data = await response.json()
                    self.log_test("Auth Me (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                    
        except Exception as e:
            self.log_test("Auth Me (Unauthenticated)", False, f"Exception: {str(e)}")
        
        # Test process-session with invalid session
        try:
            invalid_session_data = {"session_id": "invalid_session_123"}
            async with self.session.post(f"{BACKEND_URL}/auth/process-session", json=invalid_session_data) as response:
                if response.status == 400:
                    self.log_test("Process Session (Invalid)", True, "Correctly rejects invalid session ID")
                else:
                    data = await response.json()
                    self.log_test("Process Session (Invalid)", False, f"Expected 400, got {response.status}", data)
                    
        except Exception as e:
            self.log_test("Process Session (Invalid)", False, f"Exception: {str(e)}")
        
        # Test logout without session
        try:
            async with self.session.post(f"{BACKEND_URL}/auth/logout") as response:
                if response.status == 200:
                    data = await response.json()
                    if "logged out" in data.get("message", "").lower():
                        self.log_test("Logout (No Session)", True, "Handles logout without session gracefully")
                    else:
                        self.log_test("Logout (No Session)", False, f"Unexpected response: {data}")
                else:
                    data = await response.json()
                    self.log_test("Logout (No Session)", False, f"HTTP {response.status}", data)
                    
        except Exception as e:
            self.log_test("Logout (No Session)", False, f"Exception: {str(e)}")
    
    async def test_progress_endpoints(self):
        """Test 4: User Progress Tracking (requires auth)"""
        print("🧪 Testing Progress Endpoints...")
        
        # Test get progress without auth
        try:
            async with self.session.get(f"{BACKEND_URL}/progress") as response:
                if response.status == 401:
                    self.log_test("Get Progress (Unauthenticated)", True, "Correctly requires authentication")
                else:
                    data = await response.json()
                    self.log_test("Get Progress (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                    
        except Exception as e:
            self.log_test("Get Progress (Unauthenticated)", False, f"Exception: {str(e)}")
        
        # Test start competence without auth
        if self.competences:
            try:
                comp_id = self.competences[0].get("id")
                async with self.session.post(f"{BACKEND_URL}/progress/start/{comp_id}") as response:
                    if response.status == 401:
                        self.log_test("Start Competence (Unauthenticated)", True, "Correctly requires authentication")
                    else:
                        data = await response.json()
                        self.log_test("Start Competence (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                        
            except Exception as e:
                self.log_test("Start Competence (Unauthenticated)", False, f"Exception: {str(e)}")
    
    async def test_quiz_endpoints(self):
        """Test 5: Quiz System"""
        print("🧪 Testing Quiz System...")
        
        # Test get quiz questions without auth
        if self.competences:
            try:
                comp_id = self.competences[0].get("id")
                async with self.session.get(f"{BACKEND_URL}/quiz/{comp_id}/questions") as response:
                    if response.status == 401:
                        self.log_test("Get Quiz Questions (Unauthenticated)", True, "Correctly requires authentication")
                    else:
                        data = await response.json()
                        self.log_test("Get Quiz Questions (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                        
            except Exception as e:
                self.log_test("Get Quiz Questions (Unauthenticated)", False, f"Exception: {str(e)}")
        
        # Test submit quiz without auth
        if self.competences:
            try:
                comp_id = self.competences[0].get("id")
                answers = [1, 0, 2]  # Sample answers
                async with self.session.post(f"{BACKEND_URL}/quiz/{comp_id}/submit", json=answers) as response:
                    if response.status == 401:
                        self.log_test("Submit Quiz (Unauthenticated)", True, "Correctly requires authentication")
                    else:
                        data = await response.json()
                        self.log_test("Submit Quiz (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                        
            except Exception as e:
                self.log_test("Submit Quiz (Unauthenticated)", False, f"Exception: {str(e)}")
    
    async def test_ai_workshop_endpoints(self):
        """Test 6: AI Workshop Integration"""
        print("🧪 Testing AI Workshop...")
        
        # Test start workshop without auth
        if self.competences:
            try:
                comp_id = self.competences[0].get("id")
                async with self.session.post(f"{BACKEND_URL}/workshop/start/{comp_id}") as response:
                    if response.status == 401:
                        self.log_test("Start AI Workshop (Unauthenticated)", True, "Correctly requires authentication")
                    else:
                        data = await response.json()
                        self.log_test("Start AI Workshop (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                        
            except Exception as e:
                self.log_test("Start AI Workshop (Unauthenticated)", False, f"Exception: {str(e)}")
        
        # Test chat without auth
        try:
            session_id = "test_session_123"
            message = "Bonjour, pouvez-vous m'aider?"
            async with self.session.post(f"{BACKEND_URL}/workshop/{session_id}/chat", params={"message": message}) as response:
                if response.status == 401:
                    self.log_test("AI Workshop Chat (Unauthenticated)", True, "Correctly requires authentication")
                else:
                    data = await response.json()
                    self.log_test("AI Workshop Chat (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                    
        except Exception as e:
            self.log_test("AI Workshop Chat (Unauthenticated)", False, f"Exception: {str(e)}")
    
    async def test_dashboard_endpoint(self):
        """Test 7: Dashboard Analytics"""
        print("🧪 Testing Dashboard...")
        
        # Test dashboard without auth
        try:
            async with self.session.get(f"{BACKEND_URL}/dashboard") as response:
                if response.status == 401:
                    self.log_test("Dashboard (Unauthenticated)", True, "Correctly requires authentication")
                else:
                    data = await response.json()
                    self.log_test("Dashboard (Unauthenticated)", False, f"Expected 401, got {response.status}", data)
                    
        except Exception as e:
            self.log_test("Dashboard (Unauthenticated)", False, f"Exception: {str(e)}")
    
    async def test_api_structure(self):
        """Test API structure and CORS"""
        print("🧪 Testing API Structure...")
        
        # Test CORS headers
        try:
            async with self.session.options(f"{BACKEND_URL}/competences") as response:
                cors_headers = response.headers
                if "Access-Control-Allow-Origin" in cors_headers:
                    self.log_test("CORS Configuration", True, "CORS headers present")
                else:
                    self.log_test("CORS Configuration", False, "Missing CORS headers")
                    
        except Exception as e:
            self.log_test("CORS Configuration", False, f"Exception: {str(e)}")
        
        # Test 404 handling
        try:
            async with self.session.get(f"{BACKEND_URL}/nonexistent-endpoint") as response:
                if response.status == 404:
                    self.log_test("404 Handling", True, "Correctly returns 404 for non-existent endpoints")
                else:
                    self.log_test("404 Handling", False, f"Expected 404, got {response.status}")
                    
        except Exception as e:
            self.log_test("404 Handling", False, f"Exception: {str(e)}")
    
    async def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting RIAN Learning Platform Backend Tests")
        print(f"🔗 Backend URL: {BACKEND_URL}")
        print("=" * 60)
        
        # Run tests in order
        await self.test_init_data()
        await self.test_competences_api()
        await self.test_auth_endpoints()
        await self.test_progress_endpoints()
        await self.test_quiz_endpoints()
        await self.test_ai_workshop_endpoints()
        await self.test_dashboard_endpoint()
        await self.test_api_structure()
        
        # Summary
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   ❌ {result['test']}: {result['details']}")
        
        print("\n" + "=" * 60)
        return passed_tests, failed_tests

async def main():
    """Main test runner"""
    async with RIANBackendTester() as tester:
        passed, failed = await tester.run_all_tests()
        
        # Exit with appropriate code
        if failed > 0:
            print(f"\n⚠️  {failed} test(s) failed. Check the issues above.")
            sys.exit(1)
        else:
            print(f"\n🎉 All {passed} tests passed!")
            sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())