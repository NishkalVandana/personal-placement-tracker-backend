from flask import request, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError, PyMongoError

jobs_bp = Blueprint("jobs", __name__)

db["applications"].create_index(
    [("user_id", 1), ("source_job_id", 1)],
    unique=True,
    partialFilterExpression={"source_job_id": {"$exists": True}},
    name="unique_application_source_job"
)


@jobs_bp.route("/jobs", methods=["POST", "GET"])
@jwt_required()
def jobs():
    user_id = get_jwt_identity()
    saved_jobs = db["jobs"]

    if request.method == "POST":
        data = request.get_json()

        if not data:
            return {"message": "Job details are required"}, 400

        companyName = data.get("companyName")
        jobRole = data.get("jobRole")
        jobLink = data.get("jobLink")
        location = data.get("location")
        deadline = data.get("deadline") or ""
        note = data.get("note")

        if not companyName or not jobRole:
            return {"message": "Company name and job role are required"}, 400

        saved_jobs.insert_one({
            "user_id": user_id,
            "companyName": companyName,
            "jobRole": jobRole,
            "jobLink": jobLink,
            "location": location,
            "deadline": deadline,
            "note": note
        })

        return {"message": "Job saved successfully"}, 201

    user_jobs = saved_jobs.find({"user_id": user_id})

    jobs_list = []

    for job in user_jobs:
        job["_id"] = str(job["_id"])
        jobs_list.append(job)

    return jobs_list, 200

@jobs_bp.route("/jobs/<job_id>", methods=["PUT"])
@jwt_required()
def update_job(job_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data:
        return {"message": "Job details are required"}, 400

    companyName = data.get("companyName")
    jobRole = data.get("jobRole")
    jobLink = data.get("jobLink")
    location = data.get("location")
    deadline = data.get("deadline") or ""
    note = data.get("note")

    if not companyName or not jobRole:
        return {
            "message": "Company name and job role are required"
        }, 400

    try:
        job_oid = ObjectId(job_id)
    except Exception:
        return {"message": "Invalid job ID"}, 400

    result = db["jobs"].update_one(
        {
            "_id": job_oid,
            "user_id": user_id
        },
        {
            "$set": {
                "companyName": companyName,
                "jobRole": jobRole,
                "jobLink": jobLink,
                "location": location,
                "deadline": deadline,
                "note": note
            }
        }
    )

    if result.matched_count == 1:
        return {"message": "Job updated successfully"}, 200

    return {"message": "Job not found"}, 404


@jobs_bp.route("/jobs/<job_id>", methods=["DELETE"])
@jwt_required()
def delete_job(job_id):
    user_id = get_jwt_identity()

    try:
        job_oid = ObjectId(job_id)
    except Exception:
        return {"message": "Invalid job ID"}, 400

    result = db["jobs"].delete_one({
        "_id": job_oid,
        "user_id": user_id
    })

    if result.deleted_count == 1:
        return {"message": "Job deleted successfully"}, 200

    return {"message": "Job not found"}, 404


@jobs_bp.route("/jobs/<job_id>/apply", methods=["POST"])
@jwt_required()
def apply_to_job(job_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data:
        return {"message": "Application details are required"}, 400

    company_name = data.get("companyName")
    job_role = data.get("jobRole")
    application_date = data.get("applicationDate")
    resume_id = data.get("resume")

    if not company_name or not job_role or not application_date or not resume_id:
        return {
            "message": "Company, job role, application date, and resume are required"
        }, 400

    try:
        job_oid = ObjectId(job_id)
        resume_oid = ObjectId(resume_id)
    except (InvalidId, TypeError):
        return {"message": "Invalid job or resume ID"}, 400

    jobs = db["jobs"]
    applications = db["applications"]
    job_filter = {"_id": job_oid, "user_id": user_id}
    application_filter = {"user_id": user_id, "source_job_id": job_oid}
    existing_application = applications.find_one(application_filter)
    created_application = False

    if not existing_application:
        saved_job = jobs.find_one(job_filter)
        if not saved_job:
            return {"message": "Job not found"}, 404

        if not db["resumes"].find_one({"_id": resume_oid, "user_id": user_id}):
            return {"message": "Resume not found"}, 404

        application = {
            "user_id": user_id,
            "source_job_id": job_oid,
            "companyName": company_name,
            "jobRole": job_role,
            "applicationDate": application_date,
            "status": "Applied",
            "assessmentDate": data.get("assessmentDate") or "",
            "jobLink": data.get("jobLink") or "",
            "resume_id": str(resume_oid),
            "note": data.get("note") or ""
        }

        try:
            applications.insert_one(application)
            created_application = True
        except DuplicateKeyError:
            existing_application = applications.find_one(application_filter)
            if not existing_application:
                raise

    try:
        jobs.delete_one(job_filter)
    except PyMongoError:
        return {
            "message": (
                "The application was created, but the saved job could not be removed. "
                "Retry this action to finish without creating a duplicate."
            ),
            "applicationCreated": True
        }, 503

    return {
        "message": "Application created and saved job removed",
        "applicationCreated": created_application
    }, 201 if created_application else 200
