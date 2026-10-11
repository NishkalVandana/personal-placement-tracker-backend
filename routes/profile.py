
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from extensions import users

profile_bp = Blueprint("profile", __name__)

DEFAULT_NOTIFICATIONS = {
    "email": True,
    "sms": False,
    "whatsapp": False
}

DEFAULT_REMINDERS = {
    "deadlines": True,
    "assessments": True,
    "interviews": True
}


def get_current_user():
    user_id = get_jwt_identity()

    if not ObjectId.is_valid(user_id):
        return None

    return users.find_one({"_id": ObjectId(user_id)})


def serialize_profile(user):
    saved_notifications = user.get("notifications") or {}
    saved_reminders = user.get("reminders") or {}

    return {
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "mobile": user.get("mobile", ""),
        "notifications": {
            "email": saved_notifications.get("email", True),
            "sms": False,
            "whatsapp": False
        },
        "reminders": {
            **DEFAULT_REMINDERS,
            **saved_reminders
        }
    }


@profile_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user = get_current_user()

    if not user:
        return jsonify({"message": "User not found"}), 404

    return jsonify(serialize_profile(user)), 200


@profile_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user = get_current_user()

    if not user:
        return jsonify({"message": "User not found"}), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"message": "Invalid request data"}), 400

    username = data.get("username", user.get("username", ""))
    mobile = data.get("mobile", user.get("mobile", ""))

    if not isinstance(username, str) or not username.strip():
        return jsonify({"message": "Name is required"}), 400

    if len(username.strip()) > 100:
        return jsonify({
            "message": "Name must be 100 characters or fewer"
        }), 400

    if not isinstance(mobile, str) or len(mobile) > 20:
        return jsonify({"message": "Invalid mobile number"}), 400

    notifications = data.get(
        "notifications",
        user.get("notifications", DEFAULT_NOTIFICATIONS)
    )

    reminders = data.get(
        "reminders",
        user.get("reminders", DEFAULT_REMINDERS)
    )

    if not isinstance(notifications, dict) or not isinstance(reminders, dict):
        return jsonify({
            "message": "Invalid notification preferences"
        }), 400

    # Validate notification preference fields.
    if any(
        key not in DEFAULT_NOTIFICATIONS
        or not isinstance(value, bool)
        for key, value in notifications.items()
    ):
        return jsonify({
            "message": "Invalid notification preferences"
        }), 400

    # SMS and WhatsApp are intentionally unavailable.
    if notifications.get("sms", False) or notifications.get("whatsapp", False):
        return jsonify({
            "message": "SMS and WhatsApp notifications are not available yet"
        }), 400

    # Validate reminder preference fields.
    if any(
        key not in DEFAULT_REMINDERS
        or not isinstance(value, bool)
        for key, value in reminders.items()
    ):
        return jsonify({
            "message": "Invalid reminder preferences"
        }), 400

    existing_notifications = user.get("notifications") or {}
    existing_reminders = user.get("reminders") or {}

    saved_notifications = {
        "email": notifications.get(
            "email",
            existing_notifications.get("email", True)
        ),
        "sms": False,
        "whatsapp": False
    }

    saved_reminders = {
        **DEFAULT_REMINDERS,
        **existing_reminders,
        **reminders
    }

    users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "username": username.strip(),
                "mobile": mobile.strip(),
                "notifications": saved_notifications,
                "reminders": saved_reminders
            }
        }
    )

    updated_user = users.find_one({"_id": user["_id"]})

    return jsonify({
        "message": "Profile saved successfully",
        **serialize_profile(updated_user)
    }), 200
