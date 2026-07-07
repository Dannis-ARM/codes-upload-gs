"""Main test file for migration API consistency check."""

import os
import sys
import json
from pathlib import Path
from dataclasses import asdict

import pytest

from migration_checker.config import load_config, Config
from migration_checker.client import fetch_response
from migration_checker.comparator import compare_responses
from migration_checker.reporter import get_reporter, TestResult


@pytest.fixture(scope="session")
def config(pytestconfig):
    """Load configuration once per test session."""
    config_path = pytestconfig.getoption("--config")
    return load_config(config_path)


@pytest.fixture(scope="session")
def reporter():
    """Get the reporter instance."""
    return get_reporter()


@pytest.fixture(scope="session", autouse=True)
def report_summary(request, reporter):
    """Print and save report at the end of session (single-threaded only)."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    yield
    if not worker_id or worker_id == "master":
        reporter.print_summary()
        report_path = reporter.save_report()
        print(f"\nFull report saved to: {report_path}")


def pytest_generate_tests(metafunc):
    """Dynamically generate test cases from config."""
    if "api_case" in metafunc.fixturenames:
        config_path = metafunc.config.getoption("--config")
        config = load_config(config_path)
        metafunc.parametrize(
            "api_case",
            config.apis,
            ids=[api.name for api in config.apis],
        )


def test_api_consistency(api_case, config, reporter):
    """
    Test that before and after API responses match.

    Args:
        api_case: The API test case.
        config: Full configuration.
        reporter: Reporter instance.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    before_resp = None
    after_resp = None
    error_msg = ""

    try:
        # Fetch before response
        before_resp = fetch_response(api_case, "before", config.global_config)

        # Fetch after response
        after_resp = fetch_response(api_case, "after", config.global_config)

        # Compare responses
        comparison = compare_responses(
            before_resp,
            after_resp,
            api_case.ignore_fields,
        )

        # Create test result object
        def to_json_str(data: Any) -> str:
            if data is None:
                return "null"
            if isinstance(data, str):
                return data
            return json.dumps(data, ensure_ascii=False)

        result = TestResult(
            name=api_case.name,
            success=comparison.match,
            before_url=before_resp.url,
            after_url=after_resp.url,
            before_status=before_resp.status_code,
            after_status=after_resp.status_code,
            before_elapsed=before_resp.elapsed_seconds,
            after_elapsed=after_resp.elapsed_seconds,
            before_body=to_json_str(before_resp.body),
            after_body=to_json_str(after_resp.body),
            diff=comparison.diff if not comparison.match else "",
            error="",
        )

        # Record - worker mode saves single file, normal mode accumulates
        if worker_id and worker_id != "master":
            reporter.save_worker_result(worker_id, result)
        else:
            reporter.record_test(
                name=api_case.name,
                before_resp=before_resp,
                after_resp=after_resp,
                comparison=comparison,
            )

        # Assert
        assert comparison.match, f"Response mismatch:\n{comparison.diff}"

    except Exception as e:
        # Skip AssertionError - we already recorded that in try block
        if isinstance(e, AssertionError):
            raise

        error_msg = str(e)

        # Create dummy responses if needed
        if before_resp is None or after_resp is None:
            from migration_checker.client import Response as ClientResponse
            dummy = ClientResponse(
                url=api_case.before,
                status_code=0,
                headers={},
                body=None,
                raw_body="",
                elapsed_seconds=0,
            )
            before_resp = before_resp or dummy
            after_resp = after_resp or dummy

        from migration_checker.comparator import ComparisonResult

        def to_json_str(data: Any) -> str:
            if data is None:
                return "null"
            if isinstance(data, str):
                return data
            return json.dumps(data, ensure_ascii=False)

        result = TestResult(
            name=api_case.name,
            success=False,
            before_url=before_resp.url,
            after_url=after_resp.url,
            before_status=before_resp.status_code,
            after_status=after_resp.status_code,
            before_elapsed=before_resp.elapsed_seconds,
            after_elapsed=after_resp.elapsed_seconds,
            before_body=to_json_str(before_resp.body),
            after_body=to_json_str(after_resp.body),
            diff="",
            error=error_msg,
        )

        # Record error
        if worker_id and worker_id != "master":
            reporter.save_worker_result(worker_id, result)
        else:
            reporter.record_test(
                name=api_case.name,
                before_resp=before_resp,
                after_resp=after_resp,
                comparison=ComparisonResult(match=False, diff="", details={}),
                error=error_msg,
            )

        pytest.fail(f"Test failed with error: {error_msg}")
