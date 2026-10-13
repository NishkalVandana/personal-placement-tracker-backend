import re

from flask import Blueprint, request
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import users


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {"message": "All details are necessary"}, 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not isinstance(username, str) or not username.strip():
        return {"message": "Username is required"}, 400

    username = username.strip()
    if len(username) > 100:
        return {"message": "Username must be 100 characters or fewer"}, 400

    if not isinstance(email, str):
        return {"message": "A valid email is required"}, 400

    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return {"message": "A valid email is required"}, 400

    if not isinstance(password, str) or len(password) < 8:
        return {"message": "Password must be at least 8 characters"}, 400

    if users.find_one({"email": email}):
        return {"message": "User already exists"}, 409

    users.insert_one({
        "username": username,
        "email": email,
        "password": generate_password_hash(password),
    })

    return {"message": "Registration successful. You can now log in."}, 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {"message": "All details are required"}, 400

    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password:
        return {"message": "All details are required"}, 400

    user = users.find_one({"email": email.strip().lower()})
    if not user:
        return {"message": "User does not exist"}, 404

    password_hash = user.get("password")
    if not isinstance(password_hash, str) or not check_password_hash(password_hash, password):
        return {"message": "Passwords do not match"}, 401

    access_token = create_access_token(identity=str(user["_id"]))
    return {
        "message": "User Login Successful",
        "access_token": access_token,
    }
