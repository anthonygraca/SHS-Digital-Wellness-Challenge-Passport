"""Safe database migration - adds content_tags column without deleting data."""
import sqlite3
from pathlib import Path

def migrate_database(db_path: str) -> bool:
    """Add content_tags column to tasks table if it doesn't exist."""
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        return False
    
    print(f"\nMigrating: {db_path}")
    print("-" * 60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tasks table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tasks'
        """)
        if not cursor.fetchone():
            print("  ⚠️  tasks table doesn't exist - skipping")
            conn.close()
            return False
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "content_tags" in columns:
            print("  ✓ content_tags column already exists")
            conn.close()
            return True
        
        # Add the column (safe - doesn't delete any data)
        print("  → Adding content_tags column...")
        cursor.execute("""
            ALTER TABLE tasks 
            ADD COLUMN content_tags VARCHAR(255) NOT NULL DEFAULT ''
        """)
        conn.commit()
        
        # Verify it was added
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "content_tags" in columns:
            print("  ✓ Successfully added content_tags column")
            
            # Count tasks
            cursor.execute("SELECT COUNT(*) FROM tasks")
            task_count = cursor.fetchone()[0]
            print(f"  ✓ All {task_count} existing tasks preserved")
            
            conn.close()
            return True
        else:
            print("  ✗ Failed to add column")
            conn.close()
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("SAFE Database Migration - US-15")
    print("Adding content_tags column to tasks table")
    print("=" * 60)
    print("\nThis migration:")
    print("  ✓ Adds the missing content_tags column")
    print("  ✓ Preserves all existing data")
    print("  ✓ Does NOT delete anything")
    print("  ✓ Safe to run multiple times")
    
    # Find all .db files in backend directory
    backend_dir = Path("backend")
    db_files = list(backend_dir.glob("*.db"))
    
    if not db_files:
        print("\n⚠️  No database files found in backend/")
        print("The database will be created when you start the backend.")
        return 0
    
    print(f"\nFound {len(db_files)} database file(s):")
    for db_file in db_files:
        print(f"  - {db_file.name}")
    
    success_count = 0
    for db_file in db_files:
        if migrate_database(str(db_file)):
            success_count += 1
    
    print("\n" + "=" * 60)
    if success_count > 0:
        print(f"✓ Successfully migrated {success_count} database(s)")
        print("=" * 60)
        print("\nYou can now start the backend:")
        print("  cd backend")
        print("  python -m uvicorn app.main:app --reload --port 8000")
    else:
        print("No databases were migrated.")
        print("=" * 60)
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
