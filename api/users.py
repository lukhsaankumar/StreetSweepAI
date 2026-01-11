from fastapi import APIRouter, HTTPException, status, Response
from Database import UserRequest, Users  # your existing request model [file:413]
from users_service import register_user, fetch_user_by_id, fetch_all_users
from pydantic import BaseModel
from auth import verify_password, create_access_token

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str
# ==================== AUTHENTICATION ENDPOINTS =============
@router.post("/login")
def login(data: LoginRequest, response: Response):
    user = Users.find_one({"email": data.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    hashed = user.get("password_hash")
    if not hashed or not verify_password(data.password, hashed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    response.set_cookie(key="user_id", value=str(user["_id"]), httponly=True, samesite="lax")

    token = create_access_token(str(user["_id"]))
    return {"access_token": token, "token_type": "bearer"}

# ==================== USER ENDPOINTS ====================

@router.post("/create-user")
def create_user_endpoint(user: UserRequest):
    """Create a new user (volunteer or reporter)."""
    try:
        return register_user(user)
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/logout")
def logout(response: Response):
    """Logout user by clearing the cookie."""
    response.delete_cookie(key="user_id")
    return {"message": "Logged out successfully"}

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
