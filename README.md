# StreetSweepAI

A community-driven litter reporting and cleanup platform built at DeltaHacks 12.

## Live Demo
https://streetsweepai.vercel.app/

## Tech Stack
- Backend: FastAPI (Python), Uvicorn
- Database: MongoDB Atlas
- Storage: Cloudinary (image CDN)
- Auth: JWT (see auth.py), bcrypt for password hashing
- AI: Google Gemini for image classification (see tickets.py classify endpoint)
- Frontend: React/TypeScript CORS enabled on backend
- Deployment: Frontend deployed on Vercel, Backend deployed on Railway

## Data Sources
- Toronto traffic camera metadata: https://data.urbandatacentre.ca/catalogue/city-toronto-traffic-cameras
	- Used to locate camera latitude/longitude and intersection name during ingestion (ingest_general.py).
- Test images: local folder testImages/ (ignored in git).

## Running Backend Locally
1) Create and activate a venv.
2) `pip install -r requirements.txt`
3) Set environment variables (see .env.example pattern):
	 - MONGO_URI
	 - CLOUDINARY_URL
	 - GEMINI_API_KEY (for classify endpoint)
4) `uvicorn main:app --reload`

## Created By
- Lukhsaan Elankumaran
- Harry Lu
- Varun Gande
- Andrew Law
