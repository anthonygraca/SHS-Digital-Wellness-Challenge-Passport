"""Quick import test to verify no circular dependencies or missing imports."""
import sys
print("Testing imports...")

try:
    from app.models.challenge import Challenge, CheckIn, Enrollment, Task
    print("✓ models.challenge")
except Exception as e:
    print(f"✗ models.challenge: {e}")
    sys.exit(1)

try:
    from app.schemas.challenge import PassportOut, ProgressOut, TaskOut, WeekStatus
    print("✓ schemas.challenge")
except Exception as e:
    print(f"✗ schemas.challenge: {e}")
    sys.exit(1)

try:
    from app.services.challenges import get_student_passport
    print("✓ services.challenges")
except Exception as e:
    print(f"✗ services.challenges: {e}")
    sys.exit(1)

try:
    from app.routers.challenges import router
    print("✓ routers.challenges")
except Exception as e:
    print(f"✗ routers.challenges: {e}")
    sys.exit(1)

try:
    from app.main import app
    print("✓ main (app startup)")
except Exception as e:
    print(f"✗ main: {e}")
    sys.exit(1)

print("\nAll imports successful!")
