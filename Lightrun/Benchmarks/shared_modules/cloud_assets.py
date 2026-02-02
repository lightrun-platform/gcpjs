"""Cloud Asset models for tracking and cleanup."""
import abc
import subprocess
import logging
from typing import Dict, Optional

class NoSuchAsset(Exception):
    """Raised when an asset does not exist during an operation."""
    pass

class CloudAsset(abc.ABC):
    """Abstract base class for cloud assets."""

    def __init__(self, name: str, labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.labels = labels or {}

    @abc.abstractmethod
    def delete(self, logger: logging.Logger) -> bool:
        """Deletes the asset. Raise NoSuchAsset if it doesn't exist."""
        pass

    @abc.abstractmethod
    def exists(self, logger: logging.Logger) -> bool:
        """Checks if the asset exists."""
        pass

    @abc.abstractmethod
    def apply_labels(self, labels: Dict[str, str], logger: logging.Logger) -> bool:
        """Applies labels to the asset. Returns True if successful."""
        pass


class GCSSourceObject(CloudAsset):
    """Represents a Google Cloud Storage object (Source Archive)."""

    def delete(self, logger: logging.Logger) -> bool:
        if not self.exists(logger):
            raise NoSuchAsset(f"GCS object {self.name} does not exist.")
            
        try:
            logger.info(f"Deleting GCS object: {self.name}")
            result = subprocess.run(
                ['gcloud', 'storage', 'rm', self.name, '--quiet'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                logger.warning(f"Failed to delete GCS object {self.name}: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.warning(f"Exception deleting GCS object {self.name}: {e}")
            return False

    def exists(self, logger: logging.Logger) -> bool:
        try:
            result = subprocess.run(
                ['gcloud', 'storage', 'ls', self.name],
                capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Exception checking existence of {self.name}: {e}")
            return False

    def apply_labels(self, labels: Dict[str, str], logger: logging.Logger) -> bool:
        if not labels:
            return True
        try:
            label_str = ",".join([f"{k}={v}" for k, v in labels.items()])
            logger.info(f"Applying labels to {self.name}: {label_str}")
            result = subprocess.run(
                ['gcloud', 'storage', 'objects', 'update', self.name, f'--update-custom-metadata={label_str}'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                logger.warning(f"Failed to apply labels to {self.name}: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.warning(f"Exception applying labels to {self.name}: {e}")
            return False


class ArtifactRegistryImage(CloudAsset):
    """Represents an Artifact Registry Container Image."""

    def delete(self, logger: logging.Logger) -> bool:
        if not self.exists(logger):
             raise NoSuchAsset(f"Container image {self.name} does not exist.")
             
        try:
            logger.info(f"Deleting Container Image: {self.name}")
            # --delete-tags ensures we delete the image even if tagged
            result = subprocess.run(
                ['gcloud', 'artifacts', 'docker', 'images', 'delete', self.name, '--delete-tags', '--quiet'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                logger.warning(f"Failed to delete image {self.name}: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.warning(f"Exception deleting image {self.name}: {e}")
            return False

    def exists(self, logger: logging.Logger) -> bool:
        try:
            # list commands in AR can be tricky for exact matches on digests.
            # Using describe might be better but varies by version.
            # A simple list filtered might work, but 'describe' is more standard for checking existence.
            result = subprocess.run(
                ['gcloud', 'artifacts', 'docker', 'images', 'describe', self.name, '--format=value(name)'],
                capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Exception checking existence of {self.name}: {e}")
            return False

    def apply_labels(self, labels: Dict[str, str], logger: logging.Logger) -> bool:
        # Not supported easily via CLI for AR images post-creation
        logger.debug(f"Skipping label application for image {self.name} (handled via build env vars)")
        return True
