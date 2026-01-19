"""
Main handler for the AWS Lambda function.

This function acts as a secure proxy, authorizing and routing requests
based on the caller's IAM role.
"""
import json
import logging
import os
from typing import Any, Dict

import boto3

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize boto3 Lambda client globally for efficiency
lambda_client = boto3.client("lambda")

# Retrieve worker Lambda ARNs from environment variables
UPDATE_WORKER_LAMBDA_ARN = os.environ.get("UPDATE_WORKER_LAMBDA_NAME")
FETCH_WORKER_LAMBDA_ARN = os.environ.get("FETCH_WORKER_LAMBDA_NAME")

# --- Authorization Mapping ---
# Defines the permission level for each role.
ROLE_PERMISSIONS: Dict[str, str] = {
    "UpdateRole": "read-write",
    "FetchRole": "read-only",
}

# Defines the permission level required for each action.
ACTION_REQUIREMENTS: Dict[str, str] = {
    "update_record": "read-write",
    "fetch_record": "read-only",
}

def _invoke_worker(function_arn: str, event_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper function to invoke a worker Lambda and process its response.
    """
    if not function_arn:
        raise ValueError(f"Worker Lambda ARN is not configured for event payload: {event_payload}")

    logger.info("Invoking worker Lambda: %s with payload: %s", function_arn, event_payload)
    
    try:
        invoke_response = lambda_client.invoke(
            FunctionName=function_arn,
            InvocationType="RequestResponse",  # Synchronous invocation
            Payload=json.dumps(event_payload),
        )

        response_payload_stream = invoke_response["Payload"]
        response_payload_bytes = response_payload_stream.read()
        
        # Worker Lambda is expected to return a JSON string
        worker_response_body = json.loads(response_payload_bytes.decode("utf-8"))
        
        # Check if the worker Lambda returned an error (e.g., statusCode other than 200)
        if worker_response_body.get("statusCode") != 200:
            error_message = worker_response_body.get("body", "Worker lambda returned an error.")
            logger.error("Worker Lambda %s failed with status code %s: %s",
                         function_arn, worker_response_body.get("statusCode"), error_message)
            raise RuntimeError(f"Worker lambda invocation failed: {error_message}")

        # Assuming worker Lambda's body is also JSON stringified
        worker_result = json.loads(worker_response_body.get("body", "{}"))
        return worker_result

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON response from worker Lambda %s: %s", function_arn, response_payload_bytes)
        raise RuntimeError(f"Invalid JSON response from worker Lambda: {response_payload_bytes}")
    except Exception as e:
        logger.error("Error invoking worker Lambda %s: %s", function_arn, e)
        raise


def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    """
    Handles incoming requests, performs authorization, and routes to business logic.

    Args:
        event: The event dictionary from Lambda Function URL.
        context: The context object (unused).

    Returns:
        A dictionary response compatible with API Gateway / Lambda Function URLs.
    """
    logger.info("Event received: %s", json.dumps(event))

    if not UPDATE_WORKER_LAMBDA_ARN or not FETCH_WORKER_LAMBDA_ARN:
        logger.error("Worker Lambda ARNs not configured. Ensure UPDATE_WORKER_LAMBDA_NAME and FETCH_WORKER_LAMBDA_NAME environment variables are set.")
        return {
            "statusCode": 500,
            "message": "Internal Server Error: Worker Lambda ARNs not configured.",
            "payload": {}
        }

    try:
        # 1. Extract Caller Identity from the request context
        # When invoked via API Gateway with IAM auth, the caller's identity is in this path.
        caller_arn: str = event["requestContext"]["identity"]["userArn"]
        
        # Extract the role name (e.g., "RoleA") from the full ARN
        # Assumes ARN format: arn:aws:sts::123456789012:assumed-role/RoleA/session-name
        caller_role_name = caller_arn.split("/")[-2]

        # 2. Extract Requested Action from the event body
        body = json.loads(event.get("body") or "{}")
        requested_action = body.get("action")
        
        if not requested_action:
            return {
                "statusCode": 400,
                "message": "Bad Request: 'action' is required in the request body.",
                "payload": {}
            }

        # 3. Perform Authorization (The Gatekeeper Logic)
        caller_permission = ROLE_PERMISSIONS.get(caller_role_name)
        required_permission = ACTION_REQUIREMENTS.get(requested_action)

        is_authorized = False
        if caller_permission and required_permission:
            if caller_permission == "read-write":
                is_authorized = True  # Read-write can do anything
            elif caller_permission == "read-only" and required_permission == "read-only":
                is_authorized = True  # Read-only can only do read-only actions

        if not is_authorized:
            logger.warning(
                "Forbidden: Role '%s' (permission: %s) is not allowed to perform action '%s' (requires: %s).",
                caller_role_name,
                caller_permission,
                requested_action,
                required_permission
                )
            return {
                "statusCode": 403,
                "message": "Forbidden",
                "payload": {}
            }

        logger.info(
            "Authorized: Role '%s' permitted to perform action '%s'.",
            caller_role_name,
            requested_action
        )

        # 4. Route to Business Logic
        if requested_action == "update_record":
            result = _handle_update_record(body)
        elif requested_action == "fetch_record":
            result = _handle_fetch_record(body)
        else:
            raise ValueError(f"Unknown action: {requested_action}")

        return result

    except (KeyError, TypeError) as e:
        logger.error("Error processing request context. Is the authenticator configured correctly? %s", e)
        return {
            "statusCode": 400,
            "message": "Bad Request: Invalid request structure.",
            "payload": {}
        }
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "message": "Bad Request: Invalid JSON in body.",
            "payload": {}
        }
    except RuntimeError as e:
        logger.error("Worker Lambda invocation error: %s", e)
        return {
            "statusCode": 502, # Bad Gateway for issues with upstream service
            "message": str(e),
            "payload": {}
        }
    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return {
            "statusCode": 500,
            "message": "Internal Server Error",
            "payload": {}
        }

# --- Business Logic Handlers ---

def _handle_update_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invokes the update worker Lambda with a specific event payload.
    """
    logger.info("Preparing to invoke update worker Lambda.")
    # Construct a "different event" for the update worker
    worker_event = {
        "operation_type": "update_action",
        "details": payload.get("data", {}), # Pass relevant data from the incoming payload
        "source_proxy": "ActionHandlerLambda"
    }
    
    # Invoke the worker Lambda
    assert UPDATE_WORKER_LAMBDA_ARN
    worker_response = _invoke_worker(UPDATE_WORKER_LAMBDA_ARN, worker_event)
    return {
        "statusCode": 200,
        "message": "Update request processed successfully.",
        "payload": worker_response
    }


def _handle_fetch_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invokes the fetch worker Lambda with a specific event payload.
    """
    logger.info("Preparing to invoke fetch worker Lambda.")
    # Construct a "different event" for the fetch worker
    worker_event = {
        "operation_type": "fetch_action",
        "record_identifier": payload.get("record_id"), # Pass relevant data from the incoming payload
        "query_params": payload.get("query_params", {}),
        "source_proxy": "ActionHandlerLambda"
    }

    # Invoke the worker Lambda
    assert FETCH_WORKER_LAMBDA_ARN
    worker_response = _invoke_worker(FETCH_WORKER_LAMBDA_ARN, worker_event)
    return {
        "statusCode": 200,
        "message": "Fetch request processed successfully.",
        "payload": worker_response
    }
