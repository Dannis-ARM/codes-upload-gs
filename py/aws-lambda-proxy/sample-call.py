"""
This script provides examples of how to call the secure API Gateway endpoint,
which is protected by a custom Lambda Authorizer.

The authorization is based on an IAM role that the caller assumes. The name of this
role must be passed in the 'x-caller-role-name' HTTP header.
"""
import json
import os
import requests
import boto3

# --- Configuration ---
# TODO: Update these variables before running the script.
# You can get the API endpoint URL from the CloudFormation stack outputs.
API_ENDPOINT_URL = os.environ.get("API_ENDPOINT_URL", "https://your-api-id.execute-api.your-region.amazonaws.com/prod/registry-cli")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# The AWS Account ID where the roles are defined.
ACCOUNT_ID = os.environ.get("ACCOUNT_ID", "123456789012")


def get_role_arn(role_name: str) -> str:
    """Constructs the full ARN for a given IAM role name."""
    return f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"


def call_api_with_role(role_name: str, action: str, data: dict):
    """
    Assumes an IAM role and makes a call to the API Gateway endpoint.

    Args:
        role_name: The name of the IAM role to assume (e.g., 'ReadOnlyRole').
        action: The action to perform (e.g., 'fetch_record').
        data: The data payload for the action.
    """
    print(f"\n--- Calling API with Role: {role_name}, Action: {action} ---")

    if "your-api-id" in API_ENDPOINT_URL or "123456789012" in ACCOUNT_ID:
        print("!!! WARNING: Please update API_ENDPOINT_URL and ACCOUNT_ID in the script before running. !!!")
        return

    try:
        # Step 1: Assume the role.
        # The entity running this script must have STS 'AssumeRole' permissions for the target role.
        sts_client = boto3.client("sts")
        role_arn = get_role_arn(role_name)
        
        print(f"Verifying identity by assuming role: {role_arn}...")
        sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"{role_name}ApiCallSession"
        )
        # We don't need the temporary credentials for the call itself, but this step
        # simulates the client authenticating and adopting the role identity.
        print("Role assumption successful.")

        # Step 2: Construct the request payload and headers.
        request_body = {
            "action": action,
            **data  # Merge action-specific data
        }
        
        headers = {
            "Content-Type": "application/json",
            # This is the crucial header for our custom Lambda Authorizer.
            "x-caller-role-name": role_name
        }

        print(f"Making POST request to {API_ENDPOINT_URL}")
        print(f"Headers: {json.dumps(headers, indent=2)}")
        print(f"Body: {json.dumps(request_body, indent=2)}")

        # Step 3: Make the API call.
        # IMPORTANT: This script must be run from a location that has network access
        # to the private API Gateway endpoint (e.g., from within the same VPC).
        response = requests.post(API_ENDPOINT_URL, headers=headers, data=json.dumps(request_body))
        
        print("\n--- Response ---")
        print(f"Status Code: {response.status_code}")
        try:
            # Try to pretty-print if response is JSON
            print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        except json.JSONDecodeError:
            print(f"Response Body: {response.text}")
        print("--------------------")

    except Exception as e:
        print(f"\n--- An error occurred ---")
        print(e)
        print("--------------------")


def main():
    """
    Demonstrates calling the API with different roles and actions.
    """
    print("=======================================================")
    print("=          API Gateway Lambda Authorizer Demo         =")
    print("=======================================================")
    print("This script demonstrates how to call the private API by assuming")
    print("an IAM role and passing the role name in a header.")
    print("\nIMPORTANT: This script must be run from within the VPC where the")
    print("           API Gateway VPC Endpoint is located.")
    
    # --- Scenario 1: ReadOnlyRole attempts to fetch a record (should SUCCEED) ---
    fetch_payload = {"record_id": "123-abc"}
    call_api_with_role(role_name="ReadOnlyRole", action="fetch_record", data=fetch_payload)

    # --- Scenario 2: ReadOnlyRole attempts to update a record (should be FORBIDDEN) ---
    update_payload = {"data": {"record_id": "123-abc", "new_value": "hello"}}
    call_api_with_role(role_name="ReadOnlyRole", action="update_record", data=update_payload)
    
    # --- Scenario 3: ReadWriteRole attempts to fetch a record (should SUCCEED) ---
    call_api_with_role(role_name="ReadWriteRole", action="fetch_record", data=fetch_payload)
    
    # --- Scenario 4: ReadWriteRole attempts to update a record (should SUCCEED) ---
    call_api_with_role(role_name="ReadWriteRole", action="update_record", data=update_payload)


if __name__ == "__main__":
    main()