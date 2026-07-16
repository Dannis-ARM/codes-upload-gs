#!/usr/bin/env python3
"""
Unit tests for sync.py - test command building logic without needing rsync.
"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from sync import build_rsync_command


def test_basic_command():
    """Test basic command construction."""
    cmd = build_rsync_command(
        host="example.com",
        user="myuser",
        private_key="/home/user/.ssh/id_rsa",
        remote_path="/remote/data",
        local_path="/local/data",
    )

    print("Test 1 - Basic command:")
    print("  " + " ".join(cmd))
    print()

    assert cmd[0] == "rsync"
    assert "-avz" in cmd
    assert "ssh -i /home/user/.ssh/id_rsa -p 22" in " ".join(cmd)
    assert "myuser@example.com:/remote/data/" in cmd
    assert "/local/data/" in cmd
    assert "--dry-run" not in cmd
    assert "--progress" not in cmd


def test_with_custom_port():
    """Test custom port."""
    cmd = build_rsync_command(
        host="example.com",
        user="myuser",
        private_key="/key",
        remote_path="/remote",
        local_path="/local",
        port=2222,
    )

    print("Test 2 - Custom port:")
    print("  " + " ".join(cmd))
    print()

    assert "-p 2222" in " ".join(cmd)


def test_dry_run():
    """Test dry run mode."""
    cmd = build_rsync_command(
        host="example.com",
        user="myuser",
        private_key="/key",
        remote_path="/remote",
        local_path="/local",
        dry_run=True,
    )

    print("Test 3 - Dry run:")
    print("  " + " ".join(cmd))
    print()

    assert "--dry-run" in cmd


def test_verbose():
    """Test verbose mode."""
    cmd = build_rsync_command(
        host="example.com",
        user="myuser",
        private_key="/key",
        remote_path="/remote",
        local_path="/local",
        verbose=True,
    )

    print("Test 4 - Verbose:")
    print("  " + " ".join(cmd))
    print()

    assert "--progress" in cmd


def test_trailing_slashes():
    """Test that trailing slashes are handled correctly."""
    cmd = build_rsync_command(
        host="example.com",
        user="myuser",
        private_key="/key",
        remote_path="/remote/data/",  # with trailing slash
        local_path="/local/data/",    # with trailing slash
    )

    print("Test 5 - Trailing slashes:")
    print("  " + " ".join(cmd))
    print()

    assert "myuser@example.com:/remote/data/" in cmd
    assert "/local/data/" in cmd


def main():
    print("=" * 60)
    print("Running sync.py unit tests")
    print("=" * 60)
    print()

    test_basic_command()
    test_with_custom_port()
    test_dry_run()
    test_verbose()
    test_trailing_slashes()

    print("=" * 60)
    print("[OK] All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
