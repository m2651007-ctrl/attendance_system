from flask import Flask, redirect
from config import SECRET_KEY
from routes.admin_routes   import register_admin_routes
from routes.doctor_routes  import register_doctor_routes
from routes.student_routes import register_student_routes
from routes.kiosk_routes   import register_kiosk_routes

app = Flask(__name__)
app.secret_key = SECRET_KEY

register_admin_routes(app)
register_doctor_routes(app)
register_student_routes(app)
register_kiosk_routes(app)

@app.route("/")
def home():
    return redirect("/admin/login")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False,
        threaded=True
    )
