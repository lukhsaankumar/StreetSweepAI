"""Simple local test runner for /api/classify in main.py.
Requires GOOGLE_API_KEY env var to be set.
"""
import asyncio
import io
import base64
from pathlib import Path
from fastapi import UploadFile
from main import classify


async def run_test() -> None:
    base_dir = Path(__file__).resolve().parent
    cctv_dir = base_dir / "cctv"
    images = sorted([p for p in cctv_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    if not images:
        print("No images found in cctv folder.")
        return

    img_path = images[0]
    print(f"Using image: {img_path.name}")

    # Build an UploadFile compatible object for the FastAPI handler.
    file_bytes = img_path.read_bytes()
    upload = UploadFile(filename=img_path.name, file=io.BytesIO(file_bytes))

    result = await classify(file=upload)
    severity = result.get("severity")
    print(f"Severity: {severity}")

    img_b64 = result.get("image_base64")
    if img_b64:
        img_bytes = base64.b64decode(img_b64)
        output_path = base_dir / "output.jpg"
        output_path.write_bytes(img_bytes)
        print(f"Wrote image to: {output_path}")
    else:
        print("No image_base64 in response.")


if __name__ == "__main__":
    asyncio.run(run_test())
