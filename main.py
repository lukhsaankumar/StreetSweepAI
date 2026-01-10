from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from Database import create_user, create_ticket, resolve_ticket, users, tickets
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

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
    image_url: str
    location: dict  # {"lat": 43.77, "lon": -79.23}
    severity: int  # 1-10 scale
    priority: str  # "low", "medium", "high"
    description: str

class UserRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "volunteer"  # "volunteer" or "reporter"
    location: dict = None

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
    """Create a ticket from Gemini analysis results."""
    try:
        ticket_id = create_ticket(
            image_url=ticket.image_url,
            location=ticket.location,
            severity=ticket.severity,
            priority=ticket.priority,
            description=ticket.description
        )
        
        return {
            "ticket_id": ticket_id,
            "severity": ticket.severity,
            "priority": ticket.priority,
            "description": ticket.description,
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
            password=user.password,
            role=user.role,
            location=user.location
        )
        return {
            "user_id": user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role
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
