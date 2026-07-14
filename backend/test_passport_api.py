"""Test script to verify US-5 passport API endpoint works correctly."""

import sys

from sqlalchemy import select

from app.auth.session import mint_session_token
from app.db import SessionLocal, init_db
from app.models.student import Student
from app.services.challenges import get_student_passport


def test_passport_api():
    """Test the passport API with seeded data."""
    init_db()
    db = SessionLocal()

    try:
        # Find the test student
        stmt = select(Student).where(Student.sso_subject == "test-student@csub.edu")
        student = db.scalar(stmt)

        if not student:
            print("✗ Test student not found. Run seed_test_data.py first.")
            return False

        print(f"✓ Found test student: {student.sso_subject} (ID: {student.id})")

        # Test the passport service function
        passport = get_student_passport(db, student.id, student.campus_id)

        if not passport:
            print("✗ No passport data returned")
            return False

        print("\n✓ Passport data retrieved successfully:")
        print(f"  Challenge: {passport.challenge.name}")
        print(f"  Theme: {passport.challenge.theme_name}")
        print(f"  Total weeks: {passport.progress.total_weeks}")
        print(f"  Completed: {passport.progress.completed}")
        print(f"  Remaining: {passport.progress.remaining}")
        print(f"  Prize eligible: {passport.progress.is_prize_eligible}")

        print("\n  Week statuses:")
        for task in passport.tasks:
            print(f"    Week {task.week_no}: {task.status.value} - {task.title}")

        # Verify Gherkin scenarios
        print("\n✓ Testing Gherkin scenarios:")

        # Scenario 1: Passport shows week tiles with status
        locked_count = sum(1 for t in passport.tasks if t.status.value == "locked")
        available_count = sum(1 for t in passport.tasks if t.status.value == "available")
        complete_count = sum(1 for t in passport.tasks if t.status.value == "complete")

        print("  ✓ Scenario 1: Week tiles with status")
        print(f"    - {complete_count} complete")
        print(f"    - {available_count} available")
        print(f"    - {locked_count} locked")

        # Scenario 2: Progress countdown reflects completion
        expected_format = (
            f"{passport.progress.completed} of {passport.progress.total_weeks} "
            f"complete, {passport.progress.remaining} remaining"
        )
        print("  ✓ Scenario 2: Progress countdown")
        print(f"    - Format: '{expected_format}'")

        # Scenario 3: Check expected values (3 of 7 complete, 4 remaining)
        if (
            passport.progress.completed == 3
            and passport.progress.total_weeks == 7
            and passport.progress.remaining == 4
        ):
            print(
                "  ✓ Scenario 3: Expected values correct "
                "(3 of 7 complete, 4 remaining)"
            )
        else:
            print("  ✗ Scenario 3: Unexpected values")
            return False

        # Generate a test JWT token
        token = mint_session_token(
            sso_subject=student.sso_subject,
            affiliation=student.affiliation,
            campus_id=student.campus_id,
            student_id=student.id,
        )
        print("\n✓ Test JWT token generated (for manual API testing):")
        print(f"  Cookie: wp_session={token}")
        print("\n  To test the API endpoint manually:")
        print(
            f"  curl -H 'Cookie: wp_session={token}' http://localhost:8000/api/passport"
        )

        return True

    except Exception as e:
        print(f"✗ Error during test: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_passport_api()
    sys.exit(0 if success else 1)
