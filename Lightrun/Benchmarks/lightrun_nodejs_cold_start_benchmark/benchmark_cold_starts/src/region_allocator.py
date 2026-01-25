import csv
import io
import itertools
import requests
from typing import List, Dict, Iterator

CARBON_DATA_URL = "https://raw.githubusercontent.com/GoogleCloudPlatform/region-carbon-info/main/data/yearly/2024.csv"

# Known Cloud Functions supported regions (as of 2024)
# Note: europe-north2 and some other regions are not available for Cloud Functions
GCF_SUPPORTED_REGIONS = {
    "us-central1", "us-east1", "us-east4", "us-west1", "us-west2", "us-west3", "us-west4",
    "europe-west1", "europe-west2", "europe-west3", "europe-west4", "europe-west6",
    "europe-north1", "europe-central2",
    "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast2", "asia-northeast3",
    "asia-south1", "asia-south2", "asia-southeast1", "asia-southeast2",
    "australia-southeast1", "australia-southeast2",
    "northamerica-northeast1", "northamerica-northeast2",
    "southamerica-east1", "southamerica-west1",
    "me-west1", "me-central1", "me-central2",
    "africa-south1"
}


def _fetch_carbon_data():
    """Fetch carbon data from GitHub and sort by intensity."""
    response = requests.get(CARBON_DATA_URL, timeout=10)
    response.raise_for_status()

    # Parse CSV
    # Columns: Google Cloud Region,Location,Google CFE,Grid carbon intensity (gCO2eq / kWh)
    reader = csv.DictReader(io.StringIO(response.text))

    parsed_regions = []
    for row in reader:
        region_name = row.get('Google Cloud Region')
        intensity_str = row.get('Grid carbon intensity (gCO2eq / kWh)')

        # Filter to only include GCF-supported regions
        if region_name and intensity_str and region_name in GCF_SUPPORTED_REGIONS:
            try:
                intensity = float(intensity_str)
                parsed_regions.append({
                    'name': region_name,
                    'intensity': intensity,
                    'location': row.get('Location', '')
                })
            except ValueError:
                continue

    return parsed_regions

class RegionAllocator:
    """Allocates Cloud Functions to regions based on carbon intensity."""
    
    def __init__(self, max_allocations_per_region: int = 20):
        self.regions: List[Dict[str, str]] = []
        self.max_allocations_per_region = max_allocations_per_region
        self.regions = sorted(_fetch_carbon_data(), key=lambda r: r['intensity'])

    def __iter__(self):
        return itertools.chain(*[[region['name']] * self.max_allocations_per_region for region in self.regions])

