#!/usr/bin/env python3
"""
SFTP Directory Sync Tool - Sync remote directory to local using rsync over SSH/SFTP.

Features:
- Incremental sync, only download changed/new files
- No local file deletion (no --delete)
- Private key authentication
- Dry run mode support
"""

import subprocess
import argparse
import sys


def build_rsync_command(
    host: str,
    user: str,
    private_key: str,
    remote_path: str,
    local_path: str,
    port: int = 22,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[str]:
    """
    Build rsync command argument list.
    """
    # Base rsync flags:
    # -a: archive mode (preserves permissions, timestamps, recursive, etc.)
    # -v: verbose output
    # -z: compress during transfer
    cmd = ["rsync", "-avz"]

    # SSH options: specify private key and port
    ssh_opts = f"ssh -i {private_key} -p {port} -o StrictHostKeyChecking=accept-new"
    cmd.extend(["-e", ssh_opts])

    # Dry run mode
    if dry_run:
        cmd.append("--dry-run")

    # Extra verbose output with progress
    if verbose:
        cmd.append("--progress")

    # Remote path and local path
    # Note: trailing / ensures we sync directory contents, not the directory itself
    remote = f"{user}@{host}:{remote_path.rstrip('/')}/"
    local = f"{local_path.rstrip('/')}/"
    cmd.extend([remote, local])

    return cmd


def run_sync(cmd: list[str]) -> int:
    """
    Execute rsync command, return exit code.
    """
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # Output directly to terminal
            check=False,
        )
        return result.returncode
    except KeyboardInterrupt:
        print("\nSync cancelled by user.")
        return 130
    except FileNotFoundError:
        print("Error: 'rsync' command not found. Please install rsync first.")
        return 127


def main():
    parser = argparse.ArgumentParser(
        description="Sync remote SFTP directory to local using rsync.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic sync
  python sync.py -H example.com -u myuser -i ~/.ssh/id_rsa -r /remote/data -l /local/data

  # Custom port + verbose + progress
  python sync.py -H example.com -u myuser -i ~/.ssh/id_rsa -r /remote/data -l /local/data -p 2222 -v

  # Dry run (no actual download)
  python sync.py -H example.com -u myuser -i ~/.ssh/id_rsa -r /remote/data -l /local/data -n
        """,
    )

    parser.add_argument("--host", "-H", required=True, help="SFTP server hostname or IP")
    parser.add_argument("--user", "-u", required=True, help="SFTP username")
    parser.add_argument(
        "--private-key", "-i", required=True, help="Path to private key file"
    )
    parser.add_argument(
        "--remote-path", "-r", required=True, help="Remote directory path"
    )
    parser.add_argument("--local-path", "-l", required=True, help="Local directory path")

    parser.add_argument(
        "--port", "-p", type=int, default=22, help="SSH port (default: 22)"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Dry run (no actual download)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output with progress"
    )

    args = parser.parse_args()

    cmd = build_rsync_command(
        host=args.host,
        user=args.user,
        private_key=args.private_key,
        remote_path=args.remote_path,
        local_path=args.local_path,
        port=args.port,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    exit_code = run_sync(cmd)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
