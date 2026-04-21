"""
Load events from a JSON file and send them to the API.

Usage:
    python scripts/load_json.py path/to/sample_events.json
"""

import sys
import json
import requests
from typing import List, Dict

def load_events(filepath: str, base_url: str = "http://localhost:8000"):
    print(f"Loading events from {filepath}...")
    
    try:
        with open(filepath, "r") as f:
            events: List[Dict] = json.load(f)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    print(f"Found {len(events)} events. Sending to API at {base_url}...")
    
    accepted = 0
    duplicates = 0
    errors = 0

    for i, event in enumerate(events):
        try:
            resp = requests.post(f"{base_url}/api/v1/events", json=event, timeout=10.0)
            if resp.status_code == 201:
                accepted += 1
            elif resp.status_code == 200:
                duplicates += 1
            else:
                errors += 1
                if errors <= 5:
                    print(f"  Error [{resp.status_code}] for event {event.get('event_id')}: {resp.text}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Request error: {e}")

        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{len(events)} (accepted={accepted}, duplicates={duplicates}, errors={errors})")

    print("\nImport complete:")
    print(f"  Total events in file: {len(events)}")
    print(f"  Successfully imported (new): {accepted}")
    print(f"  Skipped (duplicates): {duplicates}")
    print(f"  Failed: {errors}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Please provide the path to your sample_events.json file.")
        print("Usage: python scripts/load_json.py path/to/sample_events.json")
        sys.exit(1)
        
    filepath = sys.argv[1]
    
    # Check if requests is installed, install if missing just to be helpful
    try:
        import requests
    except ImportError:
        print("Installing 'requests' module needed for this script...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
        
    load_events(filepath)
