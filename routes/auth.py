from flask import request, Blueprint
from extensions import db, users, pending_registrations
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from routes.email_service import send_email
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import os
import hmac
auth_bp=Blueprint("auth",__name__)
@auth_bp.route("/register",methods=['POST'])
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    if not data:
        return {"message": "All details are necessary"}, 400

    username = data.get("username")
    email = data.get("email", "").strip().lower()
    password = data.get("password")

    if not username or not email or not password:
        return {"message": "All details are necessary"}, 400

    if users.find_one({"email": email}):
        return {"message": "User already exists"}, 409

    # Generate a secure six-digit OTP
    otp = f"{secrets.randbelow(1_000_000):06d}"

    otp_hash = hashlib.sha256(otp.encode()).hexdigest()

    # Store registration details temporarily
    pending_registrations.update_one(
        {"email": email},
        {
            "$set": {
                "username": username,
                "email": email,
                "password": generate_password_hash(password),
                "otp_hash": otp_hash,
                "expires_at": datetime.now(timezone.utc)
                + timedelta(minutes=5),
                "attempts": 0,
                "last_sent_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

    try:
        send_email(
            email,
            "Verify Your Placement Tracker Account",
            f"Your verification code is {otp}. "
            "It expires in 5 minutes."
        )
    except Exception:
        pending_registrations.delete_one({"email": email})
        return {"message": "Unable to send verification email"}, 502

    return {
        "message": "OTP sent successfully. Please verify your email."
    }, 200

@auth_bp.route('/login',methods=["POST"])
def login():
    data=request.get_json()
    if not data:
        return {"message":"All details are neccessary"},400
    email=data.get("email")
    password=data.get("password")
    if not email or not password:
            return {"message":"All details are required"},400 
    user=users.find_one({"email":email})
    if not user:
            return {"message":"User does not exist"},404
    if user.get("email_verified") is not True:
        return {
            "message": "Please verify your email before logging in."
        }, 403
    hash_password=user.get("password")
    if not check_password_hash(hash_password,password):
        return {"message":"Passwords doesnt match"},401
    userid=user["_id"]
    access_token=create_access_token(identity=str(userid))
    return {"message":"User Login Successful",
            "access_token":access_token
        }
@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()

    if not data:
        return {"message": "Email and OTP are required"}, 400

    email = data.get("email", "").strip().lower()
    otp = data.get("otp", "").strip()

    if not email or not otp:
        return {"message": "Email and OTP are required"}, 400

    if not otp.isdigit() or len(otp) != 6:
        return {"message": "Invalid OTP format"}, 400

    pending = pending_registrations.find_one({"email": email})

    if not pending:
        return {"message": "No pending registration found"}, 404

    if pending.get("attempts", 0) >= 5:
        return {"message": "Too many attempts. Request a new OTP."}, 429

    expires_at = pending["expires_at"]

    # MongoDB may return a naive UTC datetime
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) >= expires_at:
        pending_registrations.delete_one({"_id": pending["_id"]})
        return {"message": "OTP expired. Please register again."}, 400

    submitted_hash = hashlib.sha256(otp.encode()).hexdigest()

    if not hmac.compare_digest(
        submitted_hash, pending["otp_hash"]
    ):
        pending_registrations.update_one(
            {"_id": pending["_id"]},
            {"$inc": {"attempts": 1}}
        )
        return {"message": "Incorrect OTP"}, 400

    # Prevent duplicate accounts
    if users.find_one({"email": email}):
        pending_registrations.delete_one({"_id": pending["_id"]})
        return {"message": "User already exists"}, 409

    users.insert_one({
        "username": pending["username"],
        "email": pending["email"],
        "password": pending["password"],
        "email_verified": True
    })

    pending_registrations.delete_one({"_id": pending["_id"]})

    return {
        "message": "Email verified successfully. You can now log in."
    }, 200