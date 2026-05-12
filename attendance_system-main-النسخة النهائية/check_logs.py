import sqlite3

conn = sqlite3.connect('database/attendance.db')
cur  = conn.cursor()

# 1. شوف كل الجداول
print("=" * 60)
print("الجداول الموجودة في قاعدة البيانات:")
print("=" * 60)
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
for r in cur.fetchall():
    print(f"  - {r[0]}")

# 2. شوف admin_logs
print("\n" + "=" * 60)
print("آخر 10 سجلات في admin_logs:")
print("=" * 60)
try:
    cur.execute("""
        SELECT action, student_id, student_name, details, timestamp
        FROM admin_logs
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"\n[{r[4]}] {r[0]}")
            print(f"  student: {r[1]} - {r[2]}")
            print(f"  details: {r[3]}")
    else:
        print("لا توجد سجلات!")
except Exception as e:
    print(f"خطأ: {e}")

# 3. شوف SPOOF تحديداً
print("\n" + "=" * 60)
print("سجلات SPOOF فقط:")
print("=" * 60)
try:
    cur.execute("""
        SELECT action, details, timestamp
        FROM admin_logs
        WHERE action LIKE '%SPOOF%'
        ORDER BY timestamp DESC
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"[{r[2]}] {r[0]} | {r[1]}")
    else:
        print("لا توجد محاولات SPOOF!")
except Exception as e:
    print(f"خطأ: {e}")

conn.close()
