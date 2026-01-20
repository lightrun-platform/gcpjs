import csv
import io
import requests
import threading
from typing import List, Dict, Optional
from .models import GCPFunction

CARBON_DATA_URL = "https://raw.githubusercontent.com/GoogleCloudPlatform/region-carbon-info/main/data/yearly/2024.csv"

class RegionAllocator:
    """Allocates Cloud Functions to regions based on carbon intensity."""
    
    def __init__(self, use_static_data: bool = False):
        self.regions: List[Dict[str, str]] = []
        self.allocations: Dict[str, int] = {}
        self.lock = threading.Lock()
        
        if use_static_data:
            self._load_static_data()
        else:
            self._fetch_and_parse_data()
            
    def _fetch_and_parse_data(self):
        """Fetch carbon data from GitHub and sort by intensity."""
        try:
            response = requests.get(CARBON_DATA_URL, timeout=10)
            response.raise_for_status()
            
            # Parse CSV
            # Columns: Google Cloud Region,Location,Google CFE,Grid carbon intensity (gCO2eq / kWh)
            reader = csv.DictReader(io.StringIO(response.text))
            
            parsed_regions = []
            for row in reader:
                region_name = row.get('Google Cloud Region')
                intensity_str = row.get('Grid carbon intensity (gCO2eq / kWh)')
                
                if region_name and intensity_str:
                    try:
                        intensity = float(intensity_str)
                        parsed_regions.append({
                            'name': region_name,
                            'intensity': intensity,
                            'location': row.get('Location', '')
                        })
                    except ValueError:
                        continue
                        
            # Sort by intensity ascending (greenest first)
            self.regions = sorted(parsed_regions, key=lambda r: r['intensity'])
            
            # Initialize allocations
            for r in self.regions:
                self.allocations[r['name']] = 0
                
            print(f"Loaded {len(self.regions)} regions, sorted by carbon intensity.")
            if self.regions:
                print(f"  Best: {self.regions[0]['name']} ({self.regions[0]['intensity']} gCO2eq/kWh)")
                print(f"  Worst: {self.regions[-1]['name']} ({self.regions[-1]['intensity']} gCO2eq/kWh)")
                
        except Exception as e:
            print(f"WARNING: Failed to fetch carbon data: {e}")
            print("Falling back to default region (us-central1)")
            # Fallback will be handled by returning None or specific default
            self.regions = [{'name': 'us-central1', 'intensity': 0}]
            self.allocations['us-central1'] = 0

    def allocate_region(self, function: GCPFunction):
        """Assign the next best region to the function."""
        with self.lock:
            # Find the best region with < 20 allocations
            selected_region = None
            
            for region in self.regions:
                name = region['name']
                if self.allocations.get(name, 0) < 20:
                    selected_region = name
                    self.allocations[name] += 1
                    break
            
            # If all full (unlikely given the list size), pick the first one (or random/round-robin)
            if not selected_region and self.regions:
                selected_region = self.regions[0]['name']
                self.allocations[selected_region] += 1
                
            if selected_region:
                function.region = selected_region
            else:
                # Should not happen if fallback enabled
                function.region = 'us-central1'
