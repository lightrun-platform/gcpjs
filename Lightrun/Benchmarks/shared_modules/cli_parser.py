
import argparse
import os

class CLIParser:
    """Parses command-line arguments for the benchmark."""

    def parse(self):
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description='Test Cloud Functions with guaranteed cold starts. '
                        'Deploys multiple functions for both with/without Lightrun, '
                        'waits for them to become cold, then tests them all in parallel.',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Use defaults (100 functions each, 20 minute wait)
  %(prog)s --lightrun-secret YOUR_SECRET

  # Test with 50 functions each
  %(prog)s --lightrun-secret YOUR_SECRET --num-functions 50

  # Custom region and project
  %(prog)s --lightrun-secret YOUR_SECRET --region us-central1 --project my-project
            """
        )
        
        parser.add_argument(
            '--lightrun-secret',
            type=str,
            default=os.environ.get('LIGHTRUN_SECRET', ''),
            help='Lightrun secret (default: from LIGHTRUN_SECRET env var)'
        )
        parser.add_argument(
            '--num-functions',
            type=int,
            default=100,
            help='Number of functions to deploy and test per variant (default: 100)'
        )
        parser.add_argument(
            '--test-file-length',
            type=int,
            default=10,
            help='Length of generated test file (number of dummy functions) (default: 10)'
        )
        parser.add_argument(
            '--lightrun-action-type',
            type=str,
            default='snapshot',
            choices=['snapshot', 'log'],
            help='Type of Lightrun action to insert (default: snapshot)'
        )

        parser.add_argument(
            '--region',
            type=str,
            default='europe-west3',
            help='GCP region (default: europe-west3)'
        )
        parser.add_argument(
            '--project',
            type=str,
            default='lightrun-temp',
            help='GCP project ID (default: lightrun-temp)'
        )
        parser.add_argument(
            '--runtime',
            type=str,
            default='nodejs20',
            help='Function runtime (default: nodejs20)'
        )
        parser.add_argument(
            '--results-file',
            type=str,
            default='benchmark_results.json',
            help='Output file for test results (default: benchmark_results.json)'
        )
        parser.add_argument(
            '--report-file',
            type=str,
            default='comparative_benchmark_report.txt',
            help='Output file for test report (default: comparative_benchmark_report.txt)'
        )
        parser.add_argument(
            '--num-workers',
            type=int,
            default=None,
            help='Number of worker threads per test variant (default: number of functions to deploy)'
        )
        parser.add_argument(
            '--delay-between-requests',
            type=int,
            default=10,
            help='Seconds to wait between requests to each function (default: 10)'
        )
        parser.add_argument(
            '--test-size',
            type=int,
            default=10,
            help='The size/length/repeats dimention of the test. each test is free to use this dimention as it wishes but usually it is used as the number of times to run the test, perhaps with some variation happening in some of the test iterations (default: 10)'
        )
        parser.add_argument(
            '--lightrun-api-key',
            type=str,
            default=os.environ.get('LIGHTRUN_API_KEY', ''),
            help='Lightrun API key for adding snapshots (default: from LIGHTRUN_API_KEY env var)'
        )
        parser.add_argument(
            '--lightrun-company-id',
            type=str,
            default=os.environ.get('LIGHTRUN_COMPANY_ID', ''),
            help='Lightrun Company ID (default: from LIGHTRUN_COMPANY_ID env var)'
        )
        parser.add_argument(
            '--max-allocations-per-region',
            type=int,
            default=20,
            help='Maximum number of functions to allocate per region (default: 20)'
        )
        parser.add_argument(
            '--consecutive-cold-checks',
            type=int,
            default=3,
            help='Number of consecutive checks showing 0 instances required to confirm cold state (default: 3)'
        )
        parser.add_argument(
            '--cold-check-delay',
            type=int,
            default=30,
            help='Seconds to wait between cold state checks (default: 30)'
        )
        
        parser.add_argument(
            '--skip-wait-for-cold',
            action='store_true',
            help='Skip waiting for functions to become cold (default: False)'
        )
        
        args = parser.parse_args()
        
        # Set default num_workers to num_functions if not specified
        if args.num_workers is None:
            args.num_workers = args.num_functions

        if not args.lightrun_api_key:
            parser.error("the following arguments are required: --lightrun-api-key (or set the LIGHTRUN_API_KEY environment variable)")
        
        if not args.lightrun_company_id:
            parser.error("the following arguments are required: --lightrun-company-id (or set the LIGHTRUN_COMPANY_ID environment variable)")
        
        if not args.lightrun_secret:
            parser.error("the following arguments are required: --lightrun-secret (or set the LIGHTRUN_SECRET environment variable)")
        
        return args
