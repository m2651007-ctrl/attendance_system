import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database", "attendance.db")
SECRET_KEY = "super-secret-key"


