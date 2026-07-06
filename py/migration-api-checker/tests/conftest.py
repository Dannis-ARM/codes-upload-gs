"""Pytest configuration."""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--config",
        action="store",
        default="cfgs.yaml",
        help="Path to configuration file",
    )


# Global storage per worker
_worker_results = []
_worker_start_time = None


def pytest_sessionstart(session):
    """Initialize worker result tracking."""
    global _worker_start_time
    _worker_start_time = datetime.now()


def pytest_sessionfinish(session, exitstatus):
    """Save worker results or merge all results (master)."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")

    if worker_id and worker_id != "master":
        # Worker: save results to a unique file
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        worker_file = logs_dir / f"worker_{worker_id}_{timestamp}.json"
        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump(_worker_results, f)

    elif not worker_id or worker_id == "master":
        # Master: wait a bit for workers, then merge
        time.sleep(0.5)  # Give workers time to write files
        merge_worker_results()


def merge_worker_results():
    """Merge all worker result files into one report."""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        return

    all_results = []
    worker_files = list(logs_dir.glob("worker_*.json"))

    for worker_file in worker_files:
        try:
            with open(worker_file, "r", encoding="utf-8") as f:
                worker_data = json.load(f)
                all_results.extend(worker_data)
            worker_file.unlink()  # Delete worker file after merging
        except:
            pass

    if all_results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        success_count = sum(1 for r in all_results if r["success"])

        report = {
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "results": all_results,
            "summary": {
                "total": len(all_results),
                "passed": success_count,
                "failed": len(all_results) - success_count,
            }
        }

        report_file = logs_dir / f"report_{timestamp}_merged.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Merged report saved to: {report_file}\n")


def add_worker_result(result):
    """Add a result to worker's list."""
    _worker_results.append(result)
