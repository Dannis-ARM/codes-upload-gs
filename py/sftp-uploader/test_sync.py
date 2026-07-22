#!/usr/bin/env python3
"""
Unit tests for sync.py - test command building logic without needing sftp.
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from sync import build_sftp_batch_script


def test_batch_script_download():
    """Test batch script for actual download."""
    script = build_sftp_batch_script(
        remote_path="/remote/data",
        local_path="/local/data",
        dry_run=False,
    )

    print("Test 1 - Download batch script:")
    print("  " + script.replace("\n", "\n  "))
    print()

    assert "cd /remote/data" in script
    assert "lcd /local/data" in script
    assert "get -r ." in script
    assert "quit" in script
    assert "ls -la" not in script


def test_batch_script_dry_run():
    """Test batch script for dry run."""
    script = build_sftp_batch_script(
        remote_path="/remote/data",
        local_path="/local/data",
        dry_run=True,
    )

    print("Test 2 - Dry-run batch script:")
    print("  " + script.replace("\n", "\n  "))
    print()

    assert "cd /remote/data" in script
    assert "lcd /local/data" in script
    assert "ls -la" in script
    assert "get -r ." not in script
    assert "quit" in script


def main():
    print("=" * 60)
    print("Running sync.py unit tests")
    print("=" * 60)
    print()

    test_batch_script_download()
    test_batch_script_dry_run()

    print("=" * 60)
    print("[OK] All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
