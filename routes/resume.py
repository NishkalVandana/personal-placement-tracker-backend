#resume
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from flask import Flask,request,Blueprint
from extensions import db,users
from bson import ObjectId
from datetime import datetime
resume_bp=Blueprint("resume",__name__)
@resume_bp.route("/resumes", methods=["GET", "POST"])
@jwt_required()
def resume():
    user_id = get_jwt_identity()
    if request.method == "POST":
        data = request.get_json()
        if not data:
            return {"message": "Resume details are required"}, 400
        resumeName = data.get("resumeName")
        category = data.get("category")
        url = data.get("url")
        if not resumeName or not category or not url:
            return {"message": "All resume details are required"}, 400
        resumes = db["resumes"]
        resumes.insert_one({
            "user_id": user_id,
            "resumeName": resumeName,
            "category": category,
            "url": url,
            "date": datetime.now().strftime("%d/%m/%Y")
        })
        return {"message": "Resume successfully saved"}, 201 
    resumes = db["resumes"]
    user_resumes = resumes.find({
        "user_id": user_id
    })
    resume_list = []

    for resume in user_resumes:
        resume["_id"] = str(resume["_id"])
        resume_list.append(resume)

    return resume_list, 200

@resume_bp.route("/resumes/<resume_id>",methods=["DELETE"])
@jwt_required()
def deleteResume(resume_id):
    user_id=get_jwt_identity()
    resumes=db["resumes"]
    result=resumes.delete_one({
        "_id":ObjectId(resume_id),
        "user_id":user_id
    })
    if result.deleted_count==1:
        return {"message":"Resume deleted successfully"},200
    return {"message":"Resume not found"},404