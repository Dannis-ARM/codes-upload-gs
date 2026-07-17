#!/usr/bin/env python3
"""
Unit tests for sync.py - test command building logic without needing sftp.
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from sync import build_sftp_command, build_sftp_batch_script


def test_sftp_command_basic():
    """Test basic sftp command construction."""
    cmd = build_sftp_command(
        host="example.com",
        user="myuser",
        private_key="/home/user/.ssh/id_rsa",
    )

    print("Test 1 - Basic sftp command:")
    print("  " + " ".join(cmd))
    print()

    assert cmd[0] == "sftp"
    assert "-i" in cmd
    assert "/home/user/.ssh/id_rsa" in cmd
    assert "-P" in cmd
    assert "22" in cmd
    assert "myuser@example.com" in cmd


def test_sftp_command_custom_port():
    """Test sftp command with custom port."""
    cmd = build_sftp_command(
        host="example.com",
        user="myuser",
        private_key="/key",
        port=2222,
    )

    print("Test 2 - Custom port:")
    print("  " + " ".join(cmd))
    print()

    assert "-P" in cmd
    assert "2222" in cmd


def test_batch_script_download():
    """Test batch script for actual download."""
    script = build_sftp_batch_script(
        remote_path="/remote/data",
        local_path="/local/data",
        dry_run=False,
    )

    print("Test 3 - Download batch script:")
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

    print("Test 4 - Dry-run batch script:")
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

    test_sftp_command_basic()
    test_sftp_command_custom_port()
    test_batch_script_download()
    test_batch_script_dry_run()

    print("=" * 60)
    print("[OK] All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
