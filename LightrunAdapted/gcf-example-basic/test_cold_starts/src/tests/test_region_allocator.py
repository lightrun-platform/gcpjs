import unittest
from unittest.mock import patch, MagicMock
import io
import threading
from src.models import GCPFunction
from src.region_allocator import RegionAllocator

class TestRegionAllocator(unittest.TestCase):
    
    def setUp(self):
        # Mock data
        self.mock_csv_data = """Google Cloud Region,Location,Google CFE,Grid carbon intensity (gCO2eq / kWh)
region-a,Location A,0.9,10.0
region-b,Location B,0.8,20.0
region-c,Location C,0.7,5.0""" 
        # Sorted order should be: region-c (5.0), region-a (10.0), region-b (20.0)

    @patch('requests.get')
    def test_fetch_and_sort_data(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = self.mock_csv_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        allocator = RegionAllocator()
        
        self.assertEqual(len(allocator.regions), 3)
        self.assertEqual(allocator.regions[0]['name'], 'region-c')
        self.assertEqual(allocator.regions[0]['intensity'], 5.0)
        self.assertEqual(allocator.regions[1]['name'], 'region-a')
        self.assertEqual(allocator.regions[2]['name'], 'region-b')
        
    @patch('requests.get')
    def test_allocation_distribution(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = self.mock_csv_data
        mock_get.return_value = mock_response
        
        allocator = RegionAllocator()
        
        # Allocate 25 functions. 
        # First 20 should go to 'region-c' (best).
        # Next 5 should go to 'region-a' (second best).
        
        functions = [GCPFunction(index=i) for i in range(25)]
        
        for func in functions:
            allocator.allocate_region(func)
            
        # Verify allocation counts
        # We can inspect the internal state
        self.assertEqual(allocator.allocations['region-c'], 20)
        self.assertEqual(allocator.allocations['region-a'], 5)
        self.assertEqual(allocator.allocations['region-b'], 0)
        
        # Verify assigned regions on functions
        c_functions = [f for f in functions if f.region == 'region-c']
        a_functions = [f for f in functions if f.region == 'region-a']
        
        self.assertEqual(len(c_functions), 20)
        self.assertEqual(len(a_functions), 5)

if __name__ == '__main__':
    unittest.main()
