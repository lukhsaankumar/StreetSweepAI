"""
Pipeline Demo for StreetSweepAI

Uses pre-captured demo images with known severities to demonstrate
the ticket creation workflow without requiring live classification.

Usage:
    python pipeline_demo.py           # Process all demo images
    python pipeline_demo.py -1        # Process only DEMO1
    python pipeline_demo.py -2        # Process only DEMO2
    python pipeline_demo.py -1 -2 -3  # Process DEMO1, DEMO2, and DEMO3
"""

import sys
import re
import json
import os
import io
from pathlib import Path
from dotenv import load_dotenv
import requests
import cloudinary
import cloudinary.uploader
from Database import create_ticket

load_dotenv()

# Configure Cloudinary - parse URL manually like ingestion script
cloudinary_url = os.getenv("CLOUDINARY_URL")
if not cloudinary_url:
    raise ValueError("CLOUDINARY_URL not found in environment variables")

# Parse cloudinary:// URL format manually
match = re.match(r"cloudinary://([^:]+):([^@]+)@(.+)", cloudinary_url)
if match:
    api_key, api_secret, cloud_name = match.groups()
    cloudinary.config(api_key=api_key, api_secret=api_secret, cloud_name=cloud_name)
else:
    cloudinary.config(cloudinary_url=cloudinary_url)

BASE_DIR = Path(__file__).resolve().parent
DEMOIMAGES_DIR = BASE_DIR / "demoimages"

# Toronto camera metadata URL
CAMERA_JSON_URL = "https://opendata.toronto.ca/transportation/tmc/rescucameraimages/Data/tmcearthcameras.json"


def fetch_camera_locations():
    """
    Fetches camera location data from Toronto Open Data.
    Returns dict mapping camera number to location data.
    """
    print("Fetching camera location data...")
    try:
        response = requests.get(CAMERA_JSON_URL, timeout=30)
        response.raise_for_status()
        
        # Extract JSON from callback wrapper
        # Format: jsonTMCEarthCamerasCallback({...data...});
        json_text = response.text.strip()
        
        if json_text.startswith("jsonTMCEarthCamerasCallback("):
            # Remove callback wrapper: extract content between ( and );
            start = json_text.index("(") + 1
            end = json_text.rindex(")")
            json_text = json_text[start:end]
        
        data = json.loads(json_text)
        cameras = data.get("Data", [])
        
        # Create lookup dict: number -> location info
        camera_map = {}
        for camera in cameras:
            number = camera.get("Number")
            camera_map[number] = {
                "name": camera.get("Name", f"Camera {number}"),
                "latitude": float(camera.get("Latitude", 0)),
                "longitude": float(camera.get("Longitude", 0))
            }
        
        print(f"✓ Loaded {len(camera_map)} camera locations")
        return camera_map
        
    except Exception as e:
        print(f"✗ Error fetching camera data: {e}")
        return {}


def parse_demo_filename(filename: str):
    """
    Parses demo image filename to extract metadata.
    Format: {Number}_DEMO{Demo#}_S{Severity}.png/jpg
    Example: 8015_DEMO1_S5.png
    
    Returns dict with: number, demo_num, severity, or None if not a severity file
    """
    # Skip OG (original) files
    if "_OG." in filename:
        return None
    
    # Match pattern: {Number}_DEMO{Demo#}_S{Severity}
    pattern = r"^(\d+)_DEMO(\d+)_S(\d+)\.(png|jpg)$"
    match = re.match(pattern, filename)
    
    if not match:
        return None
    
    return {
        "number": match.group(1),
        "demo_num": int(match.group(2)),
        "severity": int(match.group(3)),
        "extension": match.group(4)
    }


def process_demo_images(selected_demos=None):
    """
    Processes demo images and creates tickets.
    
    Args:
        selected_demos: List of demo numbers to process (e.g., [1, 2, 3])
                       If None, processes all demos
    """
    print("=" * 60)
    print("STREETSWEEP AI DEMO PIPELINE")
    print("=" * 60)
    
    # Fetch camera locations
    camera_map = fetch_camera_locations()
    
    if not camera_map:
        print("Cannot proceed without camera location data")
        return
    
    # Get all demo images
    if not DEMOIMAGES_DIR.exists():
        print(f"Demo images directory not found: {DEMOIMAGES_DIR}")
        return
    
    demo_files = sorted(DEMOIMAGES_DIR.iterdir())
    print(f"\nFound {len(demo_files)} files in demoimages/")
    
    # Parse and filter demo files
    demo_images_by_demo = {}  # Group by demo number
    for file_path in demo_files:
        if not file_path.is_file():
            continue
        
        metadata = parse_demo_filename(file_path.name)
        if not metadata:
            continue
        
        # Filter by selected demos if specified
        if selected_demos and metadata["demo_num"] not in selected_demos:
            continue
        
        demo_num = metadata["demo_num"]
        severity = metadata["severity"]
        
        # Keep only the highest severity for each demo
        if demo_num not in demo_images_by_demo:
            demo_images_by_demo[demo_num] = {
                "path": file_path,
                "metadata": metadata
            }
        else:
            # Replace if this one has higher severity
            if severity > demo_images_by_demo[demo_num]["metadata"]["severity"]:
                demo_images_by_demo[demo_num] = {
                    "path": file_path,
                    "metadata": metadata
                }
    
    # Convert to list (one per demo, highest severity only)
    demo_images = list(demo_images_by_demo.values())
    
    if not demo_images:
        print("No demo images found matching criteria")
        return
    
    print(f"Processing {len(demo_images)} demo images...")
    if selected_demos:
        print(f"Selected demos: {sorted(selected_demos)}")
    else:
        print("Processing all demos")
    
    print()
    
    # Process each demo image
    stats = {
        "processed": 0,
        "tickets_created": 0,
        "errors": 0,
        "ticket_ids": []
    }
    
    for idx, demo in enumerate(demo_images, 1):
        file_path = demo["path"]
        meta = demo["metadata"]
        
        camera_number = meta["number"]
        demo_num = meta["demo_num"]
        severity = meta["severity"]
        
        print(f"[{idx}/{len(demo_images)}] Processing: {file_path.name}")
        print(f"  Camera: {camera_number}")
        print(f"  Demo: {demo_num}")
        print(f"  Severity: {severity}/10")
        
        try:
            # Get location from camera map
            camera_info = camera_map.get(camera_number)
            if not camera_info:
                print(f"  ✗ Camera {camera_number} not found in location data")
                stats["errors"] += 1
                continue
            
            location_name = camera_info["name"]
            latitude = camera_info["latitude"]
            longitude = camera_info["longitude"]
            
            print(f"  Location: {location_name}")
            print(f"  Coordinates: ({latitude}, {longitude})")
            
            # Upload to Cloudinary
            print(f"  → Uploading to Cloudinary...")
            try:
                upload_response = cloudinary.uploader.upload(
                    str(file_path),
                    resource_type="image",
                    folder="streetsweep",
                )
                image_url = upload_response.get("secure_url")
                print(f"  ✓ Uploaded to Cloudinary")
            except Exception as upload_error:
                print(f"  ✗ Upload failed: {upload_error}")
                stats["errors"] += 1
                continue
            
            # Create ticket
            print(f"  → Creating ticket...")
            ticket_id = create_ticket(
                image_url=image_url,
                location={"lat": latitude, "lon": longitude},
                severity=severity,
                description=f"DEMO{demo_num}: {location_name}",
                claimed=False
            )
            
            print(f"  ✓ Ticket created: {ticket_id}")
            stats["processed"] += 1
            stats["tickets_created"] += 1
            stats["ticket_ids"].append(ticket_id)
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            stats["errors"] += 1
            print()
            continue
    
    # Print summary
    print("=" * 60)
    print("DEMO PIPELINE COMPLETE - Summary")
    print("=" * 60)
    print(f"Images processed:   {stats['processed']}")
    print(f"Tickets created:    {stats['tickets_created']}")
    print(f"Errors:             {stats['errors']}")
    print("=" * 60)


if __name__ == "__main__":
    # Parse command-line arguments for demo selection
    selected_demos = None
    
    if len(sys.argv) > 1:
        selected_demos = []
        for arg in sys.argv[1:]:
            if arg.startswith("-"):
                try:
                    demo_num = int(arg[1:])
                    selected_demos.append(demo_num)
                except ValueError:
                    print(f"Warning: Invalid demo number '{arg}', ignoring")
        
        if not selected_demos:
            selected_demos = None  # Process all if no valid demos specified
    
    # Run the demo pipeline
    process_demo_images(selected_demos)