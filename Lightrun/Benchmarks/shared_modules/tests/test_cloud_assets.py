"""Unit tests for CloudAsset."""
import unittest
from unittest.mock import Mock, patch
from Lightrun.Benchmarks.shared_modules.cloud_assets import GCSSourceObject, ArtifactRegistryImage, NoSuchAsset

class TestGCSSourceObject(unittest.TestCase):
    def setUp(self):
        self.logger = Mock()
        self.asset = GCSSourceObject("gs://my-bucket/object.zip")

    @patch('subprocess.run')
    def test_exists_true(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        self.assertTrue(self.asset.exists(self.logger))

    @patch('subprocess.run')
    def test_exists_false(self, mock_run):
        mock_run.return_value = Mock(returncode=1)
        self.assertFalse(self.asset.exists(self.logger))

    @patch('subprocess.run')
    def test_delete_exists_and_succeeds(self, mock_run):
        # exists() call -> 0, delete() call -> 0
        mock_run.side_effect = [Mock(returncode=0), Mock(returncode=0)]
        
        self.assertTrue(self.asset.delete(self.logger))
        
        # Verify calls
        # 1. ls
        self.assertIn('ls', mock_run.call_args_list[0][0][0])
        # 2. rm
        self.assertIn('rm', mock_run.call_args_list[1][0][0])

    @patch('subprocess.run')
    def test_delete_not_exists_raises(self, mock_run):
        # exists() call -> 1
        mock_run.side_effect = [Mock(returncode=1)]
        
        with self.assertRaises(NoSuchAsset):
            self.asset.delete(self.logger)
    
    @patch('subprocess.run')
    def test_apply_labels(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        self.assertTrue(self.asset.apply_labels({'a': 'b'}, self.logger))
        args = mock_run.call_args[0][0]
        self.assertIn('update', args)
        self.assertIn('--add-labels=a=b', args)


class TestArtifactRegistryImage(unittest.TestCase):
    def setUp(self):
        self.logger = Mock()
        self.asset = ArtifactRegistryImage("us-central1-docker.pkg.dev/p/r/i:tag")

    @patch('subprocess.run')
    def test_exists_true(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        self.assertTrue(self.asset.exists(self.logger))

    @patch('subprocess.run')
    def test_delete_exists_and_succeeds(self, mock_run):
        # exists() call -> 0, delete() call -> 0
        mock_run.side_effect = [Mock(returncode=0), Mock(returncode=0)]
        self.assertTrue(self.asset.delete(self.logger))

    @patch('subprocess.run')
    def test_delete_not_exists_raises(self, mock_run):
        # exists() call -> 1
        mock_run.side_effect = [Mock(returncode=1)]
        
        with self.assertRaises(NoSuchAsset):
            self.asset.delete(self.logger)

if __name__ == '__main__':
    unittest.main()
