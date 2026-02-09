"""
Main handler for the AWS Lambda function.

This function acts as a secure proxy, routing requests to worker Lambdas
after they have been authorized by a Lambda Authorizer.
"""
import json
import logging
import os
from typing import Any, Callable, Dict

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize boto3 Lambda client globally for efficiency
lambda_client = boto3.client("lambda")

# Retrieve worker Lambda ARNs from environment variables
UPDATE_WORKER_LAMBDA_ARN = os.environ.get("UPDATE_WORKER_LAMBDA_NAME")
FETCH_WORKER_LAMBDA_ARN = os.environ.get("FETCH_WORKER_LAMBDA_NAME")

# Defines the permission level required for each action.
ACTION_REQUIREMENTS: Dict[str, str] = {
    "update_record": "read-write",
    "fetch_record": "read-only",
}

def _invoke_worker(function_arn: str, event_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to invoke a worker Lambda and process its response."""
    if not function_arn:
        raise ValueError(f"Worker Lambda ARN is not configured for event payload: {event_payload}")

    logger.info("Invoking worker Lambda: %s with payload: %s", function_arn, event_payload)
    
    try:
        invoke_response = lambda_client.invoke(
            FunctionName=function_arn,
            InvocationType="RequestResponse",
            Payload=json.dumps(event_payload),
        )

        response_payload_bytes = invoke_response["Payload"].read()
        worker_response_body = json.loads(response_payload_bytes.decode("utf-8"))
        
        if worker_response_body.get("statusCode") != 200:
            error_message = worker_response_body.get("body", "Worker lambda returned an error.")
            logger.error("Worker Lambda %s failed with status %s: %s",
                         function_arn, worker_response_body.get("statusCode"), error_message)
            raise RuntimeError(f"Worker lambda invocation failed: {error_message}")

        return json.loads(worker_response_body.get("body", "{}"))

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON response from worker Lambda %s: %s", function_arn, response_payload_bytes)
        raise RuntimeError(f"Invalid JSON response from worker Lambda: {response_payload_bytes}")
    except Exception as e:
        logger.error("Error invoking worker Lambda %s: %s", function_arn, e)
        raise RuntimeError(f"An unexpected error occurred during worker invocation: {e}")


def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    """
    Handles incoming requests, performs action-level authorization, and routes to business logic.
    """
    logger.info("Event received: %s", json.dumps(event))

    # Action dispatch table
    ACTION_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
        "update_record": _handle_update_record,
        "fetch_record": _handle_fetch_record,
    }

    try:
        if not all([UPDATE_WORKER_LAMBDA_ARN, FETCH_WORKER_LAMBDA_ARN]):
            logger.error("Worker Lambda ARNs not configured.")
            return {"statusCode": 500, "message": "Internal Server Error: Worker configuration missing."}

        # 1. Extract context from authorizer
        authorizer_context = event.get("requestContext", {}).get("authorizer", {})
        caller_permission = authorizer_context.get("permission")
        caller_role_name = authorizer_context.get("callerRoleName", "UnknownRole")

        if not caller_permission:
            logger.error("Critical: Permission not found in authorizer context. Misconfiguration? %s", authorizer_context)
            return {"statusCode": 500, "message": "Internal Server Error: Authorizer context missing."}

        # 2. Extract and validate action from body
        body = json.loads(event.get("body") or "{}")
        requested_action = body.get("action")
        
        if requested_action not in ACTION_REQUIREMENTS:
             return {
                 "statusCode": 400,
                 "message": f"Bad Request: Invalid or missing 'action'. Must be one of {list(ACTION_REQUIREMENTS.keys())}."
             }

        # 3. Perform Action-level Authorization (concise)
        required_permission = ACTION_REQUIREMENTS[requested_action]
        is_authorized = (caller_permission == "read-write") or \
                        (caller_permission == "read-only" and required_permission == "read-only")

        if not is_authorized:
            logger.warning("Forbidden: Role '%s' (permission: %s) cannot perform action '%s' (requires: %s).",
                           caller_role_name, caller_permission, requested_action, required_permission)
            return {"statusCode": 403, "message": "Forbidden"}

        logger.info("Authorized: Role '%s' permitted to perform action '%s'.", caller_role_name, requested_action)

        # 4. Route to Business Logic using dispatch table
        handler = ACTION_HANDLERS[requested_action]
        return handler(body)

    except json.JSONDecodeError:
        return {"statusCode": 400, "message": "Bad Request: Invalid JSON in body."}
    except RuntimeError as e:  # From _invoke_worker
        logger.error("Worker Lambda invocation error: %s", e)
        return {"statusCode": 502, "message": str(e)}
    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return {"statusCode": 500, "message": "Internal Server Error"}

# --- Business Logic Handlers ---

def _handle_update_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invokes the update worker Lambda."""
    logger.info("Preparing to invoke update worker Lambda.")
    worker_event = {
        "operation_type": "update_action",
        "details": payload.get("data", {}),
        "source_proxy": "ActionHandlerLambda"
    }
    assert UPDATE_WORKER_LAMBDA_ARN
    worker_response = _invoke_worker(UPDATE_WORKER_LAMBDA_ARN, worker_event)
    return {
        "statusCode": 200,
        "message": "Update request processed successfully.",
        "payload": worker_response
    }

def _handle_fetch_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invokes the fetch worker Lambda."""
    logger.info("Preparing to invoke fetch worker Lambda.")
    worker_event = {
        "operation_type": "fetch_action",
        "record_identifier": payload.get("record_id"),
        "query_params": payload.get("query_params", {}),
        "source_proxy": "ActionHandlerLambda"
    }
    assert FETCH_WORKER_LAMBDA_ARN
    worker_response = _invoke_worker(FETCH_WORKER_LAMBDA_ARN, worker_event)
    return {
        "statusCode": 200,
        "message": "Fetch request processed successfully.",
        "payload": worker_response
    }
