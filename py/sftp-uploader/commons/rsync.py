"""
Local rsync wrapper utility.
"""
import subprocess
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class RsyncTool:
    """
    Wrapper for local rsync command with exclude support.
    """

    def __init__(
        self,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize RsyncTool.

        Args:
            dry_run: If True, don't actually transfer files
            verbose: If True, show verbose output

        Example:
            >>> rsync = RsyncTool(dry_run=False, verbose=True)
        """
        self.dry_run = dry_run
        self.verbose = verbose

    @staticmethod
    def _check_rsync_available() -> None:
        """Check if rsync command is available."""
        try:
            subprocess.run(
                ["rsync", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "rsync command not found. Please install rsync first."
            )

    def sync(
        self,
        source_dir: str,
        dest_dir: str,
        exclude: Optional[List[str]] = None,
        delete: bool = False,
    ) -> int:
        """
        Sync source directory to destination using rsync.

        Args:
            source_dir: Source directory path (ends with / to copy contents)
            dest_dir: Destination directory path
            exclude: List of patterns to exclude (e.g., ["*.log", "tmp/"])
            delete: If True, delete files in dest not present in source

        Returns:
            rsync exit code (0 = success)

        Raises:
            FileNotFoundError: If source directory doesn't exist
            RuntimeError: If rsync command fails

        Example:
            >>> rsync = RsyncTool()
            >>> rsync.sync(
            ...     "/tmp/source/",
            ...     "/tmp/dest/",
            ...     exclude=["*.log", "tmp/", "__pycache__/"],
            ...     delete=True
            ... )
        """
        self._check_rsync_available()

        if not os.path.exists(source_dir):
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        # Ensure source ends with / to copy contents, not the directory itself
        if not source_dir.endswith(os.sep):
            source_dir = source_dir + os.sep

        # Build rsync command
        cmd = ["rsync", "-av"]

        if self.dry_run:
            cmd.append("--dry-run")

        if self.verbose:
            cmd.append("-v")

        if delete:
            cmd.append("--delete")

        # Add exclude patterns
        if exclude:
            for pattern in exclude:
                cmd.extend(["--exclude", pattern])

        # Add source and destination
        cmd.extend([source_dir, dest_dir])

        # Ensure destination directory exists
        os.makedirs(dest_dir, exist_ok=True)

        logger.info(f"Running rsync: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=False,
                check=False,
            )

            if result.returncode == 0:
                logger.info("rsync completed successfully")
            else:
                logger.warning(f"rsync exited with code {result.returncode}")

            return result.returncode

        except KeyboardInterrupt:
            logger.info("rsync cancelled by user")
            raise
