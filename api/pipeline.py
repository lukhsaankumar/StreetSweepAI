from pathlib import Path
from dotenv import load_dotenv
from gemini_api import classify_image
from Database import create_ticket, tickets

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


CCTV_DIR = BASE_DIR / "cctv"

for cctv_file in CCTV_DIR.iterdir():
    if not cctv_file.is_file():
        continue
    try:
        with open(cctv_file, "rb") as f:
            severity = classify_image(f.read()).get("severity", None)
        print(f"File: {cctv_file.name}, Severity: {severity}")
        if severity is None:
            print(f"Could not classify severity for {cctv_file.name}, skipping...")
            continue
        image_url = f"http://example.com/cctv/{cctv_file.name}"
        location = {"lat": 43.77, "lon": -79.23}  # Placeholder location - can probably get from either eventual DB or filename
        if severity >= 8:
            print(f"High trash severity detected in {cctv_file.name}: {severity}")
            ticket_id = create_ticket(
                image_url=image_url,
                location=location,
                severity=severity,
                priority="high" if severity >= 9 else "medium",
                description="placeholder description"
            )
            print(f"Ticket {ticket_id} created for {cctv_file.name}")
        elif severity > 5:
            print(f"Mild trash severity returned for {cctv_file.name}")
            ticket_id = create_ticket(
                image_url=image_url,
                location=location,
                severity=severity,
                priority="low",
                description="placeholder description"
            )
            print(f"Ticket {ticket_id} created for {cctv_file.name}")
        else:
            print(f"Low trash severity for {cctv_file.name}")
    except Exception as e:
        print(f"Error processing file {cctv_file.name}: {e}")