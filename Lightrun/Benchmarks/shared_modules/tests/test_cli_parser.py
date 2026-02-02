import unittest
import os
from pathlib import Path
import sys

# Add parent directories to path
# We need 'Benchmarks' dir in path to import 'shared_modules'
benchmarks_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent))

from Lightrun.Benchmarks.shared_modules.cli_parser import MetadataArgumentParser, CLIParser


class TestMetadataArgumentParser(unittest.TestCase):
    def setUp(self):
        self.parser = MetadataArgumentParser(_metadata_schema={
            "is_secret": {"has_default": True, "default_value": False}
        })
        # Clean up any environment variables we might use
        for key in ['TEST_VAR', 'SECRET_VAR', 'LIGHTRUN_API_KEY', 'LIGHTRUN_COMPANY_ID', 'LIGHTRUN_SECRET']:
            if key in os.environ:
                del os.environ[key]

    def test_cli_source(self):
        self.parser.add_argument('--test', type=str)
        args = self.parser.parse_args(['--test', 'value'])
        
        metadata = getattr(args, '_metadata', {})
        self.assertIn('test', metadata)
        self.assertEqual(metadata['test']['source'], 'CLI')
        self.assertEqual(metadata['test']['is_secret'], False)
        self.assertEqual(args.test, 'value')

    def test_env_source(self):
        os.environ['TEST_VAR'] = 'env_value'
        self.parser.add_argument('--test', type=str, default='default_value', env_var='TEST_VAR')
        args = self.parser.parse_args([])
        
        metadata = getattr(args, '_metadata', {})
        self.assertIn('test', metadata)
        self.assertEqual(metadata['test']['source'], 'Env')
        self.assertEqual(args.test, 'env_value')

    def test_default_source(self):
        self.parser.add_argument('--test', type=str, default='default_value', env_var='TEST_VAR')
        args = self.parser.parse_args([])
        
        metadata = getattr(args, '_metadata', {})
        self.assertIn('test', metadata)
        self.assertEqual(metadata['test']['source'], 'Default')
        self.assertEqual(args.test, 'default_value')

    def test_cli_overrides_env(self):
        os.environ['TEST_VAR'] = 'env_value'
        self.parser.add_argument('--test', type=str, default='default_value', env_var='TEST_VAR')
        args = self.parser.parse_args(['--test', 'cli_value'])
        
        metadata = getattr(args, '_metadata', {})
        self.assertIn('test', metadata)
        self.assertEqual(metadata['test']['source'], 'CLI')
        self.assertEqual(args.test, 'cli_value')

    def test_is_secret(self):
        self.parser.add_argument('--secret', type=str, is_secret=True)
        args = self.parser.parse_args(['--secret', 'sensitive'])
        
        metadata = getattr(args, '_metadata', {})
        self.assertIn('secret', metadata)
        self.assertEqual(metadata['secret']['is_secret'], True)
        self.assertEqual(metadata['secret']['source'], 'CLI')

    def test_boolean_flag_cli(self):
        self.parser.add_argument('--flag', action='store_true')
        args = self.parser.parse_args(['--flag'])
        
        metadata = getattr(args, '_metadata', {})
        self.assertIn('flag', metadata)
        self.assertEqual(metadata['flag']['source'], 'CLI')
        self.assertTrue(args.flag)

    def test_boolean_flag_default(self):
        self.parser.add_argument('--flag', action='store_true')
        args = self.parser.parse_args([])
        
        metadata = getattr(args, '_metadata', {})
        self.assertIn('flag', metadata)
        self.assertEqual(metadata['flag']['source'], 'Default')
        self.assertFalse(args.flag)

    def test_arbitrary_metadata(self):
        schema = {
            "is_important": {"has_default": True, "default_value": False},
            "category": {"has_default": True, "default_value": "general"}
        }
        parser = MetadataArgumentParser(_metadata_schema=schema)
        parser.add_argument('--urgent', action='store_true', is_important=True, category='system')
        parser.add_argument('--normal', action='store_true')
        
        args = parser.parse_args(['--urgent'])
        
        metadata = getattr(args, '_metadata', {})
        self.assertEqual(metadata['urgent']['is_important'], True)
        self.assertEqual(metadata['urgent']['category'], 'system')
        self.assertEqual(metadata['urgent']['source'], 'CLI')
        
        self.assertEqual(metadata['normal']['is_important'], False)
        self.assertEqual(metadata['normal']['category'], 'general')
        self.assertEqual(metadata['normal']['source'], 'Default')

    def test_cli_parser_integration(self):
        # This tests the actual CLIParser class which uses MetadataArgumentParser

        
        # Mock sys.argv
        original_argv = sys.argv
        sys.argv = ['prog', '--lightrun-secret', 'topsecret', '--num-functions', '5', '--authentication-type', 'API_KEY']
        # Also need to set required env vars for validation if not in CLI
        os.environ['LIGHTRUN_API_KEY'] = 'fake_key'
        os.environ['LIGHTRUN_COMPANY_ID'] = 'fake_id'
        
        try:
            cli_parser = CLIParser(description="Test Parser")
            args = cli_parser.parse()
            
            metadata = getattr(args, '_metadata', {})
            self.assertEqual(metadata['lightrun_secret']['source'], 'CLI')
            self.assertEqual(metadata['lightrun_secret']['is_secret'], True)
            self.assertEqual(metadata['num_functions']['source'], 'CLI')
            self.assertEqual(metadata['delete_timeout']['source'], 'Default')
            self.assertEqual(metadata['lightrun_api_key']['source'], 'Env')
        finally:
            sys.argv = original_argv

if __name__ == '__main__':
    unittest.main()
