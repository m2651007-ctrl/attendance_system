import sqlite3

conn = sqlite3.connect("database/attendance.db")
cur = conn.cursor()

# Update sessions table to have proper time fields (not timestamps)
try:
    # Check if columns already exist
    cur.execute("PRAGMA table_info(sessions)")
    columns = [column[1] for column in cur.fetchall()]
    
    if 'start_time' not in columns:
        cur.execute("ALTER TABLE sessions ADD COLUMN start_time TEXT")
    
    if 'end_time' not in columns:
        cur.execute("ALTER TABLE sessions ADD COLUMN end_time TEXT")
    
    # Update existing sessions to have default times if they don't exist
    cur.execute("""
        UPDATE sessions 
        SET start_time = '08:00' 
        WHERE start_time IS NULL OR start_time = ''
    """)
    
    cur.execute("""
        UPDATE sessions 
        SET end_time = '10:00' 
        WHERE end_time IS NULL OR end_time = ''
    """)
    
    print("Sessions table updated with time fields")
except Exception as e:
    print(f"Error updating sessions table: {e}")

# No need to modify attendance table as it already has check_in and check_out
# and we can get instructor name by joining with doctors table

conn.commit()
conn.close()

print("Database schema updated successfully")
