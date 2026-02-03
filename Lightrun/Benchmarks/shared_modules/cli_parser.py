import argparse
import os
import copy
import math
import logging


def _mask_secret(value: str) -> str:
    """Mask a secret value: show first 10% and last 10%, hide the rest."""
    if not value:
        return ""
    length = len(value)
    # Calculate 10% of length, rounded up to the nearest integer
    show_count = math.ceil(length * 0.1)

    # Ensure we don't overlap or show too much
    if show_count * 2 >= length:
        # For very short strings, show at most 1 char if length > 1
        if length <= 2:
            return value
        show_count = 1

    start = value[:show_count]
    end = value[-show_count:]
    mask = "*" * (length - (show_count * 2))
    return f"{start}{mask}{end}"


class ParsedCLIArguments:

    def __init__(self, ns: argparse.Namespace):
        self._ns = ns

    def __getattr__(self, name):
        ns = object.__getattribute__(self, "_ns")
        return object.__getattribute__(ns, name)

    # def __setstate__(self, state):
    #     ns = self._ns
    #     ns.__setstate__(state)

    def print_configuration(self, table_header: str = None, logger: logging.Logger = None):
        """Print the entire benchmark configuration with sources and masked secrets."""

        def log_or_print(msg=""):
            if logger:
                logger.info(msg)
            else:
                print(msg)
        
        if table_header:
            log_or_print("=" * 80)
            log_or_print(table_header)
            log_or_print("=" * 80)
        
        # Determine column widths
        config_dict = {k: v for k, v in vars(self._ns).items() if not k.startswith('_')}
        metadata = getattr(self._ns, '_metadata', {})
        
        name_width = max(len(k) for k in config_dict.keys()) if config_dict else 20
        name_width = max(name_width, 4) # At least "NAME" length
        source_width = 8 # "Default", "CLI", "Env"
        
        # Print headers
        log_or_print(f"{'NAME':<{name_width}}  {'SOURCE':<{source_width}}  {'VALUE'}")
        log_or_print(f"{'-' * name_width}  {'-' * source_width}  {'-' * 20}")
        
        # Sort keys for consistent output
        sorted_keys = sorted(config_dict.keys())
        
        for key in sorted_keys:
            val = config_dict[key]
            entry = metadata.get(key, {})
            source = entry.get('source', 'Unknown')
            is_secret = entry.get('is_secret', False)
            
            # Format value
            display_val = str(val)
            if is_secret and display_val:
                display_val = _mask_secret(display_val)
            
            # Print row
            log_or_print(f"{key:<{name_width}}  {source:<{source_width}}  {display_val}")
        
        log_or_print("=" * 80)
        log_or_print("")


class MetadataArgumentParser(argparse.ArgumentParser):
    """Argument parser that automatically tracks the source and other metadata of arguments."""
    def __init__(self, *args, _metadata_schema=None, **kwargs):
        # Initialize schema before super().__init__ because super().__init__ calls add_argument for --help
        if _metadata_schema is None:
            _metadata_schema = {}
        self._metadata_schema = _metadata_schema
        super().__init__(*args, **kwargs)

    def add_argument(self, *args, **kwargs):
        # Intercept metadata properties based on the schema
        metadata = {}
        for prop, config in self._metadata_schema.items():
            if prop in kwargs:
                metadata[prop] = kwargs.pop(prop)
            elif config.get('has_default'):
                metadata[prop] = config.get('default_value')
        
        # env_var is a special behavior property
        env_var = kwargs.pop('env_var', None)
        
        # Automatic environment variable derivation
        env_found = False
        if env_var and env_var in os.environ:
            kwargs['default'] = os.environ[env_var]
            env_found = True
            
        action = super().add_argument(*args, **kwargs)
        
        # Attach metadata and tracking info to the action object
        action.metadata = metadata
        action.env_var = env_var
        action._env_found = env_found
        
        # Use dynamic subclassing to wrap __call__ since special methods 
        # like __call__ are looked up on the class, not the instance.
        original_class = action.__class__
        
        class WrappedAction(original_class):
            def __call__(self, parser, namespace, values, option_string=None):
                if not hasattr(namespace, '_metadata'):
                    namespace._metadata = {}
                
                # Copy metadata and add source
                ns_metadata = copy.deepcopy(getattr(self, 'metadata', {}))
                ns_metadata['source'] = 'CLI'
                namespace._metadata[self.dest] = ns_metadata
                
                return super().__call__(parser, namespace, values, option_string)
        
        action.__class__ = WrappedAction
        return action

    def parse_args(self, args=None, namespace=None):
        ns = super().parse_args(args, namespace)
        
        if not hasattr(ns, '_metadata'):
            ns._metadata = {}
            
        # For all actions that weren't triggered by CLI (not in _metadata)
        # determine if they came from Env or Default
        for action in self._actions:
            if not hasattr(action, 'dest') or action.dest == 'help':
                continue
                
            if action.dest not in ns._metadata:
                source = 'Env' if getattr(action, '_env_found', False) else 'Default'
                
                # Populate metadata for non-CLI sources
                metadata = copy.deepcopy(getattr(action, 'metadata', {}))
                metadata['source'] = source
                ns._metadata[action.dest] = metadata
        
        namespace_original_class = ns.__class__
        
        return ns

class CLIParser:
    """Parses command-line arguments for the benchmark."""

    def __init__(self, *args, **kwargs):
        self._configuration = None
        self._args = args
        self._kwargs = kwargs
        self._metadata_schema = {
            "is_secret": {"has_default": True, "default_value": False}
        }

    def parse(self) -> ParsedCLIArguments:
        if self._configuration is None:
            self._configuration = self._parse()
        return ParsedCLIArguments(copy.deepcopy(self._configuration))

    def _parse(self):
        """Parse command-line arguments."""
        parser = MetadataArgumentParser(
            *self._args,
            **self._kwargs,
            _metadata_schema=self._metadata_schema
        )
        
        parser.add_argument(
            '--lightrun-secret',
            type=str,
            default='',
            is_secret=True,
            env_var='LIGHTRUN_SECRET',
            help='Lightrun secret (default: from LIGHTRUN_SECRET env var)'
        )
        parser.add_argument(    
            '--num-functions',
            type=int,
            default=100,
            help='Number of functions to deploy and test per variant (default: 100)'
        )
        parser.add_argument(
            '--lightrun-action-type',
            type=str,
            default='snapshot',
            choices=['snapshot', 'log'],
            help='Type of Lightrun action to insert (default: snapshot)'
        )
        parser.add_argument(
            '--project',
            type=str,
            default='lightrun-temp',
            help='GCP project ID (default: lightrun-temp)'
        )
        parser.add_argument(
            '--runtimes',
            type=lambda s: [item.strip() for item in s.split(',')],
            default=['nodejs20'],
            help='List of function runtimes (comma separated, default: nodejs20)'
        )
        parser.add_argument(
            '--memory',
            type=lambda s: [item.strip() for item in s.split(',')],
            default=["256Mi", "512Mi"],
            help='List of memory allocations (comma separated, default: 256Mi, 512Mi)'
        )
        parser.add_argument(
            '--cpus',
            type=lambda s: [item.strip() for item in s.split(',')],
            default=["2"],
            help='List of cpu allocations (comma separated, default: 2)'
        )
        parser.add_argument(
            '--request-timeout',
            type=int,
            default=540,
            help='Function request timeout in seconds (default: 540)'
        )
        parser.add_argument(
            '--deployment-timeout',
            type=int,
            default=600,
            help='Function deployment timeout in seconds (default: 600)'
        )
        parser.add_argument(
            '--delete-timeout',
            type=int,
            default=120,
            help='maximum time in seconds to wait for function deletion to complete (default: 120)'
        )
        parser.add_argument(
            '--function-generations',
            type=lambda s: [item.strip() for item in s.split(',')],
            default=["gen1", "gen2"],
            help='List of function generations (comma separated, default: gen1, gen2)'
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
            is_secret=False,
            help='Seconds to wait between requests to each function (default: 10)'
        )
        parser.add_argument(
            '--test-size',
            type=int,
            default=10,
            is_secret=False,
            help='The size/length/repeats dimention of the test. each test is free to use this dimention as it wishes but usually it is used as the number of times to run the test, perhaps with some variation happening in some of the test iterations (default: 10)'
        )
        parser.add_argument(
            '--lightrun-api-key',
            type=str,
            default='',
            is_secret=True,
            env_var='LIGHTRUN_API_KEY',
            help='Lightrun API key for adding snapshots (default: from LIGHTRUN_API_KEY env var)'
        )
        parser.add_argument(
            '--lightrun-company-id',
            type=str,
            default='',
            env_var='LIGHTRUN_COMPANY_ID',
            help='Lightrun Company ID (default: from LIGHTRUN_COMPANY_ID env var)'
        )
        parser.add_argument(
            '--authentication-type',
            type=str,
            required=True,
            choices=['API_KEY', 'MANUAL'],
            help="Method of authentication to use. Options: ['API_KEY', 'MANUAL']. Option 'MANUAL' initiates an interactive login flow. Option 'API_KEY' must be used with the --lightrun-api-key option and uses the provided API key directly."
        )
        parser.add_argument(
            '--lightrun-api-url',
            type=str,
            default='https://app.lightrun.com',
            env_var='LIGHTRUN_API_URL',
            help='Lightrun API URL (default: from LIGHTRUN_API_URL env var or https://app.lightrun.com)'
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

        parser.add_argument(
            '--clean-test-resources',
            type=bool,
            default=True,
            help='Whether to clean up test resources after the test (default: True). Set to False to preserve cloud assets for post-mortem examinations. Make sure to clean them up yourself afterwards!'
        )

        parser.add_argument(
            '--lightrun-version',
            type=str,
            help='Lightrun library version to use in the test'
        )
        parser.add_argument(
            '--google-library-version',
            type=str,
            default='3.3.0',
            help='Google Cloud Functions Framework version (default: ^3.3.0)'
        )
        
        args = parser.parse_args()
        
        # Set default num_workers to num_functions (capped at 16) if not specified
        if args.num_workers is None:
            # GCP Cloud Build often has a default concurrency of 10-30. 
            # 16 is a safe default to avoid hitting project-wide quotas too easily.
            args.num_workers = min(args.num_functions, 16)

        if args.authentication_type == 'API_KEY' and not args.lightrun_api_key:
            parser.error("argument --lightrun-api-key is required when --authentication-type is 'API_KEY'")
        
        if not args.lightrun_company_id:
            parser.error("the following arguments are required: --lightrun-company-id (or set the LIGHTRUN_COMPANY_ID environment variable)")
        
        if not args.lightrun_secret:
            parser.error("the following arguments are required: --lightrun-secret (or set the LIGHTRUN_SECRET environment variable)")
        
        return args
