"""Shared types for migration-api-checker."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Response:
    """HTTP response container."""
    url: str
    status_code: int
    headers: Dict[str, str]
    body: Any  # Parsed JSON or text
    raw_body: str
    elapsed_seconds: float


@dataclass
class CompareOptions:
    """Options for response comparison using DeepDiff."""
    exclude_paths: List[str] = field(default_factory=list)
    exclude_regex_paths: List[str] = field(default_factory=list)
    ignore_order: bool = False
    ignore_numeric_type_changes: bool = True


@dataclass
class ApiTestResult:
    """Result of a single API test case execution."""
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
