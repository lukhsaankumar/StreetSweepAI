"""
Toronto Street Sweep AI Pipeline

This pipeline monitors traffic cameras from Toronto's Open Data portal,
classifies images for litter severity, and creates tickets for areas 
requiring cleanup.

The pipeline is designed to be modular, allowing easy swapping of image
sources and ticket creation logic for demos and testing.
"""

import os
import io
import json
import time
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dotenv import load_dotenv
import requests

import cloudinary
import cloudinary.uploader

from gemini_api import classify_image, generate_insight
from Database import create_ticket, tickets

load_dotenv()

# Configure Cloudinary
cloudinary.config(cloudinary_url=os.getenv("CLOUDINARY_URL"))

# ==================== IMAGE SOURCE ADAPTERS ====================

class ImageSource:
    """Base class for image sources."""
    
    def get_images(self) -> List[Dict[str, Any]]:
        """
        Returns list of image metadata dictionaries with keys:
        - 'id': unique identifier for the image
        - 'name': human-readable name/location
        - 'image_bytes': raw image bytes
        - 'latitude': optional latitude coordinate
        - 'longitude': optional longitude coordinate
        """
        raise NotImplementedError


class TorontoCCTVSource(ImageSource):
    """Fetches images from Toronto's Open Data traffic cameras."""
    
    def __init__(
        self, 
        camera_json_url: str = "https://opendata.toronto.ca/transportation/tmc/rescucameraimages/Data/tmcearthcameras.json",
        image_url_template: str = "https://opendata.toronto.ca/transportation/tmc/rescucameraimages/CameraImages/loc{number}.jpg"
    ):
        self.camera_json_url = camera_json_url
        self.image_url_template = image_url_template
    
    def get_images(self) -> List[Dict[str, Any]]:
        """Fetches camera data and downloads images."""
        print(f"Fetching camera list from {self.camera_json_url}")
        
        try:
            # Fetch camera metadata
            response = requests.get(self.camera_json_url, timeout=30)
            response.raise_for_status()
            
            # The JSON is wrapped in a callback, extract the actual JSON
            json_text = response.text
            if json_text.startswith("jsonTMCEarthCamerasCallback("):
                json_text = json_text[len("jsonTMCEarthCamerasCallback("):-2]
            
            data = json.loads(json_text)
            cameras = data.get("Data", [])
            
            # Sort by Number parameter
            cameras.sort(key=lambda x: int(x.get("Number", 0)))
            
            print(f"Found {len(cameras)} cameras")
            
            images = []
            for camera in cameras:
                number = camera.get("Number")
                name = camera.get("Name", f"Camera {number}")
                latitude = float(camera.get("Latitude", 0))
                longitude = float(camera.get("Longitude", 0))
                
                # Construct image URL
                image_url = self.image_url_template.format(number=number)
                
                try:
                    # Download image
                    img_response = requests.get(image_url, timeout=10)
                    img_response.raise_for_status()
                    
                    images.append({
                        'id': number,
                        'name': name,
                        'image_bytes': img_response.content,
                        'latitude': latitude,
                        'longitude': longitude,
                    })
                    print(f"✓ Downloaded image for {name} (#{number})")
                    
                except Exception as e:
                    print(f"✗ Failed to download image for {name} (#{number}): {e}")
                    continue
            
            return images
            
        except Exception as e:
            print(f"Error fetching camera data: {e}")
            return []


class LocalDirectorySource(ImageSource):
    """Fetches images from a local directory."""
    
    def __init__(self, directory: Path, default_location: Dict[str, float] = None):
        self.directory = Path(directory)
        self.default_location = default_location or {"lat": 43.77, "lon": -79.23}
    
    def get_images(self) -> List[Dict[str, Any]]:
        """Loads images from local directory."""
        images = []
        
        if not self.directory.exists():
            print(f"Directory {self.directory} does not exist")
            return []
        
        for img_file in sorted(self.directory.iterdir()):
            if not img_file.is_file():
                continue
            
            if img_file.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
                continue
            
            try:
                with open(img_file, 'rb') as f:
                    image_bytes = f.read()
                
                images.append({
                    'id': img_file.stem,
                    'name': img_file.name,
                    'image_bytes': image_bytes,
                    'latitude': self.default_location["lat"],
                    'longitude': self.default_location["lon"],
                })
                print(f"✓ Loaded {img_file.name}")
                
            except Exception as e:
                print(f"✗ Failed to load {img_file.name}: {e}")
                continue
        
        return images


# ==================== TICKET CREATION LOGIC ====================

class TicketCreator:
    """Base class for ticket creation logic."""
    
    def should_create_ticket(self, severity: int) -> bool:
        """Determines if a ticket should be created based on severity."""
        raise NotImplementedError
    
    def create_ticket_data(
        self, 
        image_metadata: Dict[str, Any], 
        severity: int,
        cloudinary_url: str
    ) -> Dict[str, Any]:
        """Creates ticket data dictionary."""
        raise NotImplementedError


class DefaultTicketCreator(TicketCreator):
    """Default ticket creation logic: creates tickets for severity > 4."""
    
    def __init__(self, severity_threshold: int = 4):
        self.severity_threshold = severity_threshold
    
    def should_create_ticket(self, severity: int) -> bool:
        return severity > self.severity_threshold
    
    def create_ticket_data(
        self, 
        image_metadata: Dict[str, Any], 
        severity: int,
        cloudinary_url: str
    ) -> Dict[str, Any]:
        """Creates ticket with location from image metadata."""
        return {
            "image_url": cloudinary_url,
            "location": {
                "lat": image_metadata.get("latitude", 43.77),
                "lon": image_metadata.get("longitude", -79.23)
            },
            "severity": severity,
            "description": f"Litter detected at {image_metadata.get('name', 'Unknown location')}",
            "claimed": False
        }


# ==================== MAIN PIPELINE ====================

class StreetSweepPipeline:
    """Main pipeline for processing images and creating tickets."""
    
    def __init__(
        self,
        image_source: ImageSource,
        ticket_creator: TicketCreator,
        upload_to_cloudinary: bool = True,
        max_images: Optional[int] = None
    ):
        self.image_source = image_source
        self.ticket_creator = ticket_creator
        self.upload_to_cloudinary = upload_to_cloudinary
        self.max_images = max_images
    
    def run(self) -> Dict[str, Any]:
        """
        Runs the pipeline:
        1. Fetch images from source
        2. Classify each image for litter severity
        3. Upload to Cloudinary (if enabled)
        4. Create tickets based on severity threshold
        
        Returns summary statistics.
        """
        print("=" * 60)
        print("STREETSWEEP AI PIPELINE - Starting")
        print("=" * 60)
        
        # Fetch images
        images = self.image_source.get_images()
        
        if self.max_images:
            images = images[:self.max_images]
            print(f"\nLimiting to first {self.max_images} images")
        
        if not images:
            print("No images to process!")
            return {"error": "No images found"}
        
        print(f"\n{len(images)} images ready for processing\n")
        
        # Process each image
        stats = {
            "total_images": len(images),
            "classified": 0,
            "tickets_created": 0,
            "skipped": 0,
            "errors": 0,
            "created_ticket_ids": []
        }
        
        for idx, img_meta in enumerate(images, 1):
            print(f"\n[{idx}/{len(images)}] Processing: {img_meta['name']}")
            
            try:
                # Classify image
                print(f"  → Classifying...")
                classification = classify_image(img_meta['image_bytes'])
                severity = classification.get("severity")
                
                if severity is None:
                    print(f"  ✗ Failed to classify severity")
                    stats["errors"] += 1
                    continue
                
                stats["classified"] += 1
                print(f"  ✓ Severity: {severity}/10")
                
                # Check if ticket should be created
                if not self.ticket_creator.should_create_ticket(severity):
                    print(f"  ⊘ Severity below threshold - skipping")
                    stats["skipped"] += 1
                    continue
                
                # Upload to Cloudinary
                if self.upload_to_cloudinary:
                    print(f"  → Uploading to Cloudinary...")
                    upload_response = cloudinary.uploader.upload(
                        io.BytesIO(img_meta['image_bytes']),
                        resource_type="image",
                        folder="streetsweep",
                    )
                    cloudinary_url = upload_response.get("secure_url")
                    print(f"  ✓ Uploaded")
                else:
                    cloudinary_url = f"local://{img_meta['id']}"
                
                # Create ticket
                print(f"  → Creating ticket...")
                ticket_data = self.ticket_creator.create_ticket_data(
                    img_meta, 
                    severity,
                    cloudinary_url
                )
                
                ticket_id = create_ticket(**ticket_data)
                print(f"  ✓ Ticket created: {ticket_id}")
                
                stats["tickets_created"] += 1
                stats["created_ticket_ids"].append(ticket_id)
                
            except Exception as e:
                print(f"  ✗ Error processing image: {e}")
                stats["errors"] += 1
                continue
        
        # Print summary
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE - Summary")
        print("=" * 60)
        print(f"Total images processed:  {stats['total_images']}")
        print(f"Successfully classified: {stats['classified']}")
        print(f"Tickets created:         {stats['tickets_created']}")
        print(f"Skipped (low severity):  {stats['skipped']}")
        print(f"Errors:                  {stats['errors']}")
        print("=" * 60)
        
        return stats


# ==================== MAIN EXECUTION ====================

def generate_pipeline_insights():
    """
    Generates insights from all tickets in the database.
    Writes the insights to insight.txt file.
    """
    print("\n" + "=" * 60)
    print("GENERATING INSIGHTS")
    print("=" * 60)
    
    try:
        # Fetch all tickets from database
        all_tickets = list(tickets.find({}))
        print(f"Found {len(all_tickets)} tickets in database")
        
        if not all_tickets:
            print("No tickets to analyze")
            return
        
        # Generate insights using Gemini
        print("Generating AI insights...")
        insight = generate_insight(all_tickets)
        
        # Write to file
        with open("insight.txt", "w", encoding="utf-8") as f:
            f.write(insight)
        
        print("✓ Insights saved to insight.txt")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"✗ Error generating insights: {e}")
        print("=" * 60 + "\n")


def run_toronto_cctv_pipeline(max_images: Optional[int] = None):
    """
    Runs the pipeline using Toronto CCTV cameras.
    
    Args:
        max_images: Maximum number of images to process (None for all)
    """
    source = TorontoCCTVSource()
    creator = DefaultTicketCreator(severity_threshold=4)
    
    pipeline = StreetSweepPipeline(
        image_source=source,
        ticket_creator=creator,
        upload_to_cloudinary=True,
        max_images=max_images
    )
    
    return pipeline.run()


def run_local_directory_pipeline(directory: str, max_images: Optional[int] = None):
    """
    Runs the pipeline using images from a local directory.
    
    Args:
        directory: Path to directory containing images
        max_images: Maximum number of images to process (None for all)
    """
    source = LocalDirectorySource(Path(directory))
    creator = DefaultTicketCreator(severity_threshold=4)
    
    pipeline = StreetSweepPipeline(
        image_source=source,
        ticket_creator=creator,
        upload_to_cloudinary=True,
        max_images=max_images
    )
    
    return pipeline.run()


if __name__ == "__main__":
    import datetime
    
    TWO_WEEKS_SECONDS = 14 * 24 * 60 * 60  # 14 days in seconds
    
    print("=" * 60)
    print("STREETSWEEP AI AUTOMATED PIPELINE")
    print("Runs every 2 weeks")
    print("=" * 60)
    print()
    
    while True:
        try:
            # Record start time
            start_time = datetime.datetime.now()
            print(f"\nPipeline started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            # Run the pipeline with Toronto CCTV cameras
            # Limit to first 50 images to avoid excessive API costs
            stats = run_toronto_cctv_pipeline(max_images=50)
            
            # Generate insights after processing
            generate_pipeline_insights()
            
            # Record end time
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            print(f"\n✓ Pipeline completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Duration: {duration}")
            
            # Calculate next run time
            next_run = end_time + datetime.timedelta(seconds=TWO_WEEKS_SECONDS)
            print(f"\nNext run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Sleeping for 2 weeks...\n")
            
            # Sleep for 2 weeks
            time.sleep(TWO_WEEKS_SECONDS)
            
        except KeyboardInterrupt:
            print("\n\n  Pipeline stopped by user (Ctrl+C)")
            break
        except Exception as e:
            print(f"\n\n✗ Pipeline error: {e}")
            print("Retrying in 1 hour...")
            time.sleep(3600)  # Wait 1 hour before retrying on error
    
    print("\nPipeline terminated.")
    
    # For manual one-time execution, uncomment below:
    # run_toronto_cctv_pipeline(max_images=10)
    # generate_pipeline_insights()
    # run_local_directory_pipeline("./demoimages", max_images=5)
