"""Pytest configuration."""

import sys
import os
from pathlib import Path

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


def pytest_sessionfinish(session, exitstatus):
    """Merge worker reports at the end (master only)."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")

    if not worker_id or worker_id == "master":
        # Master process: try to merge worker reports
        from migration_checker.reporter import Reporter

        merged_file = Reporter.load_and_merge()
        if merged_file:
            terminal = session.config.pluginmanager.get_plugin("terminalreporter")
            if terminal:
                terminal.write_line(f"\n✅ Merged report saved to: {merged_file}\n")
