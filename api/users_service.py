# users_service.py
from bson.objectid import ObjectId
from api.Database import create_user, users, UserRequest  # [file:413]

def register_user(user: UserRequest) -> dict:
    user_id = create_user(
        name=user.name,
        email=user.email,
        password=user.password,
    )
    return {
        "user_id": user_id,
        "name": user.name,
        "email": user.email,
    }

def fetch_user_by_id(user_id: str) -> dict | None:
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return None
    user["_id"] = str(user["_id"])
    user.pop("password_hash", None)
    return user

def fetch_all_users() -> list[dict]:
    all_users = list(users.find())
    for user in all_users:
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
    return all_users
