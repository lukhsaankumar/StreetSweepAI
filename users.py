from fastapi import APIRouter
from Database import UserRequest  # your existing request model [file:413]
from users_service import register_user, fetch_user_by_id, fetch_all_users

router = APIRouter()

# ==================== USER ENDPOINTS ====================

@router.post("/create-user")
def create_user_endpoint(user: UserRequest):
    """Create a new user (volunteer or reporter)."""
    try:
        return register_user(user)
    except Exception as e:
        return {"error": str(e)}

@router.get("/users/{user_id}")
def get_user(user_id: str):
    """Get user info by ID."""
    try:
        user = fetch_user_by_id(user_id)
        if user:
            return user
        return {"error": "User not found"}
    except Exception as e:
        return {"error": str(e)}

@router.get("/users")
def get_all_users():
    """Get all users."""
    try:
        return {"users": fetch_all_users()}
    except Exception as e:
        return {"error": str(e)}
