from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime

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
def create_user(name, email, password, role="volunteer", skills=None, location=None):
    if skills is None:
        skills = []

    # Simple password hash (never store plain passwords)
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    user_data = {
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "role": role,                # "volunteer" or "reporter"
        "skills": skills,
        "location": location,        # {"lat": 43.77, "lon": -79.23}
        "availability": [],
        
        "tickets_reported": [],
        "tickets_completed": []
    }

    result = users.insert_one(user_data)
    return str(result.inserted_id)

def create_ticket(image_url, location, bounding_boxes):

    ticket_data = {
        "image_url": image_url,
        "location": location,
        "bounding_boxes": bounding_boxes,
        "timestamp": datetime.utcnow(),
        "status": "pending",       # could also be "resolved"
        "volunteer_id": None       # will be set when a volunteer picks it up
    }

    result = tickets.insert_one(ticket_data)

    return str(result.inserted_id)

# Example usage:
#user_id = create_user("Andrew Wang", "andrew@example.com", "password123", skills=["Python", "OpenCV"])
#print("New user created with ID:", user_id)
create_ticket("testurl", [4.2, -39], 10,)
