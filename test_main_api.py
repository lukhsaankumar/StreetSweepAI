"""Test runner for /api/classify that fetches Toronto traffic camera images.
Requires GOOGLE_API_KEY env var to be set.
"""
import asyncio
import io
import json
import re
import ssl
import time
from pathlib import Path
from fastapi import UploadFile
from main import classify
import urllib.request

# Create SSL context that doesn't verify certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


async def run_test() -> None:
    base_dir = Path(__file__).resolve().parent
    results_file = base_dir / "severity_results.json"
    high_severity_file = base_dir / "severity_results.txt"
    
    # Fetch the JSONP data
    json_url = "https://opendata.toronto.ca/transportation/tmc/rescucameraimages/Data/tmcearthcameras.json"
    print(f"Fetching camera data from {json_url}...")
    
    with urllib.request.urlopen(json_url, context=ssl_context) as response:
        jsonp_text = response.read().decode('utf-8')
    
    # Strip the JSONP wrapper: jsonTMCEarthCamerasCallback({...});
    # Handle both with and without semicolon, and multiline content
    jsonp_text = jsonp_text.strip()
    if jsonp_text.startswith('jsonTMCEarthCamerasCallback('):
        # Remove callback wrapper and trailing semicolon if present
        json_text = jsonp_text[len('jsonTMCEarthCamerasCallback('):]
        if json_text.endswith(');'):
            json_text = json_text[:-2]
        elif json_text.endswith(')'):
            json_text = json_text[:-1]
    else:
        json_text = jsonp_text
    
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON. First 200 chars of response:")
        print(jsonp_text[:200])
        raise
    
    cameras = data.get("Data", [])
    print(f"Found {len(cameras)} cameras\n")
    
    results = []
    high_severity_entries = []
    
    for idx, camera in enumerate(cameras, 1):
        number = camera.get("Number")
        name = camera.get("Name")
        print(f"[{idx}/{len(cameras)}] Camera {number}: {name}")
        
        # Test main camera image
        main_url = f"https://opendata.toronto.ca/transportation/tmc/rescucameraimages/CameraImages/loc{number}.jpg"
        severity = await test_image_url(main_url, f"loc{number}.jpg")
        results.append({
            "camera_number": number,
            "camera_name": name,
            "image_type": "main",
            "url": main_url,
            "severity": severity
        })
        print(f"  Main image: severity={severity}")
        
        # Track high severity images
        if severity and severity > 1:
            high_severity_entries.append(f"Camera {number} ({name}) - Main: Severity {severity}\n  URL: {main_url}\n")
        
        # Wait 1 second before next request (paid model has higher limits)
        await asyncio.sleep(1)
        
        # Test directional comparison images
        for direction_key in ["D1", "D2", "D3", "D4"]:
            direction = camera.get(direction_key)
            if not direction:
                continue
                
            comp_url = f"https://opendata.toronto.ca/transportation/tmc/rescucameraimages/ComparisonImages/loc{number}{direction}.jpg"
            severity = await test_image_url(comp_url, f"loc{number}{direction}.jpg")
            results.append({
                "camera_number": number,
                "camera_name": name,
                "image_type": f"comparison_{direction}",
                "url": comp_url,
                "severity": severity
            })
            print(f"  Direction {direction}: severity={severity}")
            
            # Track high severity images
            if severity and severity > 1:
                high_severity_entries.append(f"Camera {number} ({name}) - Direction {direction.upper()}: Severity {severity}\n  URL: {comp_url}\n")
            
            # Wait 1 second before next request (paid model has higher limits)
            await asyncio.sleep(1)
        
        print()
    
    # Save all results to JSON file
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nAll results saved to: {results_file}")
    
    # Save high severity results to text file
    with open(high_severity_file, 'w') as f:
        f.write(f"Images with Severity > 1\n")
        f.write(f"=" * 60 + "\n\n")
        for entry in high_severity_entries:
            f.write(entry + "\n")
    print(f"High severity images (>1) saved to: {high_severity_file}")
    print(f"Total high severity images: {len(high_severity_entries)}")


async def test_image_url(url: str, filename: str, max_retries: int = 5) -> int | None:
    """Download image from URL and test it, returning severity score."""
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, context=ssl_context) as response:
                file_bytes = response.read()
            
            # Create UploadFile object
            upload = UploadFile(filename=filename, file=io.BytesIO(file_bytes))
            
            # Classify the image
            result = await classify(file=upload)
            return result.get("severity")
        
        except Exception as e:
            error_str = str(e)
            
            # Check if it's a rate limit error (429)
            if "429" in error_str or "rate limit" in error_str.lower():
                # Try to extract reset time from error message
                import re
                reset_match = re.search(r"'X-RateLimit-Reset': '(\d+)'", error_str)
                
                if reset_match:
                    reset_timestamp = int(reset_match.group(1)) / 1000  # Convert ms to seconds
                    current_time = time.time()
                    wait_time = max(1, int(reset_timestamp - current_time) + 2)  # Add 2s buffer
                    print(f"    Rate limit hit. Waiting {wait_time}s until reset...")
                    await asyncio.sleep(wait_time)
                else:
                    # If no reset time, use exponential backoff
                    wait_time = min(60, 10 * (2 ** attempt))  # Cap at 60 seconds
                    print(f"    Rate limit hit. Waiting {wait_time}s (attempt {attempt+1}/{max_retries})...")
                    await asyncio.sleep(wait_time)
            else:
                print(f"    ERROR: {e}")
                return None
    
    print(f"    Failed after {max_retries} retries")
    return None


if __name__ == "__main__":
    asyncio.run(run_test())
