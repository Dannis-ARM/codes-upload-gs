"""Main test file for migration API consistency check."""

import os
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from migration_checker.config import load_config, Config
from migration_checker.client import fetch_response
from migration_checker.comparator import compare_responses
from migration_checker.reporter import get_reporter


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--config",
        action="store",
        default="cfgs.yaml",
        help="Path to configuration file",
    )


@pytest.fixture(scope="session")
def config(pytestconfig) -> Config:
    """Load configuration once per test session."""
    config_path = pytestconfig.getoption("--config")
    return load_config(config_path)


@pytest.fixture(scope="session")
def reporter():
    """Get the reporter instance."""
    return get_reporter()


@pytest.fixture(scope="session", autouse=True)
def report_summary(request, reporter):
    """Print and save report at the end of session."""
    yield
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
    error_msg = ""
    before_resp = None
    after_resp = None

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

        # Record result
        reporter.record_test(
            name=api_case.name,
            before_resp=before_resp,
            after_resp=after_resp,
            comparison=comparison,
        )

        # Assert
        assert comparison.match, f"Response mismatch:\n{comparison.diff}"

    except Exception as e:
        error_msg = str(e)
        # Record error with dummy responses if needed
        if before_resp is None or after_resp is None:
            # Create dummy responses for error reporting
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
        reporter.record_test(
            name=api_case.name,
            before_resp=before_resp,
            after_resp=after_resp,
            comparison=ComparisonResult(match=False, diff="", details={}),
            error=error_msg,
        )
        pytest.fail(f"Test failed with error: {error_msg}")
