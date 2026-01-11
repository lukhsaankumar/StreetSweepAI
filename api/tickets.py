# tickets.py
import threading
import os
import base64
import io

from auth import get_current_user

from bson.objectid import ObjectId
from dotenv import load_dotenv

import cloudinary
import cloudinary.uploader

from watchers import watch_ticket_inserts
from Database import create_ticket, resolve_ticket, tickets
from pydantic import BaseModel

from fastapi import APIRouter, Depends, UploadFile, File
from auth import get_current_user
from gemini_api import classify_image, compare_image, get_insight


load_dotenv()

# Configure Cloudinary
cloudinary.config(cloudinary_url=os.getenv("CLOUDINARY_URL"))

router = APIRouter()

# ---------- background watcher ----------

@router.on_event("startup")
def start_watchers():
    t = threading.Thread(
        target=watch_ticket_inserts,
        args=(tickets,),
        daemon=True,
    )
    t.start()

# ---------- request models ----------

class TicketRequest(BaseModel):
    image_url: str = ""         # optional URL fallback
    image_base64: str | None = None  # optional base64 image (data URI or raw)
    location: dict              # {"lat": 43.77, "lon": -79.23}
    severity: int               # 1-10 scale
    description: str
    claimed: bool = False       # whether ticket is claimed by a user

class ResolveTicketRequest(BaseModel):
    ticket_id: str
    user_id: str

# ---------- endpoints ----------

@router.get("/")
def read_root():
    return {"message": "StreetSweepAI Backend"}

@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.post("/create-ticket")
def create_ticket_endpoint(ticket: TicketRequest, current_user: dict = Depends(get_current_user)):
    """
    Create a ticket from Gemini analysis results.
    Uploads base64 image to Cloudinary if provided.
    """
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
                    folder="streetsweep",  # organize in folder
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
            claimed=ticket.claimed,
        )

        return {
            "ticket_id": ticket_id,
            "image_url": image_url,
            "severity": ticket.severity,
            "description": ticket.description,
            "claimed": ticket.claimed,
            "resolved": False,
        }

    except Exception as e:
        return {"error": str(e)}

@router.get("/tickets")
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

@router.get("/tickets/{ticket_id}")
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

@router.post("/resolve-ticket")
def resolve_ticket_endpoint(data: ResolveTicketRequest, current_user: dict = Depends(get_current_user)):
    """Mark a ticket as resolved."""
    try:
        success = resolve_ticket(data.ticket_id, data.user_id)
        if success:
            return {
                "message": "Ticket resolved",
                "ticket_id": data.ticket_id,
                "resolved": True,
            }
        return {"error": "Failed to resolve ticket"}
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/classify")
async def classify_endpoint(
    file: UploadFile = File(...),
):
    """
    Classify a user-uploaded image for trash severity.
    """
    raw = await file.read()
    return classify_image(raw)

@router.post("/compare")
async def compare_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
):
    """
    Compare two user-uploaded images for similarity.
    """
    raw1 = await file1.read()
    raw2 = await file2.read()
    return compare_image(raw1, raw2)
# comment so i can push but i did these compare api in the last commit!!

@router.get("/insight")
def get_insight_endpoint():
    """
    Get the latest insight summary.
    """
    try:
        insight = get_insight()
        return {"insight": insight}
    except Exception as e:
        return {"error": str(e)}