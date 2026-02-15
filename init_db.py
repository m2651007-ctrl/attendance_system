import sqlite3

conn = sqlite3.connect("database/attendance.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    university_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    academic_number TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS student_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id TEXT NOT NULL,
    face_encoding TEXT NOT NULL,
    FOREIGN KEY (university_id) REFERENCES students (university_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
""")

conn.commit()
conn.close()

print("✅ DB & tables created")
