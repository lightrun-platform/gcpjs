"""Unit tests for GCPFunction class."""
import unittest
from unittest.mock import Mock, patch
from Lightrun.Benchmarks.shared_modules.gcf_models.gcp_function import GCPFunction
from Lightrun.Benchmarks.shared_modules.cloud_assets import GCSSourceObject, ArtifactRegistryImage

class TestGCPFunction(unittest.TestCase):
    def setUp(self):
        self.logger = Mock()
        self.function = GCPFunction(
            region='us-central1',
            name='test-func',
            runtime='nodejs20',
            entry_point='ep',
            function_source_code_dir='/tmp',
            project='test-proj',
            gen2=True,
            logger=self.logger
        )

    @patch('subprocess.run')
    def test_discover_associated_assets_gen2(self, mock_run):
        # Mock successful describe
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""{
                "buildConfig": {
                    "source": {
                        "storageSource": {
                            "bucket": "my-bucket",
                            "object": "source.zip"
                        }
                    },
                    "imageUri": "us-central1-docker.pkg.dev/proj/repo/img"
                }
            }"""
        )
        
        assets = self.function.discover_associated_assets()
        
        self.assertEqual(len(assets), 2)
        
        # Verify types and names
        self.assertIsInstance(assets[0], GCSSourceObject)
        self.assertEqual(assets[0].name, "gs://my-bucket/source.zip")
        
        self.assertIsInstance(assets[1], ArtifactRegistryImage)
        self.assertEqual(assets[1].name, "us-central1-docker.pkg.dev/proj/repo/img")

    @patch('subprocess.run')
    def test_discover_associated_assets_empty(self, mock_run):
        # Mock describe where no assets found
        mock_run.return_value = Mock(
            returncode=0,
            stdout="{}"
        )
        assets = self.function.discover_associated_assets()
        self.assertEqual(len(assets), 0)

    @patch('subprocess.run')
    def test_discover_failure(self, mock_run):
        # Mock failing describe
        mock_run.return_value = Mock(returncode=1, stderr="Not found")
        
        assets = self.function.discover_associated_assets()
        self.assertEqual(len(assets), 0)
        self.logger.warning.assert_called()

if __name__ == '__main__':
    unittest.main()
