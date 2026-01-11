# StreetSweepAI

Citizen-driven litter reporting platform built at Deltahacks 12.

## Tech Stack
- Backend: FastAPI (Python), Uvicorn
- Database: MongoDB Atlas
- Storage: Cloudinary (image CDN)
- Auth: JWT (see auth.py), bcrypt for password hashing
- AI: Google Gemini for image classification (see tickets.py classify endpoint)
- Frontend: React/TypeScript (frontend/ on Vercel), CORS enabled on backend

## Data Sources
- Toronto traffic camera metadata: https://data.urbandatacentre.ca/catalogue/city-toronto-traffic-cameras
	- Used to locate camera latitude/longitude and intersection name during ingestion (ingest_general.py).
- Test images: local folder testImages/ (ignored in git).

## One-time Ingestion
- Script: ingest_general.py (ignored from git)
- Pulls Toronto camera data, parses filenames `{Number}_s{severity}.png`, uploads to Cloudinary, inserts tickets into MongoDB with camera location as description.
- Example: `python ingest_general.py --limit 5`

## Running Backend Locally
1) Create and activate a virtualenv.
2) `pip install -r requirements.txt`
3) Set environment variables (see .env.example pattern):
	 - MONGO_URI
	 - CLOUDINARY_URL
	 - GEMINI_API_KEY (for classify endpoint)
4) `uvicorn main:app --reload`

## Deployment Notes
- Railway for backend deployment (python main.py / uvicorn main:app)
- Vercel for frontend

## Repo Branches
- backend branch
- frontend branch
