import requests
import sys
import json
from datetime import datetime
import time

class MoodSpaceAPITester:
    def __init__(self, base_url="https://mindaid-2.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_id = f"test_user_{datetime.now().strftime('%H%M%S')}"
        self.tests_run = 0
        self.tests_passed = 0
        self.mood_entry_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else f"{self.api_url}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)

            print(f"   Status Code: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    elif isinstance(response_data, list):
                        print(f"   Response: List with {len(response_data)} items")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout (30s)")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test("Root API Endpoint", "GET", "", 200)

    def test_create_mood_entry(self):
        """Test creating a mood entry with AI insights"""
        mood_data = {
            "user_session": self.session_id,
            "mood_score": 7,
            "emotions": ["Happy", "Grateful", "Peaceful"],
            "description": "Had a good day today. Spent time with family and felt really connected. The weather was nice and I managed to complete my work on time."
        }
        
        print("   Note: This test may take 10-15 seconds due to AI processing...")
        success, response = self.run_test(
            "Create Mood Entry with AI Insights",
            "POST",
            "mood",
            200,
            data=mood_data
        )
        
        if success and 'id' in response:
            self.mood_entry_id = response['id']
            print(f"   Mood Entry ID: {self.mood_entry_id}")
            if 'ai_insights' in response and response['ai_insights']:
                print(f"   AI Insights Generated: ✅")
                print(f"   AI Response Preview: {response['ai_insights'][:100]}...")
            else:
                print(f"   AI Insights: ❌ Missing or empty")
        
        return success

    def test_get_user_moods(self):
        """Test retrieving user mood entries"""
        return self.run_test(
            "Get User Mood Entries",
            "GET",
            f"mood/{self.session_id}",
            200
        )

    def test_ai_chat(self):
        """Test AI chat functionality"""
        chat_data = {
            "user_session": self.session_id,
            "message": "I'm feeling a bit overwhelmed with my studies. Can you help me?"
        }
        
        print("   Note: This test may take 10-15 seconds due to AI processing...")
        success, response = self.run_test(
            "AI Chat Companion",
            "POST",
            "chat",
            200,
            data=chat_data
        )
        
        if success and 'response' in response:
            print(f"   AI Response Generated: ✅")
            print(f"   AI Response Preview: {response['response'][:150]}...")
        
        return success

    def test_wellness_challenges(self):
        """Test wellness challenges endpoint"""
        success, response = self.run_test(
            "Get Wellness Challenges",
            "GET",
            "challenges",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Challenges Found: {len(response)}")
            for challenge in response[:2]:  # Show first 2 challenges
                print(f"   - {challenge.get('title', 'Unknown')}: {challenge.get('points', 0)} points")
        
        return success

    def test_user_progress(self):
        """Test user progress tracking"""
        return self.run_test(
            "Get User Progress",
            "GET",
            f"progress/{self.session_id}",
            200
        )

    def test_mood_analytics(self):
        """Test mood analytics with AI pattern analysis"""
        print("   Note: This test may take 10-15 seconds due to AI processing...")
        success, response = self.run_test(
            "Get Mood Analytics",
            "GET",
            f"analytics/{self.session_id}",
            200
        )
        
        if success:
            if 'analysis' in response and response['analysis']:
                print(f"   AI Analysis Generated: ✅")
                print(f"   Analysis Preview: {response['analysis'][:100]}...")
            if 'average_mood' in response:
                print(f"   Average Mood: {response['average_mood']}")
        
        return success

    def test_anonymous_stories(self):
        """Test anonymous story functionality"""
        # Test creating a story
        story_data = {
            "user_session": self.session_id,
            "title": "My Journey with Anxiety",
            "story": "I want to share my experience dealing with anxiety during college. It was challenging but I found ways to cope.",
            "category": "anxiety"
        }
        
        success1, response1 = self.run_test(
            "Create Anonymous Story",
            "POST",
            "stories",
            200,
            data=story_data
        )
        
        # Test getting approved stories
        success2, response2 = self.run_test(
            "Get Approved Stories",
            "GET",
            "stories",
            200
        )
        
        return success1 and success2

def main():
    print("🚀 Starting MoodSpace API Testing...")
    print("=" * 60)
    
    tester = MoodSpaceAPITester()
    
    # Test sequence
    tests = [
        ("Root Endpoint", tester.test_root_endpoint),
        ("Mood Entry Creation", tester.test_create_mood_entry),
        ("User Moods Retrieval", tester.test_get_user_moods),
        ("AI Chat", tester.test_ai_chat),
        ("Wellness Challenges", tester.test_wellness_challenges),
        ("User Progress", tester.test_user_progress),
        ("Mood Analytics", tester.test_mood_analytics),
        ("Anonymous Stories", tester.test_anonymous_stories),
    ]
    
    print(f"Session ID: {tester.session_id}")
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            test_func()
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
        
        # Small delay between tests
        time.sleep(1)
    
    # Print final results
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS")
    print(f"{'='*60}")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed! Backend is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the details above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())