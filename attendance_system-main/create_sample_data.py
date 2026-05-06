import sqlite3
import datetime
import hashlib

conn = sqlite3.connect("database/attendance.db")
cur = conn.cursor()

# Create sample sessions with proper time fields
try:
    # Check if we have a doctor
    cur.execute("SELECT doctor_id FROM doctors LIMIT 1")
    doctor = cur.fetchone()
    
    if not doctor:
        # Create a sample doctor
        cur.execute("""
            INSERT INTO doctors (name, email, username, password_hash)
            VALUES (?, ?, ?, ?)
        """, ("Dr. John Smith", "john@university.edu", "johnsmith", 
              hashlib.sha256("password123".encode()).hexdigest()))
        doctor_id = cur.lastrowid
    else:
        doctor_id = doctor[0]
    
    # Create sample sessions
    sessions_data = [
        ("Cybersecurity", "09:00", "11:00", doctor_id),
        ("Data Science", "10:00", "12:00", doctor_id),
        ("Machine Learning", "14:00", "16:00", doctor_id),
    ]
    
    for course_name, start_time, end_time, doc_id in sessions_data:
        cur.execute("""
            INSERT OR IGNORE INTO sessions (course_name, doctor_id, start_time, end_time, active)
            VALUES (?, ?, ?, ?, 1)
        """, (course_name, doc_id, start_time, end_time))
    
    # Get session IDs
    cur.execute("SELECT session_id, course_name, start_time, end_time FROM sessions")
    sessions = cur.fetchall()
    
    # Create sample students
    students_data = [
        ("2021001", "Alice Johnson", "2021001"),
        ("2021002", "Bob Smith", "2021002"),
        ("2021003", "Carol Williams", "2021003"),
        ("2021004", "David Brown", "2021004"),
        ("2021005", "Eva Davis", "2021005"),
    ]
    
    for university_id, name, academic_number in students_data:
        cur.execute("""
            INSERT OR IGNORE INTO students (university_id, name, academic_number)
            VALUES (?, ?, ?)
        """, (university_id, name, academic_number))
    
    # Create sample attendance records
    attendance_data = [
        # Present students
        (1, "2021001", datetime.datetime.now().replace(hour=9, minute=5, second=0), 
         datetime.datetime.now().replace(hour=11, minute=2, second=0), "Present"),
        (1, "2021002", datetime.datetime.now().replace(hour=9, minute=3, second=0), 
         datetime.datetime.now().replace(hour=11, minute=5, second=0), "Present"),
        
        # Late students
        (1, "2021003", datetime.datetime.now().replace(hour=9, minute=20, second=0), 
         datetime.datetime.now().replace(hour=11, minute=0, second=0), "Present"),
        
        # Not checked out
        (2, "2021004", datetime.datetime.now().replace(hour=10, minute=2, second=0), 
         None, "Present"),
        (2, "2021005", datetime.datetime.now().replace(hour=10, minute=25, second=0), 
         None, "Present"),
        
        # More records for variety
        (3, "2021001", datetime.datetime.now().replace(hour=14, minute=1, second=0), 
         datetime.datetime.now().replace(hour=16, minute=3, second=0), "Present"),
        (3, "2021003", datetime.datetime.now().replace(hour=14, minute=18, second=0), 
         datetime.datetime.now().replace(hour=16, minute=1, second=0), "Present"),
    ]
    
    for session_id, university_id, check_in, check_out, status in attendance_data:
        cur.execute("""
            INSERT OR IGNORE INTO attendance 
            (session_id, university_id, check_in, check_out, status)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, university_id, check_in, check_out, status))
    
    conn.commit()
    print("Sample data created successfully")
    
except Exception as e:
    print(f"Error creating sample data: {e}")
    conn.rollback()
finally:
    conn.close()
