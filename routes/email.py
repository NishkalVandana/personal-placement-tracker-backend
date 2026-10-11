from flask import Blueprint, jsonify
from routes.email_service import send_email

email_bp = Blueprint("email", __name__)


@email_bp.route("/send-test-email", methods=["POST"])
def send_test_email():
    try:
        result = send_email(
            "nsp0801@gmail.com",
            "Personal Placement Tracker",
            "Hello! Email integration is working."
        )

        return jsonify({
            "message": "Email request submitted successfully",
            "email_id": result.get("id")
        }), 200

    except Exception:
        return jsonify({
            "error": "Failed to send email"
        }), 500