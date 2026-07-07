"""HTTP client for fetching API responses."""

import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import httpx

from .config import ApiCase, GlobalConfig
from .types import Response


def _merge_headers(global_headers: Dict[str, str], api_headers: Dict[str, str]) -> Dict[str, str]:
    """Merge global and API-specific headers."""
    merged = global_headers.copy()
    merged.update(api_headers)
    return merged


def _parse_response_body(response: httpx.Response) -> Tuple[Any, str]:
    """Parse response body as JSON if possible, otherwise return text."""
    raw_body = response.text
    try:
        if raw_body.strip():
            return response.json(), raw_body
        return None, raw_body
    except Exception:
        return raw_body, raw_body


def _fetch_with_retry(
    client: httpx.Client,
    method: str,
    original_url: str,
    final_url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
    retries: int,
) -> Response:
    """Fetch with retry logic."""
    last_exception: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            start_time = time.time()

            kwargs: Dict[str, Any] = {
                "headers": headers,
            }
            if body is not None:
                kwargs["json"] = body

            response = client.request(method, final_url, **kwargs)

            elapsed = time.time() - start_time
            parsed_body, raw_body = _parse_response_body(response)

            return Response(
                url=original_url,  # Use the original URL from config, not httpx's constructed one
                status_code=response.status_code,
                headers=dict(response.headers),
                body=parsed_body,
                raw_body=raw_body,
                elapsed_seconds=elapsed,
            )
        except Exception as e:
            last_exception = e
            if attempt < retries:
                time.sleep(1 * (attempt + 1))  # Exponential backoff

    if last_exception:
        raise last_exception
    raise RuntimeError("Failed to fetch response")


def fetch_response(
    api_case: ApiCase,
    target: str,
    global_config: GlobalConfig,
) -> Response:
    """
    Fetch response from either 'before' or 'after' endpoint.

    Args:
        api_case: The API test case.
        target: Either 'before' or 'after'.
        global_config: Global configuration.

    Returns:
        Response object.
    """
    original_url = api_case.before if target == "before" else api_case.after
    headers = _merge_headers(global_config.common_headers, api_case.headers)

    # Parse URL and extract query params
    parsed = urlparse(original_url)
    url_query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # Merge: config params override URL params
    merged_params = {**url_query_params, **api_case.params}

    # Build final URL with manually constructed query (for special character passthrough)
    if merged_params:
        # Manually construct query string to preserve special characters
        query_parts = []
        for k, v in merged_params.items():
            if v is None:
                query_parts.append(f"{k}")
            else:
                query_parts.append(f"{k}={v}")
        final_query = "&".join(query_parts)
        parsed = parsed._replace(query=final_query)

    final_url = urlunparse(parsed)

    with httpx.Client(timeout=global_config.timeout, follow_redirects=True, verify=False) as client:
        return _fetch_with_retry(
            client=client,
            method=api_case.method,
            original_url=original_url,
            final_url=final_url,
            headers=headers,
            body=api_case.body,
            retries=global_config.retries,
        )
