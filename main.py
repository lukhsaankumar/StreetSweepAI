from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from PIL import Image
import io, os, json, base64
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)
MODEL_NAME = "google/gemini-flash-1.5"  # Paid but fast, ~$0.075 per 1M tokens

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
    # original bytes (for returning to frontend)
    raw = await file.read()

    # smaller bytes (for Gemini only, to save tokens)
    optimized = optimize_image(raw)

    # Encode optimized image to base64 for OpenRouter
    optimized_b64 = base64.b64encode(optimized).decode("utf-8")

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """You are a city cleanliness inspector.

Given this single CCTV frame, estimate how much visible trash/litter is present.
Return ONLY a JSON object with one key:
- "severity": an integer from 1 to 10
  (1 = very clean, 10 = extremely trashy).

Example:
{"severity": 7}"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{optimized_b64}"
                        }
                    }
                ]
            }
        ]
    )

    text = resp.choices[0].message.content.strip()
    try:
        data = json.loads(text)
    except Exception:
        digits = [c for c in text if c.isdigit()]
        sev = int("".join(digits)) if digits else None
        data = {"severity": sev}

    # Return ORIGINAL image (not generated) as base64
    raw_b64 = base64.b64encode(raw).decode("utf-8")

    return {
        "severity": data.get("severity"),
        "image_base64": raw_b64,
    }
