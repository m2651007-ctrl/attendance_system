import sqlite3
import datetime
from helpers import get_db

def test_student_statistics():
    """Test the student statistics queries"""
    print("🧪 Testing Student Statistics Queries")
    print("=" * 50)
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Test 1: Total Students Count
        cur.execute("SELECT COUNT(*) FROM students")
        total_students = cur.fetchone()[0]
        print(f"✅ Total Students: {total_students}")
        
        # Test 2: Today's Registrations
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        print(f"📅 Today's Date: {today}")
        
        cur.execute("""
            SELECT COUNT(*) FROM students 
            WHERE DATE(created_at) = ?
        """, (today,))
        today_registrations = cur.fetchone()[0]
        print(f"✅ Today's Registrations: {today_registrations}")
        
        # Test 3: Check if created_at column exists and has data
        cur.execute("PRAGMA table_info(students)")
        columns = [column[1] for column in cur.fetchall()]
        print(f"📋 Students table columns: {columns}")
        
        if 'created_at' in columns:
            print("✅ created_at column exists")
            
            # Show sample data
            cur.execute("""
                SELECT university_id, name, created_at 
                FROM students 
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            sample_students = cur.fetchall()
            print("📝 Sample student data:")
            for student in sample_students:
                print(f"   - {student[0]}: {student[1]} (created: {student[2]})")
        else:
            print("❌ created_at column missing")
            
        # Test 4: Verify date filtering works
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        cur.execute("""
            SELECT COUNT(*) FROM students 
            WHERE DATE(created_at) = ?
        """, (yesterday,))
        yesterday_registrations = cur.fetchone()[0]
        print(f"📅 Yesterday's Registrations: {yesterday_registrations}")
        
        print("\n🎯 Summary:")
        print(f"   Total students in database: {total_students}")
        print(f"   Students registered today: {today_registrations}")
        print(f"   Students registered yesterday: {yesterday_registrations}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_student_statistics()
