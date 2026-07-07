"""Response comparison logic using DeepDiff."""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass

from deepdiff import DeepDiff

if TYPE_CHECKING:
    from .client import Response


@dataclass
class CompareOptions:
    """Options for response comparison using DeepDiff."""
    exclude_paths: List[str] = None
    exclude_regex_paths: List[str] = None
    ignore_order: bool = False
    ignore_numeric_type_changes: bool = True

    def __post_init__(self):
        if self.exclude_paths is None:
            self.exclude_paths = []
        if self.exclude_regex_paths is None:
            self.exclude_regex_paths = []


@dataclass
class ComparisonResult:
    """Result of response comparison."""
    match: bool
    diff: str = ""
    details: Dict[str, Any] = None


def compare_responses(
    before_resp: "Response",
    after_resp: "Response",
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

    details: Dict[str, Any] = {
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

    # 2. Compare bodies with DeepDiff
    diff = DeepDiff(
        before_resp.body,
        after_resp.body,
        exclude_paths=compare_options.exclude_paths,
        exclude_regex_paths=compare_options.exclude_regex_paths,
        ignore_order=compare_options.ignore_order,
        ignore_numeric_type_changes=compare_options.ignore_numeric_type_changes,
        verbose_level=2,
    )

    if diff:
        return ComparisonResult(
            match=False,
            diff=diff.pretty(),
            details=details,
        )

    return ComparisonResult(match=True, details=details)
