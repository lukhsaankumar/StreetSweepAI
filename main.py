from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Database import create_user, create_ticket, resolve_ticket

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "StreetSweepAI Backend"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
