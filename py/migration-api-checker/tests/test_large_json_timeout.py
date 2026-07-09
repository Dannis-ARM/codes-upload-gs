"""Test for large JSON response timeout issue - verifies httpx.Timeout is used correctly."""

import json
import time
import threading
from unittest.mock import patch, MagicMock
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest
import httpx

from migration_checker.config import ApiCase, GlobalConfig
from migration_checker.client import fetch_response


def test_client_uses_httpx_timeout_with_longer_read():
    """
    Verify fetch_response creates httpx.Timeout with longer read timeout for large JSON.
    """
    api_case = ApiCase(
        name="Test",
        method="GET",
        before="http://example.com/test",
        after="http://example.com/test",
    )

    global_config = GlobalConfig(timeout=60)

    # Mock httpx.Client to capture the timeout it's called with
    captured_timeout = None

    def mock_client_init(*args, **kwargs):
        nonlocal captured_timeout
        captured_timeout = kwargs.get("timeout")
        # Return a mock client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"ok": true}'
        mock_response.json.return_value = {"ok": True}
        mock_client.request.return_value = mock_response
        return mock_client

    with patch("httpx.Client", side_effect=mock_client_init) as mock_client_cls:
        # Also patch the context manager __enter__/__exit__
        mock_client_instance = mock_client_cls.return_value
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.__exit__.return_value = None

        # Call fetch_response
        result = fetch_response(api_case, "before", global_config)

        # Verify httpx.Client was called
        mock_client_cls.assert_called_once()

        # Verify timeout is an httpx.Timeout object (not just an int)
        call_kwargs = mock_client_cls.call_args.kwargs
        timeout_arg = call_kwargs.get("timeout")

        assert isinstance(timeout_arg, httpx.Timeout), (
            f"Expected httpx.Timeout, got {type(timeout_arg)}. "
            "This is needed for large JSON responses to avoid 'read operation timed out'."
        )

        # Verify read timeout is longer than the configured timeout
        assert timeout_arg.read >= global_config.timeout, (
            f"Read timeout ({timeout_arg.read}s) should be >= configured timeout ({global_config.timeout}s) "
            "to handle large JSON responses."
        )

        # Verify connect timeout is reasonable
        assert timeout_arg.connect <= 10, (
            f"Connect timeout ({timeout_arg.connect}s) shouldn't be too long."
        )


def test_backward_compatibility_still_works():
    """Verify the fix doesn't break normal usage."""
    # Just test that fetch_response can still be called without errors
    # (we'll mock the actual HTTP call)
    api_case = ApiCase(
        name="Test",
        method="GET",
        before="http://example.com/test",
        after="http://example.com/test",
    )

    global_config = GlobalConfig(timeout=30)

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"ok": true}'
        mock_response.json.return_value = {"ok": True}
        mock_client.request.return_value = mock_response

        # This should not raise
        result = fetch_response(api_case, "before", global_config)

        assert result.status_code == 200
