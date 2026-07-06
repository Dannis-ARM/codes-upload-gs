"""Reporter for generating test logs and reports."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .client import Response
from .comparator import ComparisonResult


@dataclass
class TestResult:
    """Result of a single test case."""
    name: str
    success: bool
    before_url: str
    after_url: str
    before_status: int
    after_status: int
    before_elapsed: float
    after_elapsed: float
    diff: str = ""
    error: str = ""


class Reporter:
    """Test reporter that handles console output and file logging."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.console = Console()
        self.results: List[TestResult] = []
        self.start_time = datetime.now()

        os.makedirs(log_dir, exist_ok=True)

    def record_test(
        self,
        name: str,
        before_resp: Response,
        after_resp: Response,
        comparison: ComparisonResult,
        error: str = "",
    ) -> None:
        """Record a test result."""
        self.results.append(TestResult(
            name=name,
            success=comparison.match and not error,
            before_url=before_resp.url,
            after_url=after_resp.url,
            before_status=before_resp.status_code,
            after_status=after_resp.status_code,
            before_elapsed=before_resp.elapsed_seconds,
            after_elapsed=after_resp.elapsed_seconds,
            diff=comparison.diff,
            error=error,
        ))

    def print_summary(self) -> None:
        """Print test summary to console."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        success_count = sum(1 for r in self.results if r.success)
        total_count = len(self.results)

        # Summary table
        table = Table(title="Migration API Check Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Total APIs", str(total_count))
        table.add_row("Passed", f"[green]{success_count}[/green]")
        table.add_row("Failed", f"[red]{total_count - success_count}[/red]")
        table.add_row("Duration", f"{duration:.2f}s")

        self.console.print(table)

        # Failed tests details
        failed = [r for r in self.results if not r.success]
        if failed:
            self.console.print("\n[red]Failed Tests:[/red]")
            for r in failed:
                self.console.print(f"\n  [bold]{r.name}[/bold]")
                if r.error:
                    self.console.print(f"    [red]Error:[/red] {r.error}")
                if r.diff:
                    # Parse diff lines and render with colors
                    diff_lines = r.diff.splitlines()
                    if diff_lines:
                        formatted_diff = Text()
                        for line in diff_lines:
                            if line.startswith('---'):
                                formatted_diff.append(line + "\n", style="blue")
                            elif line.startswith('+++'):
                                formatted_diff.append(line + "\n", style="blue")
                            elif line.startswith('-'):
                                formatted_diff.append(line + "\n", style="red")
                            elif line.startswith('+'):
                                formatted_diff.append(line + "\n", style="green")
                            elif line.startswith('@'):
                                formatted_diff.append(line + "\n", style="cyan")
                            else:
                                formatted_diff.append(line + "\n", style="white")
                        self.console.print(Panel(formatted_diff, title="Response Diff", border_style="yellow"))

    def save_report(self) -> str:
        """Save full report to file and return the path."""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        json_path = os.path.join(self.log_dir, f"report_{timestamp}.json")
        report_data = {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success),
            }
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Save plain text log
        log_path = os.path.join(self.log_dir, f"migration_check_{timestamp}.log")
        with open(log_path, "w", encoding="utf-8") as f:
            for r in self.results:
                status = "PASS" if r.success else "FAIL"
                f.write(f"[{status}] {r.name}\n")
                f.write(f"  Before: {r.before_url} (status: {r.before_status}, {r.before_elapsed:.3f}s)\n")
                f.write(f"  After:  {r.after_url} (status: {r.after_status}, {r.after_elapsed:.3f}s)\n")
                if r.error:
                    f.write(f"  Error: {r.error}\n")
                if r.diff:
                    f.write(f"  Diff:\n{r.diff}\n")
                f.write("\n")

        return json_path

    def save_worker_result(self, worker_id: str, result: TestResult) -> str:
        """Save a single test result from a worker to its own file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"worker_{worker_id}_{timestamp}.json"
        filepath = os.path.join(self.log_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(result)], f, indent=2, ensure_ascii=False)

        return filepath

    @staticmethod
    def load_and_merge(log_dir: str = "logs") -> str:
        """Load all worker result files and merge into one report."""
        logs_path = Path(log_dir)
        if not logs_path.exists():
            return ""

        all_results: List[Dict] = []
        worker_files = list(logs_path.glob("worker_*.json"))

        for worker_file in worker_files:
            try:
                with open(worker_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    all_results.extend(data)
            except Exception:
                continue

        if not all_results:
            return ""

        # Create merged report
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

        report_file = logs_path / f"report_{timestamp}_merged.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Clean up worker files
        for worker_file in worker_files:
            try:
                worker_file.unlink()
            except Exception:
                pass

        return str(report_file)


# Global reporter instance
_reporter: Optional[Reporter] = None


def get_reporter() -> Reporter:
    """Get or create the global reporter instance."""
    global _reporter
    if _reporter is None:
        _reporter = Reporter()
    return _reporter
