"""
Hash calculation utilities.
"""
import hashlib
import os
import logging

logger = logging.getLogger(__name__)


class HashUtils:
    """
    Utilities for calculating file hashes.
    """

    @staticmethod
    def calculate_md5(
        file_path: str,
        chunk_size: int = 65536,
    ) -> str:
        """
        Calculate MD5 hash of a single file.

        Args:
            file_path: Path to the file
            chunk_size: Read buffer size in bytes (default: 64KB)

        Returns:
            Hexadecimal MD5 hash string

        Raises:
            FileNotFoundError: If file doesn't exist
            OSError: If file read fails

        Example:
            >>> md5 = HashUtils.calculate_md5("/tmp/file.txt")
            >>> print(md5)
            'd41d8cd98f00b204e9800998ecf8427e'
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if os.path.isdir(file_path):
            raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")

        logger.debug(f"Calculating MD5 for {file_path}")

        md5_hash = hashlib.md5()

        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(chunk_size), b""):
                md5_hash.update(chunk)

        result = md5_hash.hexdigest()
        logger.debug(f"MD5 for {file_path}: {result}")

        return result

    @staticmethod
    def verify_md5(
        file_path: str,
        expected_md5: str,
    ) -> bool:
        """
        Verify file against expected MD5 hash.

        Args:
            file_path: Path to the file
            expected_md5: Expected MD5 hash string

        Returns:
            True if hash matches, False otherwise

        Raises:
            FileNotFoundError: If file doesn't exist

        Example:
            >>> HashUtils.verify_md5("/tmp/file.txt", "d41d8cd98f00b204e9800998ecf8427e")
            True
        """
        actual_md5 = HashUtils.calculate_md5(file_path)
        return actual_md5.lower() == expected_md5.lower()
