"""Seed test data for US-5 passport view testing.

Creates a 7-week challenge with tasks at different stages:
- 3 completed weeks
- 2 available weeks (current/past)
- 2 locked weeks (future)
"""

from datetime import date, timedelta

from app.db import SessionLocal, init_db
from app.models.challenge import Challenge, CheckIn, Enrollment, Task
from app.models.student import Student


def seed_test_data():
    """Seed test data for passport view testing."""
    init_db()
    db = SessionLocal()

    try:
        # Create a test student
        student = Student(
            campus_id="csub",
            sso_subject="test-student@csub.edu",
            affiliation="student@csub.edu",
        )
        db.add(student)
        db.flush()

        # Create a 7-week challenge
        today = date.today()
        challenge = Challenge(
            campus_id="csub",
            name="Digital Wellness Challenge",
            theme_name="Stranger Things",
            semester="Fall 2026",
            starts_on=today - timedelta(days=21),  # Started 3 weeks ago
            ends_on=today + timedelta(days=28),  # Ends in 4 weeks
            status="active",
        )
        db.add(challenge)
        db.flush()

        # Enroll the student
        enrollment = Enrollment(
            student_id=student.id,
            challenge_id=challenge.id,
        )
        db.add(enrollment)

        # Create 7 weeks of tasks
        tasks_data = [
            {
                "week_no": 1,
                "title": "Welcome & Orientation",
                "caption": "Learn about the Digital Wellness Challenge",
                "activity_type": "event",
                "location": "Student Health Center",
                "date_start": today - timedelta(days=21),
                "date_end": today - timedelta(days=15),
                "is_required": True,
                "order": 1,
            },
            {
                "week_no": 2,
                "title": "Vision Screening",
                "caption": "Get your eyes checked for healthy screen time",
                "activity_type": "event",
                "location": "SHS Vision Clinic",
                "date_start": today - timedelta(days=14),
                "date_end": today - timedelta(days=8),
                "is_required": True,
                "order": 2,
            },
            {
                "week_no": 3,
                "title": "Social Media Wellness",
                "caption": "Explore healthy social media habits",
                "activity_type": "content",
                "location": None,
                "date_start": today - timedelta(days=7),
                "date_end": today - timedelta(days=1),
                "is_required": True,
                "order": 3,
            },
            {
                "week_no": 4,
                "title": "Digital Detox Workshop",
                "caption": "Learn strategies for unplugging",
                "activity_type": "event",
                "location": "Wellness Lab, Room 201",
                "date_start": today,
                "date_end": today + timedelta(days=6),
                "is_required": True,
                "order": 4,
            },
            {
                "week_no": 5,
                "title": "Sleep & Screen Time",
                "caption": "Understand how screens affect your sleep",
                "activity_type": "assessment",
                "location": None,
                "date_start": today + timedelta(days=7),
                "date_end": today + timedelta(days=13),
                "is_required": True,
                "order": 5,
            },
            {
                "week_no": 6,
                "title": "Mindful Technology Use",
                "caption": "Practice mindfulness with technology",
                "activity_type": "reflection",
                "location": None,
                "date_start": today + timedelta(days=14),
                "date_end": today + timedelta(days=20),
                "is_required": False,  # Optional task
                "order": 6,
            },
            {
                "week_no": 7,
                "title": "Final Celebration",
                "caption": "Celebrate your digital wellness journey",
                "activity_type": "event",
                "location": "Student Union",
                "date_start": today + timedelta(days=21),
                "date_end": today + timedelta(days=27),
                "is_required": True,
                "order": 7,
            },
        ]

        tasks = []
        for task_data in tasks_data:
            task = Task(challenge_id=challenge.id, **task_data)
            db.add(task)
            tasks.append(task)

        db.flush()

        # Complete the first 3 weeks (student has completed 3 of 7)
        for i in range(3):
            check_in = CheckIn(
                student_id=student.id,
                task_id=tasks[i].id,
                method="event_qr",
            )
            db.add(check_in)

        db.commit()
        print("✓ Test data seeded successfully!")
        print(f"  - Student: {student.sso_subject} (ID: {student.id})")
        print(f"  - Challenge: {challenge.name} (ID: {challenge.id})")
        print(f"  - Tasks: {len(tasks)} weeks")
        print("  - Completed: 3 of 7 weeks")
        print("  - Status: 3 complete, 2 available, 2 locked")

    except Exception as e:
        db.rollback()
        print(f"✗ Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_data()
