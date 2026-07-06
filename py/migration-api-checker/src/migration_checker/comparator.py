"""Response comparison logic."""

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from difflib import unified_diff

from .client import Response


@dataclass
class ComparisonResult:
    """Result of response comparison."""
    match: bool
    diff: str = ""
    details: Dict[str, Any] = None


def _jsonpath_to_parts(path: str) -> List[str]:
    """Convert simple JSONPath-like string to key parts."""
    # Handle patterns like "data[*].updatedAt" -> ["data", "*", "updatedAt"]
    # Handle patterns like "root.nested[0].key" -> ["root", "nested", "0", "key"]
    parts: List[str] = []
    current = []
    i = 0
    n = len(path)

    while i < n:
        if path[i] == '.':
            if current:
                parts.append(''.join(current))
                current = []
            i += 1
        elif path[i] == '[':
            if current:
                parts.append(''.join(current))
                current = []
            i += 1
            # Find matching ']'
            while i < n and path[i] != ']':
                current.append(path[i])
                i += 1
            if current:
                parts.append(''.join(current))
                current = []
            i += 1
        else:
            current.append(path[i])
            i += 1
    if current:
        parts.append(''.join(current))
    return parts


def _should_ignore(path: List[str], ignore_patterns: List[str]) -> bool:
    """Check if the given path matches any ignore pattern."""
    path_str = '.'.join(path)
    for pattern in ignore_patterns:
        pattern_parts = _jsonpath_to_parts(pattern)
        if _match_pattern(path, pattern_parts):
            return True
    return False


def _match_pattern(path: List[str], pattern_parts: List[str]) -> bool:
    """Check if path matches pattern parts (supports * wildcard)."""
    if not path and not pattern_parts:
        return True
    if not path or not pattern_parts:
        return False

    p = pattern_parts[0]

    if p == '*':
        # * matches any single segment or remaining segments
        if _match_pattern(path[1:], pattern_parts[1:]):
            return True
        if _match_pattern(path[1:], pattern_parts):
            return True
    elif p == path[0] or (p.isdigit() and path[0] == p):
        if _match_pattern(path[1:], pattern_parts[1:]):
            return True

    return False


def _remove_ignored_fields(data: Any, ignore_patterns: List[str], current_path: List[str] = None) -> Any:
    """Recursively remove ignored fields from data."""
    if current_path is None:
        current_path = []

    if _should_ignore(current_path, ignore_patterns):
        return None  # Mark for removal

    if isinstance(data, dict):
        result: Dict[str, Any] = {}
        for key, value in data.items():
            new_path = current_path + [key]
            cleaned = _remove_ignored_fields(value, ignore_patterns, new_path)
            if not _should_ignore(new_path, ignore_patterns):
                result[key] = cleaned
        return result
    elif isinstance(data, list):
        return [
            _remove_ignored_fields(item, ignore_patterns, current_path + [str(i)])
            for i, item in enumerate(data)
        ]
    else:
        return data


def _normalize_json(data: Any) -> str:
    """Normalize JSON data for comparison (sorted keys)."""
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)


def _generate_diff(before: Any, after: Any) -> str:
    """Generate unified diff between two data structures."""
    before_str = _normalize_json(before)
    after_str = _normalize_json(after)

    diff = unified_diff(
        before_str.splitlines(),
        after_str.splitlines(),
        fromfile='before',
        tofile='after',
        lineterm='',
    )
    return '\n'.join(diff)


def compare_responses(
    before_resp: Response,
    after_resp: Response,
    ignore_fields: List[str] = None,
) -> ComparisonResult:
    """
    Compare two API responses.

    Args:
        before_resp: Response from old API.
        after_resp: Response from new API.
        ignore_fields: List of field patterns to ignore.

    Returns:
        ComparisonResult with match status and diff.
    """
    if ignore_fields is None:
        ignore_fields = []

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

    # 2. Clean ignored fields
    before_clean = _remove_ignored_fields(before_resp.body, ignore_fields)
    after_clean = _remove_ignored_fields(after_resp.body, ignore_fields)

    # 3. Compare bodies
    if before_clean != after_clean:
        return ComparisonResult(
            match=False,
            diff=_generate_diff(before_clean, after_clean),
            details=details,
        )

    return ComparisonResult(match=True, details=details)
