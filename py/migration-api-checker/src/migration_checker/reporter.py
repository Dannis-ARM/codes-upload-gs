"""Reporter for generating test logs and reports."""

import json
import os
import shutil
import string
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from importlib import resources

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .client import Response
from .comparator import ComparisonResult
from .types import ApiTestResult

# Cached template content
_HTML_TEMPLATE: Optional[str] = None


def _get_html_template() -> str:
    """Get HTML template content, cached on first load.

    Returns:
        HTML template string.
    """
    global _HTML_TEMPLATE
    if _HTML_TEMPLATE is None:
        _HTML_TEMPLATE = resources.read_text("migration_checker.templates", "report.html")
    return _HTML_TEMPLATE


def _escape_html(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: Text to escape.

    Returns:
        Escaped text.
    """
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _format_diff_html(diff_text: str, max_lines: int = 20) -> str:
    """Format diff text into HTML with color coding, truncating if too long.

    Args:
        diff_text: Raw diff text.
        max_lines: Maximum lines to show before truncating.

    Returns:
        Formatted HTML string.
    """
    if not diff_text:
        return ""

    lines = diff_text.split("\n")
    html_lines: List[str] = []
    truncated = False

    for idx, line in enumerate(lines):
        if idx >= max_lines:
            truncated = True
            break

        line_stripped = line.strip()
        if (
            line_stripped.startswith("Values changed")
            or line_stripped.startswith("Dictionary item")
            or line_stripped.startswith("Item added")
            or line_stripped.startswith("Item removed")
            or line_stripped.startswith("Type changed")
        ):
            html_lines.append(f'<div class="diff-line changed">{_escape_html(line)}</div>')
        elif "old_value:" in line or line_stripped.startswith("-"):
            html_lines.append(f'<div class="diff-line removed">{_escape_html(line)}</div>')
        elif "new_value:" in line or line_stripped.startswith("+"):
            html_lines.append(f'<div class="diff-line added">{_escape_html(line)}</div>')
        elif line_stripped:
            html_lines.append(f'<div class="diff-line normal">{_escape_html(line)}</div>')
        else:
            html_lines.append('<div class="diff-line normal">&nbsp;</div>')

    if truncated:
        html_lines.append(
            '<div class="diff-line normal" style="color: #fbbf24; font-style: italic;">'
            "... (truncated, see JSON report for full diff)</div>"
        )

    return "".join(html_lines)


def _generate_test_rows(results: List[ApiTestResult]) -> str:
    """Generate HTML table rows for test results.

    Args:
        results: List of test results.

    Returns:
        HTML string with table rows.
    """
    test_rows: List[str] = []
    append = test_rows.append  # Cache method for speed

    for idx, r in enumerate(results):
        status_class = "pass" if r.success else "fail"
        status_text = "✅ PASS" if r.success else "❌ FAIL"
        row_id = f"test-{idx}"

        # Build details content - always show full test name first
        details_parts: List[str] = []
        details_parts.append(
            f'<div class="name-section"><div class="section-title">Test Name</div>'
            f'<div class="full-name">{_escape_html(r.name)}</div></div>'
        )
        if r.error:
            details_parts.append(
                f'<div class="error-section"><div class="section-title">Error</div>'
                f"<pre>{_escape_html(r.error)}</pre></div>"
            )
        if r.diff:
            diff_html = _format_diff_html(r.diff)
            details_parts.append(
                f'<div class="diff-section"><div class="section-title">Diff</div>{diff_html}</div>'
            )
        details_content = "\n".join(details_parts)

        # Build name cell - always show tooltip, only truncate if >50 chars
        name_needs_truncation = len(r.name) > 50
        truncation_class = " truncate" if name_needs_truncation else ""

        # Always make test name clickable
        name_cell = f'<button class="toggle-btn{truncation_class}" onclick="toggleDetails(\'{row_id}\')" title="{_escape_html(r.name)}">{_escape_html(r.name)}</button>'

        append(f"""
        <tr class="{status_class}" data-status="{status_class}">
            <td class="status-cell">{status_text}</td>
            <td class="name-cell">
                {name_cell}
            </td>
            <td class="url-cell"><a href="{_escape_html(r.before_url)}" target="_blank" title="{_escape_html(r.before_url)}">{_escape_html(r.before_url)}</a></td>
            <td class="url-cell"><a href="{_escape_html(r.after_url)}" target="_blank" title="{_escape_html(r.after_url)}">{_escape_html(r.after_url)}</a></td>
            <td class="status-code">{r.before_status}</td>
            <td class="status-code">{r.after_status}</td>
            <td class="time">{r.before_elapsed:.3f}s</td>
            <td class="time">{r.after_elapsed:.3f}s</td>
        </tr>
        """)
        append(f"""
        <tr class="details-row" id="{row_id}">
            <td colspan="8">
                <div class="details-content">{details_content}</div>
            </td>
        </tr>
        """)

    return "".join(test_rows)


def _generate_html_content(
    results: List[ApiTestResult],
    start_time: datetime,
    end_time: Optional[datetime] = None,
) -> str:
    """Generate complete HTML report content.

    Args:
        results: List of test results.
        start_time: Test start time.
        end_time: Test end time (defaults to now).

    Returns:
        Complete HTML string.
    """
    if end_time is None:
        end_time = datetime.now()

    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed
    duration = (end_time - start_time).total_seconds()

    # Build meta section
    meta = f"Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')} | End: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"

    # Build summary cards
    summary_parts = [
        f'<div class="summary-card total" data-filter="all">Total: {total}</div>',
        f'<div class="summary-card passed" data-filter="pass">Passed: {passed}</div>',
        f'<div class="summary-card failed" data-filter="fail">Failed: {failed}</div>',
    ]
    if duration > 0:
        summary_parts.append(f'<div class="summary-card duration">Duration: {duration:.3f}s</div>')
    summary = "".join(summary_parts)

    # Build test rows
    test_rows = _generate_test_rows(results)

    # Fill template
    template = _get_html_template()
    return string.Template(template).substitute(meta=meta, summary=summary, test_rows=test_rows)


def _should_generate_html() -> bool:
    """Check if HTML generation is enabled via environment variable.

    Returns:
        True if HTML should be generated, False otherwise.
    """
    skip_html = os.environ.get("SKIP_HTML", "").lower() in ("1", "true", "yes", "y")
    return not skip_html


def _archive_current_reports(current_dir: Path, archive_dir: Path) -> None:
    """Move current reports to archive and keep only last 5.

    Args:
        current_dir: Directory with current reports.
        archive_dir: Directory to archive old reports.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Move current files to archive
    for filename in ["report-latest.json", "success-latest.json", "error-latest.json"]:
        src = current_dir / filename
        if src.exists():
            dst = archive_dir / filename.replace("-latest", f"_{timestamp}")
            shutil.move(str(src), str(dst))

    # Clean up old archives - keep last 5 groups
    archive_files = sorted(archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    groups: Dict[str, List[Path]] = {}
    for f in archive_files:
        parts = f.stem.split("_")
        if len(parts) >= 3:
            ts_key = f"{parts[1]}_{parts[2]}"
            groups.setdefault(ts_key, []).append(f)
    sorted_groups = sorted(groups.keys(), reverse=True)
    for old_group in sorted_groups[5:]:
        for f in groups[old_group]:
            try:
                f.unlink()
            except Exception:
                pass


class Reporter:
    """Test reporter that handles console output and file logging."""

    def __init__(self, log_dir: str = "logs", generate_html: Optional[bool] = None):
        """Initialize reporter.

        Args:
            log_dir: Directory to store logs.
            generate_html: Whether to generate HTML report.
                If None, checks SKIP_HTML environment variable.
        """
        self.log_dir = Path(log_dir)
        self.current_dir = self.log_dir / "current"
        self.archive_dir = self.log_dir / "archive"
        self.console = Console()
        self.results: List[ApiTestResult] = []
        self.start_time = datetime.now()

        # Determine if HTML should be generated
        if generate_html is None:
            self.generate_html = _should_generate_html()
        else:
            self.generate_html = generate_html

        # Create directories
        self.current_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def record_test(
        self,
        name: str,
        before_resp: Response,
        after_resp: Response,
        comparison: ComparisonResult,
        error: str = "",
    ) -> None:
        """Record a test result.

        Args:
            name: Test name.
            before_resp: Response from before migration.
            after_resp: Response from after migration.
            comparison: Comparison result.
            error: Error message if any.
        """
        self.results.append(ApiTestResult(
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
                    # Render DeepDiff output with basic coloring
                    diff_lines = r.diff.splitlines()
                    if diff_lines:
                        formatted_diff = Text()
                        for line in diff_lines:
                            if (line.startswith('Values changed') or line.startswith('Dictionary item')
                                    or line.startswith('Item added') or line.startswith('Item removed')):
                                formatted_diff.append(line + "\n", style="yellow")
                            elif 'old_value:' in line:
                                formatted_diff.append(line + "\n", style="red")
                            elif 'new_value:' in line:
                                formatted_diff.append(line + "\n", style="green")
                            else:
                                formatted_diff.append(line + "\n", style="white")
                        self.console.print(Panel(formatted_diff, title="Response Diff", border_style="yellow"))

    def _build_report_data(self, results: List[ApiTestResult]) -> Dict[str, Any]:
        """Build report data structure.

        Args:
            results: List of test results.

        Returns:
            Report data dictionary.
        """
        results_with_emoji = []
        for r in results:
            result_dict = asdict(r)
            result_dict["status_emoji"] = "✅" if r.success else "❌"
            results_with_emoji.append(result_dict)

        return {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "results": results_with_emoji,
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
            }
        }

    def _save_report_file(self, filepath: Path, results: List[ApiTestResult]) -> None:
        """Save report to a specific file.

        Args:
            filepath: Path to save to.
            results: List of test results.
        """
        report_data = self._build_report_data(results)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

    def save_report(self) -> str:
        """Save full report, success report, and error report.

        Returns:
            Path to the full report.
        """
        # Archive old current reports
        _archive_current_reports(self.current_dir, self.archive_dir)

        # Save latest reports to current/
        full_report_path = self.current_dir / "report-latest.json"
        success_report_path = self.current_dir / "success-latest.json"
        error_report_path = self.current_dir / "error-latest.json"

        success_results = [r for r in self.results if r.success]
        error_results = [r for r in self.results if not r.success]

        self._save_report_file(full_report_path, self.results)
        self._save_report_file(success_report_path, success_results)
        self._save_report_file(error_report_path, error_results)

        # Also save timestamped version to archive for completeness
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        timestamped_path = self.archive_dir / f"report_{timestamp}.json"
        self._save_report_file(timestamped_path, self.results)

        # Save HTML report if enabled
        if self.generate_html:
            html_latest_path = self.current_dir / "report-latest.html"
            html_archive_path = self.archive_dir / f"report_{timestamp}.html"
            html_content = _generate_html_content(self.results, self.start_time)
            with open(html_latest_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            with open(html_archive_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        # Save plain text log
        log_path = self.archive_dir / f"migration_check_{timestamp}.log"
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

        return str(full_report_path)

    def save_worker_result(self, worker_id: str, result: ApiTestResult) -> str:
        """Save a single test result from a worker to its own file.

        Args:
            worker_id: Worker ID.
            result: Test result.

        Returns:
            Path to the saved file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"worker_{worker_id}_{timestamp}.json"
        filepath = self.log_dir / filename

        result_dict = asdict(result)
        result_dict["status_emoji"] = "✅" if result.success else "❌"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([result_dict], f, indent=2, ensure_ascii=False)

        return str(filepath)

    @staticmethod
    def load_and_merge(log_dir: str = "logs") -> Optional[str]:
        """Load all worker result files and merge into one report.

        Args:
            log_dir: Log directory path.

        Returns:
            Path to the merged full report, or None if no results.
        """
        logs_path = Path(log_dir)
        if not logs_path.exists():
            return None

        current_dir = logs_path / "current"
        archive_dir = logs_path / "archive"
        current_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)

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
            return None

        # Convert dicts back to ApiTestResult for processing
        from .types import ApiTestResult

        results_objs = []
        for r_dict in all_results:
            # Remove status_emoji before recreating
            r_dict.pop("status_emoji", None)
            results_objs.append(ApiTestResult(**r_dict))

        # Archive old current reports
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _archive_current_reports(current_dir, archive_dir)

        # Build and save reports
        def build_and_save_json(filepath: Path, results: List[ApiTestResult]) -> None:
            results_with_emoji = []
            for r in results:
                rd = asdict(r)
                rd["status_emoji"] = "✅" if r.success else "❌"
                results_with_emoji.append(rd)
            report_data = {
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
                "results": results_with_emoji,
                "summary": {
                    "total": len(results),
                    "passed": sum(1 for r in results if r.success),
                    "failed": sum(1 for r in results if not r.success),
                }
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

        success_results = [r for r in results_objs if r.success]
        error_results = [r for r in results_objs if not r.success]

        full_report_path = current_dir / "report-latest.json"
        success_report_path = current_dir / "success-latest.json"
        error_report_path = current_dir / "error-latest.json"
        html_latest_path = current_dir / "report-latest.html"
        html_archive_path = archive_dir / f"report_{timestamp}.html"

        build_and_save_json(full_report_path, results_objs)
        build_and_save_json(success_report_path, success_results)
        build_and_save_json(error_report_path, error_results)

        # Also save timestamped full report
        build_and_save_json(archive_dir / f"report_{timestamp}.json", results_objs)

        # Save HTML reports if enabled
        if _should_generate_html():
            html_content = _generate_html_content(results_objs, datetime.now())
            with open(html_latest_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            with open(html_archive_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        # Clean up worker files
        for worker_file in worker_files:
            try:
                worker_file.unlink()
            except Exception:
                pass

        return str(full_report_path)


# Global reporter instance
_reporter: Optional[Reporter] = None


def get_reporter() -> Reporter:
    """Get or create the global reporter instance.

    Returns:
        Global reporter instance.
    """
    global _reporter
    if _reporter is None:
        _reporter = Reporter()
    return _reporter
