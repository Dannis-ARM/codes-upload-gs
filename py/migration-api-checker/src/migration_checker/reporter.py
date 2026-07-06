"""Reporter for generating test logs and reports."""

import json
import os
from datetime import datetime
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


# Global reporter instance
_reporter: Optional[Reporter] = None


def get_reporter() -> Reporter:
    """Get or create the global reporter instance."""
    global _reporter
    if _reporter is None:
        _reporter = Reporter()
    return _reporter
