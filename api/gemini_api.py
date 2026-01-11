from google import genai
from google.genai import types
from PIL import Image
import io, os, json, base64
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"


def optimize_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_size / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


def classify_image(image_bytes: bytes) -> dict:
    """
    Classify trash severity in an image using Gemini.
    Returns: {"severity": int | None, "image_base64": str}
    """
    optimized = optimize_image(image_bytes)

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

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "severity": data.get("severity"),
        "image_base64": image_b64,
    }
