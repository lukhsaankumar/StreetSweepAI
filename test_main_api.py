"""Simple local test runner for /api/classify in main.py.
Requires GOOGLE_API_KEY env var to be set.
"""
import asyncio
import io
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

    img_path = images[7]
    print(f"Using image: {img_path.name}")

    # Build an UploadFile compatible object for the FastAPI handler.
    file_bytes = img_path.read_bytes()
    upload = UploadFile(filename=img_path.name, file=io.BytesIO(file_bytes))

    result = await classify(file=upload)
    print("API response:", result)


if __name__ == "__main__":
    asyncio.run(run_test())
