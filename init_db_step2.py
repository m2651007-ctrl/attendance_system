import sqlite3

conn = sqlite3.connect("database/attendance.db")
cur = conn.cursor()

# Sessions
cur.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    is_active INTEGER DEFAULT 1
)
""")

# Attendance
cur.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    university_id TEXT NOT NULL,
    check_in TIMESTAMP,
    check_out TIMESTAMP,
    status TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
""")

conn.commit()
conn.close()

print("✅ STEP 2 tables created")
