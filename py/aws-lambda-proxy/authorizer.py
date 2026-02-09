"""
Lambda Authorizer for the secure proxy.
"""
import json
import logging
from typing import Any, Dict

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Authorization Mapping ---
# Defines the permission level for each role. (Copied from main.py)
ROLE_PERMISSIONS: Dict[str, str] = {
    "ReadWriteRole": "read-write",
    "ReadOnlyRole": "read-only",
}

def generate_policy(principal_id: str, effect: str, resource: str) -> Dict[str, Any]:
    """Helper function to generate an IAM policy for the authorizer response."""
    return {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource,
            }]
        }
    }

def authorizer_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    """
    Handles API Gateway Lambda Authorizer requests.

    This function authorizes requests based on a role name passed in a header.
    """
    logger.info("Authorizer event received: %s", json.dumps(event))

    # The role name is expected in a custom header 'x-caller-role-name'.
    # This is configured in the API Gateway Authorizer's IdentitySource.
    caller_role_name = event.get("headers", {}).get("x-caller-role-name")
    method_arn = event.get("methodArn")

    if not caller_role_name:
        logger.warning("Authorization failed: Missing 'x-caller-role-name' header.")
        # Explicitly deny access if the header is missing.
        return generate_policy('user', 'Deny', method_arn)

    # Determine the permission level for the given role
    permission = ROLE_PERMISSIONS.get(caller_role_name)

    if not permission:
        logger.warning("Authorization failed: Role '%s' not found in ROLE_PERMISSIONS.", caller_role_name)
        return generate_policy(caller_role_name, 'Deny', method_arn)

    # Generate an 'Allow' policy and pass the permission level in the context.
    # This context is then available in the integration Lambda's event.
    policy = generate_policy(caller_role_name, 'Allow', method_arn)
    policy['context'] = {
        'permission': permission,
        'callerRoleName': caller_role_name,  # Pass for logging/auditing
    }

    logger.info("Authorization successful for role '%s' with permission '%s'.", caller_role_name, permission)
    return policy
