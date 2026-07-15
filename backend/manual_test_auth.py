"""Test authentication flow to debug sign-in issues.

Run this to verify the backend auth system is working.

Usage:
    cd backend
    python test_auth.py
"""

import requests

BASE_URL = "http://localhost:8000"


def test_health():
    """Test if backend is running."""
    print("1. Testing backend health...")
    try:
        resp = requests.get(f"{BASE_URL}/healthz", timeout=5)
        if resp.status_code == 200:
            print("   ✅ Backend is running")
            return True
        else:
            print(f"   ❌ Backend returned status {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect to backend. Is it running on port 8000?")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_mock_idp():
    """Test if mock IdP page is accessible."""
    print("\n2. Testing mock IdP...")
    try:
        resp = requests.get(f"{BASE_URL}/mock-idp/login?returnTo=/", timeout=5)
        if resp.status_code == 200 and "Mock Campus IdP" in resp.text:
            print("   ✅ Mock IdP page is accessible")
            return True
        elif resp.status_code == 404:
            print("   ❌ Mock IdP not found. Is AUTH_PROVIDER=mock set?")
            return False
        else:
            print(f"   ❌ Unexpected response: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_auth_flow():
    """Test complete authentication flow."""
    print("\n3. Testing authentication flow...")
    
    session = requests.Session()
    
    # Step 1: Get login redirect
    print("   Step 1: GET /auth/login")
    resp = session.get(f"{BASE_URL}/auth/login?returnTo=/test", allow_redirects=False)
    if resp.status_code != 302:
        print(f"   ❌ Expected redirect (302), got {resp.status_code}")
        return False
    print(f"   ✅ Redirected to: {resp.headers.get('Location', 'unknown')}")
    
    # Step 2: Post to ACS (simulate IdP callback)
    print("   Step 2: POST /auth/acs (simulating IdP)")
    resp = session.post(
        f"{BASE_URL}/auth/acs",
        data={
            "returnTo": "/test",
            "subject": "test@csub.edu",
            "affiliation": "student",
        },
        allow_redirects=False
    )
    
    if resp.status_code != 302:
        print(f"   ❌ Expected redirect (302), got {resp.status_code}")
        print(f"   Response: {resp.text}")
        return False
    
    # Check if we got a session cookie
    cookies = session.cookies.get_dict()
    if "wp_session" not in cookies:
        print("   ❌ No session cookie set")
        return False
    
    print(f"   ✅ Session cookie set: wp_session={cookies['wp_session'][:20]}...")
    print(f"   ✅ Redirected to: {resp.headers.get('Location', 'unknown')}")
    
    # Step 3: Check session
    print("   Step 3: GET /auth/session")
    resp = session.get(f"{BASE_URL}/auth/session")
    if resp.status_code != 200:
        print(f"   ❌ Failed to get session: {resp.status_code}")
        return False
    
    session_data = resp.json()
    print(f"   ✅ Signed in as: {session_data.get('subject')}")
    print(f"   ✅ Affiliation: {session_data.get('affiliation')}")
    print(f"   ✅ Is current student: {session_data.get('isCurrentStudent')}")
    print(f"   ✅ Student ID: {session_data.get('student_id')}")
    
    return True


def test_database():
    """Test if database is initialized."""
    print("\n4. Testing database...")
    try:
        from app.db import SessionLocal
        from app.models.student import Student
        
        db = SessionLocal()
        try:
            # Try to query students
            count = db.query(Student).count()
            print(f"   ✅ Database is accessible ({count} students)")
            return True
        except Exception as e:
            print(f"   ❌ Database error: {e}")
            print("   💡 Try running: python -c 'from app.db import init_db; init_db()'")
            return False
        finally:
            db.close()
    except ImportError:
        print("   ⚠️  Cannot import app modules. Make sure you're in the backend directory.")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("Authentication System Diagnostic")
    print("=" * 60)
    
    results = []
    
    results.append(("Backend Health", test_health()))
    results.append(("Mock IdP", test_mock_idp()))
    results.append(("Auth Flow", test_auth_flow()))
    results.append(("Database", test_database()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_pass = False
    
    print("\n" + "=" * 60)
    
    if all_pass:
        print("🎉 All tests passed! Auth system is working correctly.")
        print("\nYou should be able to:")
        print("1. Go to http://localhost:5173")
        print("2. Click 'Sign in with campus SSO'")
        print("3. Click 'Student' preset")
        print("4. Click 'Authenticate'")
        print("5. See the signed-in page")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        print("\nCommon fixes:")
        print("1. Make sure backend is running: uvicorn app.main:app --reload --port 8000")
        print("2. Initialize database: python -c 'from app.db import init_db; init_db()'")
        print("3. Check .env file for AUTH_PROVIDER=mock")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
