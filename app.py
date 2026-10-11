
import os

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from apscheduler.schedulers.background import BackgroundScheduler

from routes.auth import auth_bp
from routes.resume import resume_bp
from routes.applications import applications_bp
from routes.jobs import jobs_bp
from routes.interviews import interviews_bp
from routes.profile import profile_bp
from routes.email import email_bp
from routes.reminder_service import check_reminders

load_dotenv()

app = Flask(__name__)

# JWT configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

if not app.config["JWT_SECRET_KEY"]:
    raise RuntimeError("JWT_SECRET_KEY is missing from environment variables")

jwt = JWTManager(app)

# Register existing blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(applications_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(interviews_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(email_bp)

# Allow the local frontend and the deployed frontend.
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

frontend_url = os.getenv("FRONTEND_URL")

if frontend_url:
    allowed_origins.append(frontend_url.rstrip("/"))

CORS(
    app,
    resources={
        r"/*": {
            "origins": allowed_origins,
            "methods": [
                "GET", "POST", "PUT", "DELETE", "OPTIONS"
            ],
            "allow_headers": [
                "Authorization", "Content-Type"
            ],
        }
    },
)

@app.route("/")
def home():
    return "Flask server is working!"


# Keep the scheduler for local development.
# Production will use a separate reminder worker.
if __name__ == "__main__":
    scheduler = BackgroundScheduler(
        timezone="Asia/Kolkata"
    )

    scheduler.add_job(
        func=check_reminders,
        trigger="date",
        id="initial_reminder_check",
    )

    scheduler.add_job(
        func=check_reminders,
        trigger="interval",
        minutes=1,
        id="reminder_checker",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    print("Email reminder scheduler started!")

    try:
        app.run(debug=True, use_reloader=False)
    finally:
        scheduler.shutdown(wait=False)
