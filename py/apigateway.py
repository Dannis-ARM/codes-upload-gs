import urllib.request
import urllib.error
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def call_private_api_gateway(
    vpce_dns_name: str,
    api_dns_name: str,
    stage: str = "prod",
    path: str = "/test",
    method: str = "GET",
    body: bytes = None,
) -> str:
    full_url = f"https://{vpce_dns_name}/{stage}{path}"
    logging.info(f"Request URL: {full_url}")
    logging.info(f"Host Header: {api_dns_name}")

    headers = {"Host": api_dns_name, "Content-Type": "application/json"}

    try:
        req = urllib.request.Request(
            full_url, data=body, headers=headers, method=method.upper()
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            logging.info(f"Status Code: {status_code}")
            decoded_response = response.read().decode("utf-8").strip()
            logging.info(f"Response: {decoded_response}")
            return decoded_response

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        logging.error(f"HTTP Error: {e.code} | {e.reason} | Body: {error_body}")
        return f"ERROR_{e.code}: {error_body}"

    except urllib.error.URLError as e:
        logging.error(f"Connection Failed: {e}")
        return f"CONNECTION_ERROR: {str(e)}"

    except Exception as e:
        logging.error(f"Unexpected Error: {str(e)}")
        return f"UNKNOWN_ERROR: {str(e)}"


# Example Usage
if __name__ == "__main__":
    VPCE_DNS = "vpce-xxx.execute-api.region.vpce.amazonaws.com"
    API_DNS = "api-id.execute-api.region.amazonaws.com"
    response = call_private_api_gateway(VPCE_DNS, API_DNS, stage="prod", path="/test")
    print("Decoded Response:", response)
