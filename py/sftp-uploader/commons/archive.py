"""
Archive extraction utilities.
"""
import zipfile
import os
import logging

logger = logging.getLogger(__name__)


class ArchiveUtils:
    """
    Utilities for archive extraction.
    Currently supports zip format only.
    """

    @staticmethod
    def extract_zip(
        zip_path: str,
        dest_dir: str,
        overwrite: bool = False,
    ) -> None:
        """
        Extract a zip file to destination directory.

        Args:
            zip_path: Path to the zip file
            dest_dir: Destination directory to extract to
            overwrite: If True, overwrite existing files

        Raises:
            FileNotFoundError: If zip file doesn't exist
            zipfile.BadZipFile: If zip file is invalid
            OSError: If extraction fails

        Example:
            >>> ArchiveUtils.extract_zip("/tmp/data.zip", "/tmp/extracted")
        """
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Zip file not found: {zip_path}")

        # Ensure destination directory exists
        os.makedirs(dest_dir, exist_ok=True)

        logger.info(f"Extracting {zip_path} to {dest_dir}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Check if files would be overwritten
            if not overwrite:
                for member in zf.infolist():
                    target_path = os.path.join(dest_dir, member.filename)
                    if os.path.exists(target_path):
                        raise FileExistsError(
                            f"File already exists: {target_path}. "
                            f"Use overwrite=True to overwrite."
                        )

            # Extract all files
            zf.extractall(dest_dir)

        logger.info(f"Successfully extracted to {dest_dir}")
