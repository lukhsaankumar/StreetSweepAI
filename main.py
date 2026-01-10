from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from PIL import Image
import io, os, json

from dotenv import load_dotenv
load_dotenv()  # ensure .env is loaded

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"

api = FastAPI()
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def optimize_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_size / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()

@api.post("/api/classify")
async def classify(file: UploadFile = File(...)):
    raw = await file.read()
    optimized = optimize_image(raw)

    prompt = """
You are a city cleanliness inspector.

Given this single CCTV frame, estimate how much visible trash/litter is present.
Return ONLY a JSON object with one key:
- "severity": an integer from 1 to 10
  (1 = very clean, 10 = extremely trashy).

Example:
{"severity": 7}
"""

    image_part = types.Part.from_bytes(data=optimized, mime_type="image/jpeg")

    resp = client.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, image_part],
    )

    text = resp.text.strip()

    try:
        data = json.loads(text)
    except Exception:
        digits = [c for c in text if c.isdigit()]
        sev = int("".join(digits)) if digits else None
        data = {"severity": sev}

    return data
