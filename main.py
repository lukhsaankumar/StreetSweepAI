from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from users import router as users_router
from tickets import router as tickets_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(tickets_router)
