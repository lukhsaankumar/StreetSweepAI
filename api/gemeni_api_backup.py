import io
import os
import json
import base64
from dotenv import load_dotenv
from collections import Counter
from PIL import Image
import requests  # for OpenRouter HTTP calls


load_dotenv()

# --- OpenRouter + Gemini config ---

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Use a Gemini model exposed via OpenRouter
MODEL_NAME = "google/gemini-2.0-flash-001"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _openrouter_chat(messages, max_tokens: int | None = None) -> str:
    """
    Call OpenRouter chat completion API and return the text content.
    messages: list of {"role": "system"|"user"|"assistant", "content": str}
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


# --- Image helpers ---


def optimize_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_size / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


# --- Classification ---


def classify_image(image_bytes: bytes) -> dict:
    """
    Classify trash severity in an image using Gemini via OpenRouter.
    Returns: {"severity": int | None, "image_base64": str}
    """
    # Keep this in case you later wire image support through OpenRouter
    _ = optimize_image(image_bytes)

    prompt = """
You are a city cleanliness inspector.
Estimate how much visible trash/litter is present in a CCTV frame.
Return ONLY a JSON object with one key:
- "severity": an integer from 1 to 10
(1 = very clean, 10 = extremely trashy).

Example:
{"severity": 7}
"""

    text = _openrouter_chat(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=64,
    )

    text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        digits = [c for c in text if c.isdigit()]
        sev = int("".join(digits)) if digits else None
        data = {"severity": sev}

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "severity": data.get("severity"),
        "image_base64": image_b64,
    }


# --- Before / after comparison ---


def compare_image(before_bytes: bytes, after_bytes: bytes) -> dict:
    """
    Compare two images (before and after) to verify cleanup.

    Returns:
        {
            "same_location": bool | None,
            "cleanup_successful": bool | None,
        }
    """
    _ = optimize_image(before_bytes)
    _ = optimize_image(after_bytes)

    prompt = """
You are a city cleanliness inspector.

You are given TWO photos:
- Photo A: supposed 'before' image of a location with trash.
- Photo B: supposed 'after' image of the same location after cleanup.

Your tasks:
1. Decide if these two photos show the SAME physical location
   (allowing for different angles, lighting, time of day, and amount of trash).
2. If they are the same location, decide if the amount of visible trash/litter
   in Photo B is clearly LESS than in Photo A (cleanup success).

Return ONLY a JSON object with the following keys:
- "same_location": true or false
- "cleanup_successful": true or false

Example:
{
  "same_location": true,
  "cleanup_successful": true
}
"""

    text = _openrouter_chat(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=128,
    )

    text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        lower = text.lower()
        same = "same location" in lower or "same place" in lower
        cleanup = "less trash" in lower or "cleaner" in lower
        data = {
            "same_location": same,
            "cleanup_successful": cleanup,
        }

    return {
        "same_location": data.get("same_location"),
        "cleanup_successful": data.get("cleanup_successful"),
    }


# --- Ticket insights ---


def generate_insight(tickets: list[dict]) -> str:
    """
    Generate insights from ticket data using Gemini (via OpenRouter).
    Returns a text summary.
    """
    locations = [tuple(t["location"]) for t in tickets]
    severities = [t["severity"] for t in tickets if "severity" in t]

    loc_counts = Counter(locations)
    severity_dist = Counter(severities)

    prompt_data = {
        "total_tickets": len(tickets),
        "top_locations": loc_counts.most_common(10),
        "severity_distribution": severity_dist,
    }
    prompt = (
        "You are a municipal waste planning assistant.\n"
        f"Data summary: {json.dumps(prompt_data)}\n\n"
        "Explain:\n"
        "1) Key problem areas and trends.\n"
        "2) Operational improvements (routing, frequency, scheduling).\n"
        "3) Policy ideas (education, enforcement, infrastructure).\n"
        "Keep it concise and specific."
    )

    text = _openrouter_chat(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    return text.strip()


def get_insight() -> str:
    with open("insight.txt", "r", encoding="utf-8") as f:
        content = f.read()
    return content
