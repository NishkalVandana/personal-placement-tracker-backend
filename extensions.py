from pymongo import MongoClient
from dotenv import load_dotenv
import os
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
try:
    client.admin.command("ping")
    print("MongoDB connected successfully!")
except Exception as e:
    print("MongoDB connection failed:", e)
db = client["placement_tracker"]
users=db["users"]