"""Reporter for generating test logs and reports."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import asdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .client import Response
from .comparator import ComparisonResult
from .types import ApiTestResult


class Reporter:
    """Test reporter that handles console output and file logging."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.current_dir = self.log_dir / "current"
        self.archive_dir = self.log_dir / "archive"
        self.console = Console()
        self.results: List[ApiTestResult] = []
        self.start_time = datetime.now()

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
        """Record a test result."""
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
                            if line.startswith('Values changed') or line.startswith('Dictionary item') or line.startswith('Item added') or line.startswith('Item removed'):
                                formatted_diff.append(line + "\n", style="yellow")
                            elif 'old_value:' in line:
                                formatted_diff.append(line + "\n", style="red")
                            elif 'new_value:' in line:
                                formatted_diff.append(line + "\n", style="green")
                            else:
                                formatted_diff.append(line + "\n", style="white")
                        self.console.print(Panel(formatted_diff, title="Response Diff", border_style="yellow"))

    def _archive_current_reports(self) -> None:
        """Move current reports to archive and keep only last 5."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Move current files to archive
        for filename in ["report-latest.json", "success-latest.json", "error-latest.json"]:
            src = self.current_dir / filename
            if src.exists():
                dst = self.archive_dir / filename.replace("-latest", f"_{timestamp}")
                shutil.move(str(src), str(dst))

        # Clean up old archives - keep last 5 groups
        archive_files = sorted(self.archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        # Group by timestamp prefix
        groups: Dict[str, List[Path]] = {}
        for f in archive_files:
            # Extract timestamp from filename like report_20250707_143022.json
            parts = f.stem.split("_")
            if len(parts) >= 3:
                ts_key = f"{parts[1]}_{parts[2]}"
                groups.setdefault(ts_key, []).append(f)
        # Keep only last 5 groups
        sorted_groups = sorted(groups.keys(), reverse=True)
        for old_group in sorted_groups[5:]:
            for f in groups[old_group]:
                try:
                    f.unlink()
                except Exception:
                    pass

    def _build_report_data(self, results: List[ApiTestResult]) -> Dict[str, Any]:
        """Build report data structure."""
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
        """Save report to a specific file."""
        report_data = self._build_report_data(results)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

    def save_report(self) -> str:
        """Save full report, success report, and error report.

        Returns:
            Path to the full report.
        """
        # Archive old current reports
        self._archive_current_reports()

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

        # Save HTML report
        html_latest_path = self.current_dir / "report-latest.html"
        html_archive_path = self.archive_dir / f"report_{timestamp}.html"
        html_content = self._generate_html_report()
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

    def _generate_html_report(self) -> str:
        """Generate HTML report with inline CSS."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        # Build test result rows
        test_rows = []
        for idx, r in enumerate(self.results):
            status_class = "pass" if r.success else "fail"
            status_text = "✅ PASS" if r.success else "❌ FAIL"
            row_id = f"test-{idx}"

            # Build details content
            details_parts = []
            if r.error:
                details_parts.append(f'<div class="error-section"><div class="section-title">Error</div><pre>{self._escape_html(r.error)}</pre></div>')
            if r.diff:
                diff_html = self._format_diff_html(r.diff)
                details_parts.append(f'<div class="diff-section"><div class="section-title">Diff</div>{diff_html}</div>')
            details_content = "\n".join(details_parts) if details_parts else ""

            row = f"""
            <tr class="{status_class}">
                <td class="status-cell">{status_text}</td>
                <td class="name-cell">
                    <button class="toggle-btn" onclick="toggleDetails('{row_id}')">
                        {self._escape_html(r.name)}
                    </button>
                </td>
                <td class="url-cell"><span class="label">Before:</span> {self._escape_html(r.before_url)}</td>
                <td class="url-cell"><span class="label">After:</span> {self._escape_html(r.after_url)}</td>
                <td class="status-code">{r.before_status}</td>
                <td class="status-code">{r.after_status}</td>
                <td class="time">{r.before_elapsed:.3f}s</td>
                <td class="time">{r.after_elapsed:.3f}s</td>
            </tr>
            """
            if details_content:
                row += f"""
                <tr class="details-row" id="{row_id}">
                    <td colspan="8">
                        <div class="details-content">{details_content}</div>
                    </td>
                </tr>
                """
            test_rows.append(row)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Migration API Check Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 24px; }}
        h1 {{ color: #333; margin-bottom: 20px; font-size: 24px; }}
        .summary {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
        .summary-card {{ padding: 16px 24px; border-radius: 8px; color: white; font-weight: 600; }}
        .summary-card.total {{ background: #6366f1; }}
        .summary-card.passed {{ background: #10b981; }}
        .summary-card.failed {{ background: #ef4444; }}
        .summary-card.duration {{ background: #8b5cf6; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; font-weight: 600; color: #374151; position: sticky; top: 0; }}
        .pass {{ background: #ecfdf5; }}
        .fail {{ background: #fef2f2; }}
        .status-cell {{ font-weight: 600; }}
        .name-cell {{ font-weight: 500; }}
        .url-cell {{ font-family: monospace; font-size: 12px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .url-cell .label {{ color: #666; font-weight: 600; }}
        .status-code {{ font-family: monospace; text-align: center; }}
        .time {{ font-family: monospace; text-align: right; }}
        .toggle-btn {{ background: none; border: none; cursor: pointer; font-size: 14px; font-weight: 500; text-align: left; padding: 0; color: #3b82f6; }}
        .toggle-btn:hover {{ text-decoration: underline; }}
        .details-row {{ display: none; }}
        .details-row.show {{ display: table-row; }}
        .details-content {{ padding: 16px; background: #1f2937; border-radius: 8px; margin: 8px 0; }}
        .section-title {{ color: #fbbf24; font-weight: 600; margin-bottom: 8px; font-size: 14px; }}
        .error-section pre {{ color: #fca5a5; background: #450a0a; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 12px; line-height: 1.5; }}
        .diff-section .diff-line {{ padding: 2px 8px; font-family: monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }}
        .diff-line.added {{ background: #064e3b; color: #6ee7b7; }}
        .diff-line.removed {{ background: #450a0a; color: #fca5a5; }}
        .diff-line.changed {{ background: #431407; color: #fdba74; }}
        .diff-line.normal {{ color: #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Migration API Check Report</h1>
        <div class="meta">
            Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} | End: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        <div class="summary">
            <div class="summary-card total">Total: {total}</div>
            <div class="summary-card passed">Passed: {passed}</div>
            <div class="summary-card failed">Failed: {failed}</div>
            <div class="summary-card duration">Duration: {duration:.2f}s</div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>Test Name</th>
                    <th>Before URL</th>
                    <th>After URL</th>
                    <th>Before Status</th>
                    <th>After Status</th>
                    <th>Before Time</th>
                    <th>After Time</th>
                </tr>
            </thead>
            <tbody>
                {"".join(test_rows)}
            </tbody>
        </table>
    </div>
    <script>
        function toggleDetails(id) {{
            const row = document.getElementById(id);
            row.classList.toggle('show');
        }}
    </script>
</body>
</html>
"""
        return html

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

    def _format_diff_html(self, diff_text: str) -> str:
        """Format diff text into HTML with color coding."""
        lines = diff_text.split("\n")
        html_lines = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("Values changed") or line_stripped.startswith("Dictionary item") or \
               line_stripped.startswith("Item added") or line_stripped.startswith("Item removed") or \
               line_stripped.startswith("Type changed"):
                html_lines.append(f'<div class="diff-line changed">{self._escape_html(line)}</div>')
            elif "old_value:" in line or line_stripped.startswith("-"):
                html_lines.append(f'<div class="diff-line removed">{self._escape_html(line)}</div>')
            elif "new_value:" in line or line_stripped.startswith("+"):
                html_lines.append(f'<div class="diff-line added">{self._escape_html(line)}</div>')
            elif line_stripped:
                html_lines.append(f'<div class="diff-line normal">{self._escape_html(line)}</div>')
            else:
                html_lines.append(f'<div class="diff-line normal">&nbsp;</div>')
        return "".join(html_lines)

    def save_worker_result(self, worker_id: str, result: ApiTestResult) -> str:
        """Save a single test result from a worker to its own file."""
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
            Path to the merged full report.
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

        def build_and_save_html(filepath: Path, results: List[ApiTestResult]) -> None:
            """Build and save HTML report for merged results."""
            total = len(results)
            passed = sum(1 for r in results if r.success)
            failed = total - passed

            def escape_html(text: str) -> str:
                if not text:
                    return ""
                return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

            def format_diff_html(diff_text: str) -> str:
                lines = diff_text.split("\n")
                html_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.startswith("Values changed") or line_stripped.startswith("Dictionary item") or \
                       line_stripped.startswith("Item added") or line_stripped.startswith("Item removed") or \
                       line_stripped.startswith("Type changed"):
                        html_lines.append(f'<div class="diff-line changed">{escape_html(line)}</div>')
                    elif "old_value:" in line or line_stripped.startswith("-"):
                        html_lines.append(f'<div class="diff-line removed">{escape_html(line)}</div>')
                    elif "new_value:" in line or line_stripped.startswith("+"):
                        html_lines.append(f'<div class="diff-line added">{escape_html(line)}</div>')
                    elif line_stripped:
                        html_lines.append(f'<div class="diff-line normal">{escape_html(line)}</div>')
                    else:
                        html_lines.append(f'<div class="diff-line normal">&nbsp;</div>')
                return "".join(html_lines)

            test_rows = []
            for idx, r in enumerate(results):
                status_class = "pass" if r.success else "fail"
                status_text = "✅ PASS" if r.success else "❌ FAIL"
                row_id = f"test-{idx}"
                details_parts = []
                if r.error:
                    details_parts.append(f'<div class="error-section"><div class="section-title">Error</div><pre>{escape_html(r.error)}</pre></div>')
                if r.diff:
                    diff_html = format_diff_html(r.diff)
                    details_parts.append(f'<div class="diff-section"><div class="section-title">Diff</div>{diff_html}</div>')
                details_content = "\n".join(details_parts) if details_parts else ""
                row = f"""
                <tr class="{status_class}">
                    <td class="status-cell">{status_text}</td>
                    <td class="name-cell">
                        <button class="toggle-btn" onclick="toggleDetails('{row_id}')">
                            {escape_html(r.name)}
                        </button>
                    </td>
                    <td class="url-cell"><span class="label">Before:</span> {escape_html(r.before_url)}</td>
                    <td class="url-cell"><span class="label">After:</span> {escape_html(r.after_url)}</td>
                    <td class="status-code">{r.before_status}</td>
                    <td class="status-code">{r.after_status}</td>
                    <td class="time">{r.before_elapsed:.3f}s</td>
                    <td class="time">{r.after_elapsed:.3f}s</td>
                </tr>
                """
                if details_content:
                    row += f"""
                    <tr class="details-row" id="{row_id}">
                        <td colspan="8">
                            <div class="details-content">{details_content}</div>
                        </td>
                    </tr>
                    """
                test_rows.append(row)

            html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Migration API Check Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 24px; }}
        h1 {{ color: #333; margin-bottom: 20px; font-size: 24px; }}
        .summary {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
        .summary-card {{ padding: 16px 24px; border-radius: 8px; color: white; font-weight: 600; }}
        .summary-card.total {{ background: #6366f1; }}
        .summary-card.passed {{ background: #10b981; }}
        .summary-card.failed {{ background: #ef4444; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; font-weight: 600; color: #374151; position: sticky; top: 0; }}
        .pass {{ background: #ecfdf5; }}
        .fail {{ background: #fef2f2; }}
        .status-cell {{ font-weight: 600; }}
        .name-cell {{ font-weight: 500; }}
        .url-cell {{ font-family: monospace; font-size: 12px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .url-cell .label {{ color: #666; font-weight: 600; }}
        .status-code {{ font-family: monospace; text-align: center; }}
        .time {{ font-family: monospace; text-align: right; }}
        .toggle-btn {{ background: none; border: none; cursor: pointer; font-size: 14px; font-weight: 500; text-align: left; padding: 0; color: #3b82f6; }}
        .toggle-btn:hover {{ text-decoration: underline; }}
        .details-row {{ display: none; }}
        .details-row.show {{ display: table-row; }}
        .details-content {{ padding: 16px; background: #1f2937; border-radius: 8px; margin: 8px 0; }}
        .section-title {{ color: #fbbf24; font-weight: 600; margin-bottom: 8px; font-size: 14px; }}
        .error-section pre {{ color: #fca5a5; background: #450a0a; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 12px; line-height: 1.5; }}
        .diff-section .diff-line {{ padding: 2px 8px; font-family: monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }}
        .diff-line.added {{ background: #064e3b; color: #6ee7b7; }}
        .diff-line.removed {{ background: #450a0a; color: #fca5a5; }}
        .diff-line.changed {{ background: #431407; color: #fdba74; }}
        .diff-line.normal {{ color: #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Migration API Check Report</h1>
        <div class="meta">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        <div class="summary">
            <div class="summary-card total">Total: {total}</div>
            <div class="summary-card passed">Passed: {passed}</div>
            <div class="summary-card failed">Failed: {failed}</div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>Test Name</th>
                    <th>Before URL</th>
                    <th>After URL</th>
                    <th>Before Status</th>
                    <th>After Status</th>
                    <th>Before Time</th>
                    <th>After Time</th>
                </tr>
            </thead>
            <tbody>
                {"".join(test_rows)}
            </tbody>
        </table>
    </div>
    <script>
        function toggleDetails(id) {{
            const row = document.getElementById(id);
            row.classList.toggle('show');
        }}
    </script>
</body>
</html>
"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)

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

        # Save HTML reports
        build_and_save_html(html_latest_path, results_objs)
        build_and_save_html(html_archive_path, results_objs)

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
    """Get or create the global reporter instance."""
    global _reporter
    if _reporter is None:
        _reporter = Reporter()
    return _reporter
