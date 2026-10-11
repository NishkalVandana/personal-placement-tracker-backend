
from flask import request, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from bson import ObjectId


interviews_bp = Blueprint("interviews", __name__)


# GET all interviews / POST a new interview
@interviews_bp.route("/interviews", methods=["GET", "POST"])
@jwt_required()
def interviews():
    user_id = get_jwt_identity()
    interviews_collection = db["interviews"]

    if not user_id:
        return {"message": "Unauthorized access"}, 401

    # GET: Fetch interviews belonging to the logged-in user
    if request.method == "GET":
        user_interviews = interviews_collection.find(
            {"user_id": user_id}
        ).sort([("scheduledDate", 1), ("scheduledTime", 1)])

        interviews_list = []

        for interview in user_interviews:
            interview["_id"] = str(interview["_id"])

            if interview.get("application_id"):
                interview["application_id"] = str(
                    interview["application_id"]
                )

            interviews_list.append(interview)

        return interviews_list, 200

    # POST: Create a new interview
    data = request.get_json() or {}

    application_id = data.get("application_id")
    roundName = data.get("roundName")
    scheduledDate = data.get("scheduledDate")

    if not application_id or not roundName or not scheduledDate:
        return {
            "message": (
                "Application, interview round, and scheduled date "
                "are required"
            )
        }, 400

    try:
        application_oid = ObjectId(application_id)
    except Exception:
        return {"message": "Invalid application ID"}, 400

    # Verify that the application belongs to the logged-in user
    application = db["applications"].find_one({
        "_id": application_oid,
        "user_id": user_id
    })

    if not application:
        return {"message": "Application not found"}, 404

    interview = {
        "user_id": user_id,
        "application_id": application_oid,
        "companyName": application.get("companyName", ""),
        "jobRole": application.get("jobRole", ""),
        "roundName": roundName,
        "scheduledDate": scheduledDate,
        "scheduledTime": data.get("scheduledTime", ""),
        "mode": data.get("mode", "Online"),
        "meetingLink": data.get("meetingLink", ""),
        "status": data.get("status", "Scheduled"),
        "outcome": data.get("outcome", "Pending"),
        "notes": data.get("notes", ""),
        "feedback": data.get("feedback", "")
    }

    valid_statuses = ["Scheduled", "Completed", "Cancelled"]
    valid_outcomes = ["Pending", "Passed", "Failed", "On Hold"]

    if interview["status"] not in valid_statuses:
        return {"message": "Invalid interview status"}, 400

    if interview["outcome"] not in valid_outcomes:
        return {"message": "Invalid interview outcome"}, 400

    result = interviews_collection.insert_one(interview)

    return {
        "message": "Interview scheduled successfully",
        "interview_id": str(result.inserted_id)
    }, 201


# PUT: Update an existing interview
@interviews_bp.route("/interviews/<interview_id>", methods=["PUT"])
@jwt_required()
def update_interview(interview_id):
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    if not user_id:
        return {"message": "Unauthorized access"}, 401

    try:
        interview_oid = ObjectId(interview_id)
    except Exception:
        return {"message": "Invalid interview ID"}, 400

    existing_interview = db["interviews"].find_one({
        "_id": interview_oid,
        "user_id": user_id
    })

    if not existing_interview:
        return {"message": "Interview not found"}, 404

    # Update only the fields supplied by the client
    allowed_fields = [
        "roundName",
        "scheduledDate",
        "scheduledTime",
        "mode",
        "meetingLink",
        "status",
        "outcome",
        "notes",
        "feedback"
    ]

    updates = {
        field: data[field]
        for field in allowed_fields
        if field in data
    }

    if not updates:
        return {"message": "No fields provided to update"}, 400

    if "roundName" in updates and not updates["roundName"]:
        return {"message": "Interview round is required"}, 400

    if "scheduledDate" in updates and not updates["scheduledDate"]:
        return {"message": "Scheduled date is required"}, 400

    valid_statuses = ["Scheduled", "Completed", "Cancelled"]
    valid_outcomes = ["Pending", "Passed", "Failed", "On Hold"]

    if (
        "status" in updates
        and updates["status"] not in valid_statuses
    ):
        return {"message": "Invalid interview status"}, 400

    if (
        "outcome" in updates
        and updates["outcome"] not in valid_outcomes
    ):
        return {"message": "Invalid interview outcome"}, 400

    db["interviews"].update_one(
        {
            "_id": interview_oid,
            "user_id": user_id
        },
        {"$set": updates}
    )

    return {"message": "Interview updated successfully"}, 200


# DELETE: Delete an interview
@interviews_bp.route("/interviews/<interview_id>", methods=["DELETE"])
@jwt_required()
def delete_interview(interview_id):
    user_id = get_jwt_identity()

    if not user_id:
        return {"message": "Unauthorized access"}, 401

    try:
        interview_oid = ObjectId(interview_id)
    except Exception:
        return {"message": "Invalid interview ID"}, 400

    result = db["interviews"].delete_one({
        "_id": interview_oid,
        "user_id": user_id
    })

    if result.deleted_count == 1:
        return {"message": "Interview deleted successfully"}, 200

    return {"message": "Interview not found"}, 404
