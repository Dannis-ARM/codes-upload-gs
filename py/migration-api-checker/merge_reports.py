"""Merge worker report files into one (manual backup)."""

import sys
import json
from pathlib import Path


def merge_reports():
    """Merge all worker_*.json files using Reporter's merge method."""
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from migration_checker.reporter import Reporter

    merged_file = Reporter.load_and_merge()

    if merged_file:
        print("\n✅ Merged report saved to:", merged_file, "\n")

        # Let's also read and show summary
        with open(merged_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            summary = data["summary"]
            print("Summary:")
            print("  Total: ", summary["total"])
            print("  Passed:", summary["passed"])
            print("  Failed:", summary["failed"])
    else:
        print("\n❌ No worker report files found to merge!\n")


if __name__ == "__main__":
    merge_reports()
