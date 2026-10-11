from flask import Flask,request,Blueprint
from flask_jwt_extended import jwt_required,get_jwt_identity
from extensions import db
from bson import ObjectId


applications_bp=Blueprint("applications",__name__)
@applications_bp.route("/applications",methods=["POST","GET"])
@jwt_required()
def applications():
    if request.method=="POST":
        data=request.get_json()
        user_id=get_jwt_identity()
        if not user_id:
            return {"message":"User not authorized"},400
        if not data:
            return {"message":"All details are required"},400
        companyName=data.get("companyName")
        jobRole=data.get("jobRole")
        applicationDate=data.get("applicationDate")
        status=data.get("status")
        assessmentDate=data.get("assessmentDate")
        jobLink=data.get("jobLink")
        resume_id=data.get("resume")
        note=data.get("note")
        if not companyName or not jobRole or not applicationDate or not jobLink or not resume_id:
            return {"message":"Please fill all details"},400
        applications=db["applications"]
        result = applications.insert_one({
            "user_id":user_id,
            "companyName":companyName,
            "jobRole":jobRole,
            "applicationDate":applicationDate,
            "status":status,
            "assessmentDate":assessmentDate,
            "jobLink":jobLink,
            "resume_id":resume_id,
            "note":note
        })
        return {
            "message": "Application successfully saved",
            "application_id": str(result.inserted_id)
        }, 201
    applications=db["applications"]
    user_id=get_jwt_identity()
    userapplications=applications.find({
        "user_id":user_id
    })
    applications_list=[]
    for app in userapplications:
        app["_id"] = str(app["_id"])
        if app.get("source_job_id") is not None:
                app["source_job_id"] = str(app["source_job_id"])
        applications_list.append(app)
    
    return applications_list


@applications_bp.route("/applications/<application_id>",methods=["DELETE"])
@jwt_required()
def delete_applications(application_id):
    user_id=get_jwt_identity()
    if not user_id:
        return {"message":"User not authorized"},400
    applications=db["applications"]
    result=applications.delete_one({
        "_id":ObjectId(application_id),
        "user_id":user_id
    })
    if result.deleted_count==1:
        return {"message":"Application Deleted Successfully"},200
    return {"message":"Application not found"},404

@applications_bp.route("/applications/<application_id>", methods=["PUT"])
@jwt_required()
def update_application(application_id):
    user_id = get_jwt_identity()
    if not user_id:
        return {"message": "User not authorized"}, 400

    data = request.get_json()
    if not data:
        return {"message": "All details are required"}, 400

    companyName = data.get("companyName")
    jobRole = data.get("jobRole")
    applicationDate = data.get("applicationDate")
    status = data.get("status")
    assessmentDate = data.get("assessmentDate")
    jobLink = data.get("jobLink")
    resume_id = data.get("resume")
    note = data.get("note")

    # Same required fields as the POST route
    if not companyName or not jobRole or not applicationDate or not jobLink or not resume_id:
        return {"message": "Please fill all details"}, 400

    try:
        app_oid = ObjectId(application_id)
        resume_oid = ObjectId(resume_id)
    except Exception:
        return {"message": "Invalid id"}, 400

    # Make sure the chosen resume belongs to this user
    if not db["resumes"].find_one({"_id": resume_oid, "user_id": user_id}):
        return {"message": "Resume not found"}, 404

    result = db["applications"].update_one(
        {"_id": app_oid, "user_id": user_id},
        {"$set": {
            "companyName": companyName,
            "jobRole": jobRole,
            "applicationDate": applicationDate,
            "status": status,
            "assessmentDate": assessmentDate,
            "jobLink": jobLink,
            "resume_id": resume_id,
            "note": note
        }}
    )

    # matched_count (not modified_count), so saving without changes still succeeds
    if result.matched_count == 1:
        return {"message": "Application updated successfully"}, 200
    return {"message": "Application not found"}, 404
  