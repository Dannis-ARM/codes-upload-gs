"""Response comparison logic using DeepDiff."""

from typing import Any
from dataclasses import dataclass

from deepdiff import DeepDiff

from .types import Response, CompareOptions


@dataclass
class ComparisonResult:
    """Result of response comparison."""
    match: bool
    diff: str = ""
    details: Any = None


def _fast_check_diff(before: Any, after: Any, path: str = "root") -> Optional[str]:
    """
    Fast pre-check for obvious differences before calling DeepDiff.
    Returns a diff string if differences found, None otherwise.
    """
    # Check type
    if type(before) != type(after):
        return f"Type mismatch at {path}: {type(before)} != {type(after)}"

    # Check list length first (performance optimization for large arrays)
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return f"List length mismatch at {path}: {len(before)} != {len(after)}"
        # Don't check each element for performance - let DeepDiff handle that if needed

    # Check dict keys first, then recursively check values
    if isinstance(before, dict) and isinstance(after, dict):
        before_keys = set(before.keys())
        after_keys = set(after.keys())
        if before_keys != after_keys:
            added = after_keys - before_keys
            removed = before_keys - after_keys
            parts = []
            if added:
                parts.append(f"Added keys: {sorted(added)}")
            if removed:
                parts.append(f"Removed keys: {sorted(removed)}")
            return f"Dict keys mismatch at {path}: " + ", ".join(parts)

        # Recursively check common keys (for nested large arrays like 'payload')
        for key in before_keys & after_keys:
            child_path = f"{path}['{key}']"
            child_diff = _fast_check_diff(before[key], after[key], child_path)
            if child_diff:
                return child_diff

    return None


def compare_responses(
    before_resp: Response,
    after_resp: Response,
    compare_options: CompareOptions = None,
) -> ComparisonResult:
    """
    Compare two API responses using DeepDiff.

    Args:
        before_resp: Response from old API.
        after_resp: Response from new API.
        compare_options: DeepDiff comparison options.

    Returns:
        ComparisonResult with match status and diff.
    """
    if compare_options is None:
        compare_options = CompareOptions()

    details = {
        "before_url": before_resp.url,
        "after_url": after_resp.url,
        "before_status": before_resp.status_code,
        "after_status": after_resp.status_code,
    }

    # 1. Compare status codes
    if before_resp.status_code != after_resp.status_code:
        return ComparisonResult(
            match=False,
            diff=f"Status code mismatch: {before_resp.status_code} != {after_resp.status_code}",
            details=details,
        )

    # 2. Fast pre-check (for large arrays/dicts)
    fast_diff = _fast_check_diff(before_resp.body, after_resp.body)
    if fast_diff:
        return ComparisonResult(
            match=False,
            diff=fast_diff,
            details=details,
        )

    # 3. Compare bodies with DeepDiff
    diff = DeepDiff(
        before_resp.body,
        after_resp.body,
        exclude_paths=compare_options.exclude_paths,
        exclude_regex_paths=compare_options.exclude_regex_paths,
        ignore_order=compare_options.ignore_order,
        ignore_numeric_type_changes=compare_options.ignore_numeric_type_changes,
        verbose_level=1,  # 降低 verbose 级别，减少输出
        cache_size=0,     # 禁用缓存，节省内存
        view='tree',      # 使用 tree 视图，性能更好
    )

    if diff:
        return ComparisonResult(
            match=False,
            diff=diff.pretty(),
            details=details,
        )

    return ComparisonResult(match=True, details=details)
