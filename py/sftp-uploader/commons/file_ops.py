"""
File operation utilities (delete, move).
"""
import os
import shutil
import logging

logger = logging.getLogger(__name__)


class FileOps:
    """
    Utilities for file operations (delete, move).
    """

    @staticmethod
    def delete(
        path: str,
        recursive: bool = False,
    ) -> None:
        """
        Delete a file or directory.

        Args:
            path: Path to file or directory to delete
            recursive: Must be True to delete directories

        Raises:
            FileNotFoundError: If path doesn't exist
            IsADirectoryError: If path is directory but recursive=False
            OSError: If deletion fails

        Example:
            >>> FileOps.delete("/tmp/file.txt")
            >>> FileOps.delete("/tmp/dir", recursive=True)
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")

        if os.path.isdir(path):
            if not recursive:
                raise IsADirectoryError(
                    f"Path is a directory: {path}. "
                    f"Use recursive=True to delete directories."
                )
            logger.info(f"Deleting directory: {path}")
            shutil.rmtree(path)
        else:
            logger.info(f"Deleting file: {path}")
            os.remove(path)

        logger.info(f"Successfully deleted: {path}")

    @staticmethod
    def move(
        src_path: str,
        dest_path: str,
        recursive: bool = False,
        overwrite: bool = False,
    ) -> None:
        """
        Move a file or directory to a new location.

        Args:
            src_path: Source path
            dest_path: Destination path
            recursive: Must be True to move directories
            overwrite: If True, overwrite existing destination

        Raises:
            FileNotFoundError: If source doesn't exist
            IsADirectoryError: If source is directory but recursive=False
            FileExistsError: If destination exists and overwrite=False
            OSError: If move fails

        Example:
            >>> FileOps.move("/tmp/old.txt", "/tmp/new.txt")
            >>> FileOps.move("/tmp/old_dir", "/tmp/new_dir", recursive=True)
        """
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Source not found: {src_path}")

        if os.path.isdir(src_path) and not recursive:
            raise IsADirectoryError(
                f"Source is a directory: {src_path}. "
                f"Use recursive=True to move directories."
            )

        if os.path.exists(dest_path):
            if not overwrite:
                raise FileExistsError(
                    f"Destination already exists: {dest_path}. "
                    f"Use overwrite=True to overwrite."
                )
            # Delete existing destination first
            if os.path.isdir(dest_path):
                shutil.rmtree(dest_path)
            else:
                os.remove(dest_path)

        # Ensure parent directory of destination exists
        dest_parent = os.path.dirname(dest_path)
        if dest_parent:
            os.makedirs(dest_parent, exist_ok=True)

        logger.info(f"Moving {src_path} -> {dest_path}")

        shutil.move(src_path, dest_path)

        logger.info(f"Successfully moved to: {dest_path}")

    @staticmethod
    def copy(
        src_path: str,
        dest_path: str,
        recursive: bool = False,
        overwrite: bool = False,
    ) -> None:
        """
        Copy a file or directory to a new location.

        Args:
            src_path: Source path
            dest_path: Destination path
            recursive: Must be True to copy directories
            overwrite: If True, overwrite existing destination

        Raises:
            FileNotFoundError: If source doesn't exist
            IsADirectoryError: If source is directory but recursive=False
            FileExistsError: If destination exists and overwrite=False
            OSError: If copy fails

        Example:
            >>> FileOps.copy("/tmp/original.txt", "/tmp/copy.txt")
            >>> FileOps.copy("/tmp/original_dir", "/tmp/copy_dir", recursive=True)
        """
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Source not found: {src_path}")

        if os.path.isdir(src_path):
            if not recursive:
                raise IsADirectoryError(
                    f"Source is a directory: {src_path}. "
                    f"Use recursive=True to copy directories."
                )
            if os.path.exists(dest_path) and not overwrite:
                raise FileExistsError(
                    f"Destination already exists: {dest_path}. "
                    f"Use overwrite=True to overwrite."
                )
            logger.info(f"Copying directory: {src_path} -> {dest_path}")
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
        else:
            if os.path.exists(dest_path) and not overwrite:
                raise FileExistsError(
                    f"Destination already exists: {dest_path}. "
                    f"Use overwrite=True to overwrite."
                )
            logger.info(f"Copying file: {src_path} -> {dest_path}")
            shutil.copy2(src_path, dest_path)

        logger.info(f"Successfully copied to: {dest_path}")
