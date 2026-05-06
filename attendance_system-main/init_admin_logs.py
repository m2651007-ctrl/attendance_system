import sqlite3

conn = sqlite3.connect("database/attendance.db")
cur = conn.cursor()

# Admin logs table
cur.execute("""
CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    student_name TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id INTEGER,
    details TEXT
)
""")

conn.commit()
conn.close()

print("Admin logs table created")
