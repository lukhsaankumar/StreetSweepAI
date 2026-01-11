import threading
from watchers import watch_ticket_inserts
from Database import tickets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from Database import create_user, create_ticket, resolve_ticket, users, tickets
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import base64
import io

load_dotenv()

# Configure Cloudinary
cloudinary.config(cloudinary_url=os.getenv("CLOUDINARY_URL"))

app = FastAPI()

@app.on_event("startup")
def start_watchers():
    t = threading.Thread(
        target=watch_ticket_inserts,
        args=(tickets,),
        daemon=True
    )
    t.start()


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class TicketRequest(BaseModel):
    image_url: str = ""  # optional URL fallback
    image_base64: str = None  # optional base64 image (data URI or raw)
    location: dict  # {"lat": 43.77, "lon": -79.23}
    severity: int  # 1-10 scale
    description: str
    claimed: bool = False  # whether ticket is claimed by a user

class UserRequest(BaseModel):
    name: str
    email: str
    password: str

class ResolveTicketRequest(BaseModel):
    ticket_id: str
    user_id: str

@app.get("/")
def read_root():
    return {"message": "StreetSweepAI Backend"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# ==================== TICKET ENDPOINTS ====================

@app.post("/create-ticket")
def create_ticket_endpoint(ticket: TicketRequest):
    """Create a ticket from Gemini analysis results. Uploads base64 image to Cloudinary if provided."""
    try:
        image_url = ticket.image_url or ""
        
        # If base64 image provided, upload to Cloudinary
        if ticket.image_base64:
            data = ticket.image_base64
            
            # Remove data URI prefix if present
            if data.startswith("data:"):
                data = data.split(",", 1)[1]
            
            # Decode base64 to bytes
            img_bytes = base64.b64decode(data)
            
            # Size validation (10 MB max)
            MAX_SIZE = 10_000_000
            if len(img_bytes) > MAX_SIZE:
                return {"error": f"Image too large (max {MAX_SIZE} bytes)"}
            
            # Upload to Cloudinary
            try:
                upload_response = cloudinary.uploader.upload(
                    io.BytesIO(img_bytes),
                    resource_type="image",
                    folder="streetsweep"  # organize in folder
                )
                image_url = upload_response.get("secure_url")
            except Exception as e:
                return {"error": f"Cloudinary upload failed: {str(e)}"}
        
        # Create ticket with image URL (Cloudinary or fallback)
        ticket_id = create_ticket(
            image_url=image_url,
            location=ticket.location,
            severity=ticket.severity,
            description=ticket.description,
            claimed=ticket.claimed
        )
        
        return {
            "ticket_id": ticket_id,
            "image_url": image_url,
            "severity": ticket.severity,
            "description": ticket.description,
            "claimed": ticket.claimed,
            "resolved": False
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/tickets")
def get_all_tickets():
    """Get all tickets (resolved and unresolved)."""
    try:
        all_tickets = list(tickets.find({}))
        # Convert ObjectId to string for JSON
        for ticket in all_tickets:
            ticket["_id"] = str(ticket["_id"])
        return {"tickets": all_tickets}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    """Get a specific ticket by ID."""
    try:
        ticket = tickets.find_one({"_id": ObjectId(ticket_id)})
        if ticket:
            ticket["_id"] = str(ticket["_id"])
            return ticket
        return {"error": "Ticket not found"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/resolve-ticket")
def resolve_ticket_endpoint(data: ResolveTicketRequest):
    """Mark a ticket as resolved."""
    try:
        success = resolve_ticket(data.ticket_id, data.user_id)
        if success:
            return {"message": "Ticket resolved", "ticket_id": data.ticket_id, "resolved": True}
        return {"error": "Failed to resolve ticket"}
    except Exception as e:
        return {"error": str(e)}

# ==================== USER ENDPOINTS ====================

@app.post("/create-user")
def create_user_endpoint(user: UserRequest):
    """Create a new user (volunteer or reporter)."""
    try:
        user_id = create_user(
            name=user.name,
            email=user.email,
            password=user.password
        )
        return {
            "user_id": user_id,
            "name": user.name,
            "email": user.email
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/users/{user_id}")
def get_user(user_id: str):
    """Get user info by ID."""
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if user:
            user["_id"] = str(user["_id"])
            user.pop("password_hash", None)  # Don't return password hash
            return user
        return {"error": "User not found"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/users")
def get_all_users():
    """Get all users."""
    try:
        all_users = list(users.find())
        for user in all_users:
            user["_id"] = str(user["_id"])
            user.pop("password_hash", None)  # Don't return password hashes
        return {"users": all_users}
    except Exception as e:
        return {"error": str(e)}
