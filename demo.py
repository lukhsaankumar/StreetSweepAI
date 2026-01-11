"""
Demo script to test the StreetSweepAI API endpoints
Run this after starting the server with: uvicorn main:app --reload
"""

import requests
import json
import base64
from pathlib import Path

# API base URL
BASE_URL = "http://127.0.0.1:8000"

# Sample data for creating a ticket WITH base64 image
def create_ticket_data_with_image(image_path=None):
    """Create ticket data. If image_path provided, encode as base64."""
    data = {
        "image_url": "",  # Empty since we're using base64
        "image_base64": None,
        "location": {
            "lat": 43.6629,
            "lon": -79.3957
        },
        "severity": 7,  # 1-10 scale
        "description": "Large pile of trash and debris on Main Street corner test image",
        "claimed": False
    }
    
    # If image path provided, encode as base64
    if image_path and Path(image_path).exists():
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        b64_string = base64.b64encode(img_bytes).decode()
        # Add data URI prefix for clarity
        data["image_base64"] = f"data:image/jpeg;base64,{b64_string}"
    
    return data

# Sample data for creating a ticket WITHOUT image (fallback)
ticket_data_no_image = {
    "image_url": "https://example.com/street_trash.jpg",
    "image_base64": None,
    "location": {
        "lat": 43.6629,
        "lon": -79.3957
    },
    "severity": 5,
    "description": "Small litter on sidewalk",
    "claimed": False
}

# Sample data for creating a user
user_data = {
    "name": "John Doe",
    "email": "john@example.com",
    "password": "password123",
    "role": "user",
    "location": {"lat": 43.6629, "lon": -79.3957}
}

def test_health():
    """Test if the server is running."""
    print("\n=== Testing Health ===")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_create_ticket(image_path=None):
    """Test creating a ticket. If image_path provided, uploads as base64."""
    print("\n=== Creating Ticket ===")
    try:
        ticket_data = create_ticket_data_with_image(image_path) if image_path else ticket_data_no_image
        response = requests.post(f"{BASE_URL}/create-ticket", json=ticket_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if "ticket_id" in result:
            print(f"✅ Ticket created successfully! ID: {result['ticket_id']}")
            if "image_url" in result and result["image_url"]:
                print(f"📸 Image URL: {result['image_url']}")
            return result["ticket_id"]
        else:
            print(f"❌ Failed to create ticket")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_get_tickets():
    """Test getting all tickets."""
    print("\n=== Getting All Tickets ===")
    try:
        response = requests.get(f"{BASE_URL}/tickets")
        print(f"Status: {response.status_code}")
        result = response.json()
        
        if "tickets" in result:
            print(f"✅ Found {len(result['tickets'])} tickets")
            for ticket in result['tickets']:
                print(f"  - ID: {ticket['_id']}, Severity: {ticket['severity']}, Priority: {ticket['priority']}")
        else:
            print(f"Response: {result}")
    except Exception as e:
        print(f"Error: {e}")

def test_create_user():
    """Test creating a user."""
    print("\n=== Creating User ===")
    try:
        response = requests.post(f"{BASE_URL}/create-user", json=user_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if "user_id" in result:
            print(f"✅ User created successfully! ID: {result['user_id']}")
            return result["user_id"]
        else:
            print(f"❌ Failed to create user")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_resolve_ticket(ticket_id, user_id):
    """Test resolving a ticket."""
    print(f"\n=== Resolving Ticket ===")
    try:
        resolve_data = {
            "ticket_id": ticket_id,
            "user_id": user_id
        }
        response = requests.post(f"{BASE_URL}/resolve-ticket", json=resolve_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200:
            print(f"✅ Ticket resolved successfully!")
        else:
            print(f"❌ Failed to resolve ticket")
    except Exception as e:
        print(f"Error: {e}")

def main():
    """Run all demo tests."""
    import sys
    
    print("🚀 StreetSweepAI API Demo")
    print("=" * 50)
    
    # Test health
    if not test_health():
        print("\n❌ Server is not running! Start it with: uvicorn main:app --reload")
        return
    
    # Create a user
    user_id = test_create_user()
    
    # Create a ticket without image (fallback)
    print("\n--- Testing Ticket Creation WITHOUT Image ---")
    ticket_id = test_create_ticket()
    
    # Create a ticket WITH image if image path provided as command-line arg
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"\n--- Testing Ticket Creation WITH Image: {image_path} ---")
        ticket_id_with_image = test_create_ticket(image_path)
    
    # Get all tickets
    test_get_tickets()
    
    # Resolve ticket if we have both IDs
    if ticket_id and user_id:
        test_resolve_ticket(ticket_id, user_id)
        
        # Check tickets again to see resolved status
        print("\n=== Checking Tickets After Resolution ===")
        test_get_tickets()
    
    print("\n" + "=" * 50)
    print("✅ Demo completed!")
    print("\n📝 To test image upload, run:")
    print("   python demo.py /path/to/image.jpg")

if __name__ == "__main__":
    main()
