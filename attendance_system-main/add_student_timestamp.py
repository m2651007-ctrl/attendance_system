import sqlite3
import datetime

def add_student_timestamp():
    """Add created_at timestamp column to students table"""
    conn = sqlite3.connect("database/attendance.db")
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(students)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'created_at' not in columns:
            print("Adding created_at column to students table...")
            cursor.execute("""
                ALTER TABLE students 
                ADD COLUMN created_at TIMESTAMP
            """)
            
            # Update existing records to have today's date as created_at
            today = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                UPDATE students 
                SET created_at = ? 
                WHERE created_at IS NULL
            """, (today,))
            
            conn.commit()
            print("✅ created_at column added successfully")
            print(f"✅ Updated existing records with today's date: {today}")
        else:
            print("✅ created_at column already exists")
            
    except Exception as e:
        print(f"❌ Error adding created_at column: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_student_timestamp()
