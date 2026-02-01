from pathlib import Path
from typing import Dict, List, Type, Any, TypeVar, Optional


T = TypeVar("T")


class NoPublicConstructor(type):
    """Metaclass that ensures a private constructor

    If a class uses this metaclass like this:

        class SomeClass(metaclass=NoPublicConstructor):
            pass

    If you try to instantiate your class (`SomeClass()`),
    a `TypeError` will be thrown.
    """

    def __call__(cls, *args, **kwargs):
        raise TypeError(
            f"{cls.__module__}.{cls.__qualname__} has no public constructor"
        )

    def _create(cls: Type[T], *args: Any, **kwargs: Any) -> T:
        return super().__call__(*args, **kwargs)  # type: ignore



class GCFDeployCommandParameters(metaclass=NoPublicConstructor):
    """A DTO representing all currently supported parameters for the 'gcloud deploy' command as of Jan. 2026.
    it is included mostly for comprehensiveness. """

    # this constructor is "private" and should not be used directly, instead use the create factory method.
    def __init__(
            self,
            # Mandatory params that don't have default and will fail the deployment if not actually set
            function_name: str,
            region: str,
            runtime: str,
            entry_point: str,
            source_code_dir: Path,

            # commonly used parameters with sane defaults
            memory: str = "512Mi",
            cpu: str = "2",
            concurrency: int = 80,
            max_instances: int = 1,
            min_instances: int = 0,
            timeout: int = 540,
            project: str = "lightrun-temp",
            allow_unauthenticated: bool = True,
            deployment_timeout: int = 600,  # 10 minutes
            quiet: bool = True,
            gen2: bool = True,

            # Env vars
            env_vars: Dict[str, str] = None,


            # Triggers (mutually exclusive)
            trigger_http: bool = True,
            trigger_bucket: Optional[str] = None,
            trigger_topic: Optional[str] = None,
            trigger_event: Optional[str] = None,
            trigger_resource: Optional[str] = None,
            trigger_event_filters: Optional[Dict[str, str]] = None,
            trigger_event_filters_path_pattern: Optional[Dict[str, str]] = None,

            # which files to ignore while uploading the function, similar to .gitignore
            ignore_file: Optional[str] = None,


            # Networking & Security
            ingress_settings: Optional[str] = None,  # all, internal-only, internal-and-gclb
            egress_settings: Optional[str] = None,  # private-ranges-only, all
            security_level: str = "secure-always",  # secure-always, secure-optional

            # Service Accounts & Authorization
            service_account: Optional[str] = None,
            run_service_account: Optional[str] = None,
            trigger_service_account: Optional[str] = None,

            # Build & Deployment
            build_env_vars: Optional[Dict[str, str]] = None,
            build_env_vars_file: Optional[str] = None,
            docker_registry: Optional[str] = None,  # DEPRECATED
            docker_repository: Optional[str] = None,
            stage_bucket: Optional[str] = None,
            build_service_account: Optional[str] = None,
            build_worker_pool: Optional[str] = None,

            # Labels & Metadata
            update_labels: Optional[Dict[str, str]] = None,

            # Additional Configuration
            retry: bool = False,
            runtime_update_policy: Optional[str] = None,  # automatic, on-deploy
            serve_all_traffic_latest_revision: bool = False,
            trigger_location: Optional[str] = None,

            # Secrets & Encryption
            set_secrets: Optional[Dict[str, str]] = None,
            update_secrets: Optional[Dict[str, str]] = None,
            remove_secrets: Optional[List[str]] = None,
            kms_key: Optional[str] = None,

            # VPC Configuration
            vpc_connector: Optional[str] = None,

            # Binary Authorization
            binary_authorization: Optional[str] = None,

            # Environment variable management (alternative to env_vars)
            env_vars_file: Optional[str] = None,
            update_env_vars: Optional[Dict[str, str]] = None,
            remove_env_vars: Optional[List[str]] = None,

            # Build environment variable management (alternative to build_env_vars)
            set_build_env_vars: Optional[Dict[str, str]] = None,
            update_build_env_vars: Optional[Dict[str, str]] = None,
            remove_build_env_vars: Optional[List[str]] = None,

            # Clear flags
            clear_env_vars: bool = False,
            clear_build_env_vars: bool = False,
            clear_binary_authorization: bool = False,
            clear_build_service_account: bool = False,
            clear_build_worker_pool: bool = False,
            clear_docker_repository: bool = False,
            clear_kms_key: bool = False,
            clear_labels: bool = False,
            clear_max_instances: bool = False,
            clear_min_instances: bool = False,
            clear_secrets: bool = False,
            clear_vpc_connector: bool = False,
            remove_labels: Optional[List[str]] = None,
    ):
        # Mandatory params that don't have default and must be set to actually make the deployment work
        self.function_name = function_name
        self.region = region
        self.runtime = runtime
        self.entry_point = entry_point
        self.source_code_dir = source_code_dir

        # Env vars
        self.env_vars = env_vars


        # Basic configuration
        self.gen2 = gen2
        self.ignore_file = ignore_file
        # Networking & Security
        self.ingress_settings = ingress_settings
        self.egress_settings = egress_settings
        self.security_level = security_level
        # Service Accounts & Authorization
        self.service_account = service_account
        self.run_service_account = run_service_account
        self.trigger_service_account = trigger_service_account
        # Build & Deployment
        self.build_env_vars = build_env_vars
        self.build_env_vars_file = build_env_vars_file
        self.docker_registry = docker_registry
        self.docker_repository = docker_repository
        self.stage_bucket = stage_bucket
        self.build_service_account = build_service_account
        self.build_worker_pool = build_worker_pool
        # Labels & Metadata
        self.update_labels = update_labels
        # Additional Configuration
        self.retry = retry
        self.runtime_update_policy = runtime_update_policy
        self.serve_all_traffic_latest_revision = serve_all_traffic_latest_revision
        self.trigger_location = trigger_location
        # Triggers
        self.trigger_http = trigger_http
        self.trigger_bucket = trigger_bucket
        self.trigger_topic = trigger_topic
        self.trigger_event = trigger_event
        self.trigger_resource = trigger_resource
        self.trigger_event_filters = trigger_event_filters
        self.trigger_event_filters_path_pattern = trigger_event_filters_path_pattern
        # Secrets & Encryption
        self.set_secrets = set_secrets
        self.update_secrets = update_secrets
        self.remove_secrets = remove_secrets
        self.kms_key = kms_key
        # VPC Configuration
        self.vpc_connector = vpc_connector
        # Binary Authorization
        self.binary_authorization = binary_authorization
        # Environment variable management
        self.env_vars_file = env_vars_file
        self.update_env_vars = update_env_vars
        self.remove_env_vars = remove_env_vars
        # Build environment variable management
        self.set_build_env_vars = set_build_env_vars
        self.update_build_env_vars = update_build_env_vars
        self.remove_build_env_vars = remove_build_env_vars
        # Clear flags
        self.clear_env_vars = clear_env_vars
        self.clear_build_env_vars = clear_build_env_vars
        self.clear_binary_authorization = clear_binary_authorization
        self.clear_build_service_account = clear_build_service_account
        self.clear_build_worker_pool = clear_build_worker_pool
        self.clear_docker_repository = clear_docker_repository
        self.clear_kms_key = clear_kms_key
        self.clear_labels = clear_labels
        self.clear_max_instances = clear_max_instances
        self.clear_min_instances = clear_min_instances
        self.clear_secrets = clear_secrets
        self.clear_vpc_connector = clear_vpc_connector
        self.remove_labels = remove_labels
        self.memory = memory
        self.cpu = cpu
        self.concurrency = concurrency
        self.max_instances = max_instances
        self.min_instances = min_instances
        self.timeout = timeout
        self.project = project
        self.allow_unauthenticated = allow_unauthenticated
        self.deployment_timeout = deployment_timeout
        self.quiet = quiet

    @classmethod
    def create(cls,
               # Mandatory params that don't have default and will fail the deployment if not actually set
               # * syntax means only named arguments are accepted
               *,
               function_name: str,
               region: str,
               runtime: str,
               entry_point: str,
               source_code_dir: Path,

               # commonly used parameters
               memory: str,
               cpu: str,
               concurrency: int,
               max_instances: int,
               min_instances: int,
               timeout: int,
               project: str,
               allow_unauthenticated: bool,
               deployment_timeout: int,
               quiet: bool,
               gen2: bool,
               env_vars: Optional[Dict[str, str]] = None,

               # rest of parameters
               **kwargs
               ) -> 'GCFDeployCommandParameters':

        return cls._create(function_name=function_name,
                   region=region,
                   runtime=runtime,
                   entry_point=entry_point,
                   source_code_dir=source_code_dir,
                   memory=memory,
                   cpu=cpu,
                   concurrency=concurrency,
                   max_instances=max_instances,
                   min_instances=min_instances,
                   timeout=timeout,
                   project=project,
                   allow_unauthenticated=allow_unauthenticated,
                   deployment_timeout=deployment_timeout,
                   quiet=quiet,
                   gen2=gen2,
                   env_vars=env_vars,
                   **kwargs)

    def build_gcloud_command(self) -> List[str]:
        """Build the gcloud functions deploy command with all specified parameters."""

        for index, param in enumerate([self.function_name, self.region, self.runtime, self.entry_point, self.source_code_dir]):
            if param is None:
                raise Exception(f'Missing mandatory parameter. index in the above list: {index}')

        cmd = ['gcloud', 'functions', 'deploy', self.function_name]

        # Basic configuration
        if self.gen2:
            cmd.append('--gen2')
        else:
            cmd.append('--no-gen2')
        if self.ignore_file:
            cmd.append(f'--ignore-file={self.ignore_file}')

        # Required parameters
        cmd.extend([
            f'--runtime={self.runtime}',
            f'--region={self.region}',
            f'--source={self.source_code_dir}',
            f'--entry-point={self.entry_point}',
            f'--project={self.project}',
        ])

        # Networking & Security
        if self.allow_unauthenticated:
            cmd.append('--allow-unauthenticated')
        else:
            cmd.append('--no-allow-unauthenticated')
        if self.ingress_settings:
            cmd.append(f'--ingress-settings={self.ingress_settings}')
        if self.egress_settings:
            cmd.append(f'--egress-settings={self.egress_settings}')
        if self.security_level and not self.gen2:
            cmd.append(f'--security-level={self.security_level}')

        # Performance & Scaling
        if self.clear_max_instances:
            cmd.append('--clear-max-instances')
        elif self.max_instances is not None:
            cmd.append(f'--max-instances={self.max_instances}')
        if self.clear_min_instances:
            cmd.append('--clear-min-instances')
        elif self.min_instances is not None:
            cmd.append(f'--min-instances={self.min_instances}')
        if self.timeout is not None:
            cmd.append(f'--timeout={self.timeout}')
        if self.concurrency is not None:
            cmd.append(f'--concurrency={self.concurrency}')

        # Service Accounts & Authorization
        if self.service_account:
            cmd.append(f'--service-account={self.service_account}')
        if self.run_service_account:
            cmd.append(f'--run-service-account={self.run_service_account}')
        if self.trigger_service_account:
            cmd.append(f'--trigger-service-account={self.trigger_service_account}')

        # Build & Deployment
        if self.build_env_vars_file:
            cmd.append(f'--build-env-vars-file={self.build_env_vars_file}')
        elif self.clear_build_env_vars:
            cmd.append('--clear-build-env-vars')
        elif self.set_build_env_vars:
            build_vars = ",".join([f"{k}={v}" for k, v in self.set_build_env_vars.items()])
            cmd.append(f'--set-build-env-vars={build_vars}')
        elif self.build_env_vars:
            build_vars = ",".join([f"{k}={v}" for k, v in self.build_env_vars.items()])
            cmd.append(f'--set-build-env-vars={build_vars}')
        else:
            if self.update_build_env_vars:
                build_vars = ",".join([f"{k}={v}" for k, v in self.update_build_env_vars.items()])
                cmd.append(f'--update-build-env-vars={build_vars}')
            if self.remove_build_env_vars:
                cmd.append(f'--remove-build-env-vars={",".join(self.remove_build_env_vars)}')

        if self.clear_build_service_account:
            cmd.append('--clear-build-service-account')
        elif self.build_service_account:
            cmd.append(f'--build-service-account={self.build_service_account}')

        if self.clear_build_worker_pool:
            cmd.append('--clear-build-worker-pool')
        elif self.build_worker_pool:
            cmd.append(f'--build-worker-pool={self.build_worker_pool}')

        if self.clear_docker_repository:
            cmd.append('--clear-docker-repository')
        elif self.docker_repository:
            cmd.append(f'--docker-repository={self.docker_repository}')

        if self.docker_registry:
            cmd.append(f'--docker-registry={self.docker_registry}')
        if self.stage_bucket:
            cmd.append(f'--stage-bucket={self.stage_bucket}')

        # Environment Variables
        if self.env_vars_file:
            cmd.append(f'--env-vars-file={self.env_vars_file}')
        elif self.clear_env_vars:
            cmd.append('--clear-env-vars')
        elif self.env_vars and len(self.env_vars) > 0:
            env_vars_str = ",".join([f"{key}={value}" for key, value in self.env_vars.items()])
            cmd.append(f'--set-env-vars={env_vars_str}')
        else:
            if self.update_env_vars:
                env_vars_str = ",".join([f"{key}={value}" for key, value in self.update_env_vars.items()])
                cmd.append(f'--update-env-vars={env_vars_str}')
            if self.remove_env_vars:
                cmd.append(f'--remove-env-vars={",".join(self.remove_env_vars)}')

        # Labels & Metadata
        if self.clear_labels:
            cmd.append('--clear-labels')
        if self.remove_labels:
            cmd.append(f'--remove-labels={",".join(self.remove_labels)}')
        if self.update_labels:
            labels_str = ",".join([f"{k}={v}" for k, v in self.update_labels.items()])
            cmd.append(f'--update-labels={labels_str}')

        # Resource Configuration
        if self.memory:
            cmd.append(f'--memory={self.memory}')
        if self.cpu:
            cmd.append(f'--cpu={self.cpu}')

        # Additional Configuration
        if self.retry:
            cmd.append('--retry')
        if self.runtime_update_policy:
            cmd.append(f'--runtime-update-policy={self.runtime_update_policy}')
        if self.serve_all_traffic_latest_revision:
            cmd.append('--serve-all-traffic-latest-revision')
        if self.trigger_location:
            cmd.append(f'--trigger-location={self.trigger_location}')

        # Triggers (mutually exclusive)
        if self.trigger_http:
            cmd.append('--trigger-http')
        elif self.trigger_bucket:
            cmd.append(f'--trigger-bucket={self.trigger_bucket}')
        elif self.trigger_topic:
            cmd.append(f'--trigger-topic={self.trigger_topic}')
        elif self.trigger_event:
            cmd.append(f'--trigger-event={self.trigger_event}')
            if self.trigger_resource:
                cmd.append(f'--trigger-resource={self.trigger_resource}')
        elif self.trigger_event_filters:
            filters_str = ",".join([f"{k}={v}" for k, v in self.trigger_event_filters.items()])
            cmd.append(f'--trigger-event-filters={filters_str}')
            if self.trigger_event_filters_path_pattern:
                pattern_str = ",".join([f"{k}={v}" for k, v in self.trigger_event_filters_path_pattern.items()])
                cmd.append(f'--trigger-event-filters-path-pattern={pattern_str}')

        # Secrets & Encryption
        if self.clear_secrets:
            cmd.append('--clear-secrets')
        elif self.set_secrets:
            secrets_str = ",".join([f"{k}={v}" for k, v in self.set_secrets.items()])
            cmd.append(f'--set-secrets={secrets_str}')
        else:
            if self.update_secrets:
                secrets_str = ",".join([f"{k}={v}" for k, v in self.update_secrets.items()])
                cmd.append(f'--update-secrets={secrets_str}')
            if self.remove_secrets:
                cmd.append(f'--remove-secrets={",".join(self.remove_secrets)}')

        if self.clear_kms_key:
            cmd.append('--clear-kms-key')
        elif self.kms_key:
            cmd.append(f'--kms-key={self.kms_key}')

        # VPC Configuration
        if self.clear_vpc_connector:
            cmd.append('--clear-vpc-connector')
        elif self.vpc_connector:
            cmd.append(f'--vpc-connector={self.vpc_connector}')

        # Binary Authorization
        if self.clear_binary_authorization:
            cmd.append('--clear-binary-authorization')
        elif self.binary_authorization:
            cmd.append(f'--binary-authorization={self.binary_authorization}')

        # Quiet flag
        if self.quiet:
            cmd.append('--quiet')

        return cmd


