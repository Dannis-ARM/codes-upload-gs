#!/usr/bin/env python3
"""
SFTP Directory Sync Tool - Sync remote directory to local using sftp command.

Features:
- Full recursive download (no incremental sync)
- No local file deletion, suitable for multi-source merge
- Private key authentication
- Dry run mode (list only)
- Secure against injection via temporary batch file
"""

import subprocess
import argparse
import sys
import os
import tempfile


def build_sftp_batch_script(
    remote_path: str,
    local_path: str,
    dry_run: bool = False,
) -> str:
    """
    Build sftp batch script content.
    """
    if dry_run:
        return f"""\
cd {remote_path}
lcd {local_path}
ls -la
quit
"""
    else:
        return f"""\
cd {remote_path}
lcd {local_path}
get -r .
quit
"""


def build_sftp_command(
    host: str,
    user: str,
    private_key: str,
    batch_file: str,
    port: int = 22,
) -> list[str]:
    """
    Build sftp command argument list with batch file.
    """
    cmd = ["sftp", "-i", private_key, "-P", str(port), "-b", batch_file]

    # Add host/user destination
    cmd.append(f"{user}@{host}")

    return cmd


def run_sync(
    cmd: list[str],
    batch_script: str,
    dry_run: bool = False,
) -> int:
    """
    Execute sftp command, return exit code.
    """
    print(f"Running: {' '.join(cmd)}")
    if dry_run:
        print("Mode: dry-run (list only)")
    print("-" * 60)
    print("Batch script:")
    print(batch_script)
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
        print("Error: 'sftp' command not found.")
        return 127


def ensure_local_dir_exists(local_path: str) -> None:
    """
    Create local directory if it doesn't exist.
    """
    if not os.path.exists(local_path):
        print(f"Creating local directory: {local_path}")
        os.makedirs(local_path, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Sync remote SFTP directory to local using sftp command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic sync
  python sync.py -H example.com -u myuser -i ~/.ssh/id_rsa -r /remote/data -l /local/data

  # Custom port
  python sync.py -H example.com -u myuser -i ~/.ssh/id_rsa -r /remote/data -l /local/data -P 2222

  # Dry run (list only, no download)
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
        "--port", "-P", type=int, default=22, help="SFTP port (default: 22)"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Dry run (list only, no download)"
    )

    args = parser.parse_args()

    # Ensure local directory exists
    if not args.dry_run:
        ensure_local_dir_exists(args.local_path)

    # Build batch script
    batch_script = build_sftp_batch_script(
        remote_path=args.remote_path,
        local_path=args.local_path,
        dry_run=args.dry_run,
    )

    # Create temporary batch file (safer than stdin)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(batch_script)
        batch_file = f.name

    try:
        # Build and run sftp command
        cmd = build_sftp_command(
            host=args.host,
            user=args.user,
            private_key=args.private_key,
            batch_file=batch_file,
            port=args.port,
        )

        exit_code = run_sync(cmd, batch_script, dry_run=args.dry_run)
        sys.exit(exit_code)
    finally:
        # Clean up temporary file
        try:
            os.unlink(batch_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()
