"""Quick script to enroll a test student in the demo challenge.

Run after seed_dev.py to prepare for US-15 testing.

Usage:
    cd backend
    python enroll_test_student.py
"""

from app.db import SessionLocal
from app.models.challenge import Challenge, Enrollment
from app.models.student import Student
from sqlalchemy import select


def main():
    db = SessionLocal()
    try:
        # Find the demo challenge
        challenge = db.execute(
            select(Challenge)
            .where(Challenge.campus_id == "csub", Challenge.status == "published")
            .order_by(Challenge.id.desc())
        ).scalar_one_or_none()

        if not challenge:
            print("❌ No published challenge found. Run seed_dev.py first.")
            return

        # Find or create the test student (abc@csub.edu)
        student = db.execute(
            select(Student).where(Student.sso_subject == "abc@csub.edu")
        ).scalar_one_or_none()

        if not student:
            # Create the test student
            student = Student(
                sso_subject="abc@csub.edu",
                campus_id="csub",
                affiliation="student",
                is_current_student=True,
            )
            db.add(student)
            db.commit()
            db.refresh(student)
            print(f"✅ Created test student: {student.sso_subject} (id={student.id})")
        else:
            print(f"✅ Found test student: {student.sso_subject} (id={student.id})")

        # Check if already enrolled
        existing = db.execute(
            select(Enrollment).where(
                Enrollment.student_id == student.id,
                Enrollment.challenge_id == challenge.id,
            )
        ).scalar_one_or_none()

        if existing:
            print(f"✅ Student already enrolled in challenge: {challenge.name}")
        else:
            # Enroll the student
            enrollment = Enrollment(student_id=student.id, challenge_id=challenge.id)
            db.add(enrollment)
            db.commit()
            print(f"✅ Enrolled student in challenge: {challenge.name}")

        print(f"\n🎉 Ready to test US-15!")
        print(f"   Challenge: {challenge.name}")
        print(f"   Student: {student.sso_subject}")
        print(f"   Tasks: {len(challenge.tasks)}")
        print(f"\n📝 Next steps:")
        print(f"   1. Sign in at http://localhost:5173")
        print(f"   2. Use the Student preset (abc@csub.edu)")
        print(f"   3. View your passport")
        print(f"   4. Click on an available task")
        print(f"   5. Click 'Check in' to see the personalized tip!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
