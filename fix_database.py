"""Fix database schema to add missing content_tags column."""
import sqlite3
import sys
from pathlib import Path

# Database file paths
DB_FILES = [
    "backend/wellness_passport.db",
    "backend/wellness.db",
]

def add_content_tags_column(db_path: str):
    """Add content_tags column to tasks table if it doesn't exist."""
    if not Path(db_path).exists():
        print(f"⚠️  Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "content_tags" in columns:
            print(f"✓ content_tags already exists in {db_path}")
            conn.close()
            return True
        
        # Add the column
        print(f"Adding content_tags column to {db_path}...")
        cursor.execute("""
            ALTER TABLE tasks 
            ADD COLUMN content_tags VARCHAR(255) NOT NULL DEFAULT ''
        """)
        conn.commit()
        conn.close()
        
        print(f"✓ Successfully added content_tags to {db_path}")
        return True
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print(f"⚠️  tasks table doesn't exist in {db_path} - database not initialized")
        else:
            print(f"✗ Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error updating {db_path}: {e}")
        return False

def main():
    print("=" * 60)
    print("Database Schema Fix - Adding content_tags to tasks")
    print("=" * 60)
    print()
    
    success_count = 0
    for db_file in DB_FILES:
        if add_content_tags_column(db_file):
            success_count += 1
        print()
    
    if success_count > 0:
        print("=" * 60)
        print(f"✓ Updated {success_count} database(s)")
        print("=" * 60)
        print()
        print("Now try starting the backend:")
        print("  cd backend")
        print("  python -m uvicorn app.main:app --reload --port 8000")
        return 0
    else:
        print("=" * 60)
        print("No databases were updated.")
        print("Try deleting the database files and restarting to create fresh:")
        print("  rm backend/*.db")
        print("  cd backend && python -m uvicorn app.main:app --reload --port 8000")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
