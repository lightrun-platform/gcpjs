import unittest
from unittest.mock import patch, MagicMock
import io
from pathlib import Path
import sys

# Add parent directory to path so we can import as a package
# Add parent directory to path so we can import as a package
# We need 'Benchmarks' dir in path to import 'shared_modules'
benchmarks_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(benchmarks_dir))
# We need root dir in path to import 'Lightrun.Benchmarks...'
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from shared_modules.gcf_models import GCPFunction
from shared_modules.region_allocator import RegionAllocator

class TestRegionAllocator(unittest.TestCase):
    
    def setUp(self):
        # Mock data (using real supported regions)
        self.mock_csv_data = """Google Cloud Region,Location,Google CFE,Grid carbon intensity (gCO2eq / kWh)
us-east1,Location A,0.9,10.0
us-west1,Location B,0.8,20.0
us-central1,Location C,0.7,5.0""" 
        # Sorted order should be: us-central1 (5.0), us-east1 (10.0), us-west1 (20.0)

    @patch('requests.get')
    def test_fetch_and_sort_data(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = self.mock_csv_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        allocator = RegionAllocator()
        
        self.assertEqual(len(allocator.regions), 3)
        self.assertEqual(allocator.regions[0]['name'], 'us-central1')
        self.assertEqual(allocator.regions[0]['intensity'], 5.0)
        self.assertEqual(allocator.regions[1]['name'], 'us-east1')
        self.assertEqual(allocator.regions[2]['name'], 'us-west1')
        
    @patch('requests.get')
    def test_allocation_distribution(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = self.mock_csv_data
        mock_get.return_value = mock_response

        allocator = RegionAllocator()
        allocator_iter = iter(allocator)

        # Allocate 25 functions.
        # First 20 should go to 'us-central1' (best).
        # Next 5 should go to 'us-east1' (second best).

        functions = [GCPFunction(name=f'test-{i}', region=next(allocator_iter)) for i in range(25)]

        # Verify assigned regions on functions
        c_functions = [f for f in functions if f.region == 'us-central1']
        a_functions = [f for f in functions if f.region == 'us-east1']
        b_functions = [f for f in functions if f.region == 'us-west1']

        self.assertEqual(len(c_functions), 20)
        self.assertEqual(len(a_functions), 5)
        self.assertEqual(len(b_functions), 0)

if __name__ == '__main__':
    unittest.main()
