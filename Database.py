from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
from bson.objectid import ObjectId 
import bcrypt
from pydantic import BaseModel

# Load .env file
load_dotenv()  

# Get the URI
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise Exception("MONGO_URI not found! Check your .env file and make sure it’s in project root.")

# Connect to MongoDB
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)  # 5s timeout

try:
    client.admin.command("ping")
    print("Connected to MongoDB!")
except Exception as e:
    print("Could not connect:", e)


# DATABASE AND COLLECTION NAMES
client = MongoClient(MONGO_URI)
db = client["ProjectDB"]        # Your database
users = db["users"]  
tickets = db["tickets"]


# EDITING THE DATABASE
def create_user(name, email, password):
    # password crypt
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    user_data = {
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "availability": [],
        "points": 0
    }

    result = users.insert_one(user_data)
    return str(result.inserted_id)

def create_ticket(image_url, location, severity, description, claimed=False, priority: str | None = None):
    ticket_data = {
        "image_url": image_url,
        "location": location,
        "severity": severity,           # 1-10 scale
        "description": description,
        "claimed": claimed,             # whether user claimed the ticket
        "timestamp": datetime.now(timezone.utc),
        "resolved": False,
        "priority": priority
    }
    result = tickets.insert_one(ticket_data)
    return str(result.inserted_id)

def resolve_ticket(ticket_id, user_id=None):
    """Mark a ticket as resolved (set resolved=true)."""
    
    # Update user statistics if user_id provided
    if user_id:
        users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"points": 1}}
        )
    
    # Mark ticket as resolved
    result = tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": {"resolved": True}}
    )
    
    return result.modified_count == 1

class UserRequest(BaseModel):
    name: str
    email: str
    password: str

Users = users

#creating a user:
#user_id = create_user("Andrew Wang", "andrew@example.com", "password123", skills=["Python", "OpenCV"])

#creating a ticket:
#create_ticket("testurl", [4.2, -39], 10,)
