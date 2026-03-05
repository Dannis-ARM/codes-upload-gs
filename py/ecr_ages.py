import boto3
import json
import datetime
from typing import Dict, Any, Set, Tuple, List, Optional
from botocore.exceptions import ClientError
import logging

# Use Any for boto3 clients (most practical approach)
from typing import Any as Boto3Client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_IMAGE_AGE_DAYS = 90


# ────────────────────────────────────────────────
# Environment & Client Initialization
# ────────────────────────────────────────────────

def get_lambda_env_info(context: Any) -> Dict[str, str]:
    """Extract AWS region and account ID from Lambda context."""
    try:
        arn_parts = context.invoked_function_arn.split(':')
        return {
            "region": arn_parts[3],
            "account_id": arn_parts[4],
        }
    except (IndexError, AttributeError) as exc:
        logger.error("Failed to parse Lambda context ARN", exc_info=True)
        raise ValueError("Invalid Lambda context ARN") from exc


def initialize_clients(region: str) -> Dict[str, Boto3Client]:
    """Create boto3 clients for ECS, ECR, and Config."""
    return {
        "ecs": boto3.client("ecs", region_name=region),
        "ecr": boto3.client("ecr", region_name=region),
        "config": boto3.client("config", region_name=region),
    }


# ────────────────────────────────────────────────
# Event & Resource Parsing
# ────────────────────────────────────────────────

def parse_invoking_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse the invoking_event JSON string from AWS Config event."""
    try:
        return json.loads(event["invoking_event"])
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("Failed to parse invoking_event", exc_info=True)
        raise ValueError("Invalid or missing invoking_event") from exc


def extract_evaluated_resource(invoking_event: Dict[str, Any]) -> Dict[str, str]:
    """Extract resource type, ID and ARN from configurationItem."""
    item = invoking_event.get("configurationItem", {})
    return {
        "type": item.get("resourceType", ""),
        "id": item.get("resourceId", ""),
        "arn": item.get("ARN", ""),
    }


def is_supported_resource_type(resource_type: str) -> bool:
    """Check if the resource type is supported by this rule."""
    return resource_type == "AWS::ECS::Service"


# ────────────────────────────────────────────────
# ECS Service → Task Definition → Images
# ────────────────────────────────────────────────

def parse_cluster_and_service_from_arn(service_arn: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse cluster name and service name from ECS service ARN."""
    if not service_arn or ":" not in service_arn:
        return None, None

    parts = service_arn.split("/")
    if len(parts) < 3:
        return None, None

    return parts[-2], parts[-1]


def get_primary_task_definition_arn(
    ecs_client: Boto3Client,
    cluster_arn: str,
    service_name: str,
) -> Optional[str]:
    """Retrieve task definition ARN from the primary deployment."""
    try:
        response = ecs_client.describe_services(cluster=cluster_arn, services=[service_name])
        services = response.get("services", [])
        if not services:
            logger.info(f"No active service found: {service_name}")
            return None

        service = services[0]
        if service["status"] != "ACTIVE":
            return None

        for deployment in service.get("deployments", []):
            if deployment["status"] == "PRIMARY":
                return deployment["taskDefinition"]
        return None

    except ClientError as exc:
        logger.error(f"Failed to describe service {service_name}", exc_info=True)
        raise


def extract_ecr_image_uris_from_task_definition(
    ecs_client: Boto3Client,
    task_def_arn: str,
) -> Set[str]:
    """Extract all ECR image URIs from a task definition."""
    try:
        response = ecs_client.describe_task_definition(taskDefinition=task_def_arn)
        container_defs = response["taskDefinition"].get("containerDefinitions", [])

        ecr_images: Set[str] = set()
        for container in container_defs:
            image = container.get("image", "")
            if ".dkr.ecr." in image and ".amazonaws.com" in image:
                ecr_images.add(image)
        return ecr_images

    except ClientError as exc:
        logger.error(f"Failed to describe task definition {task_def_arn}", exc_info=True)
        raise


def build_cluster_arn(region: str, account_id: str, cluster_name: str) -> str:
    """Construct full cluster ARN from name, region and account."""
    return f"arn:aws:ecs:{region}:{account_id}:cluster/{cluster_name}"


def fetch_currently_used_ecr_images(
    ecs_client: Boto3Client,
    service_arn_or_name: str,
    region: str,
    account_id: str,
) -> Set[str]:
    """Fetch ECR image URIs used by the primary deployment of an ECS service."""
    cluster_name, service_name = parse_cluster_and_service_from_arn(service_arn_or_name)
    if not cluster_name or not service_name:
        logger.warning(f"Cannot parse service identifier: {service_arn_or_name}")
        return set()

    cluster_arn = build_cluster_arn(region, account_id, cluster_name)

    task_def_arn = get_primary_task_definition_arn(ecs_client, cluster_arn, service_name)
    if not task_def_arn:
        return set()

    return extract_ecr_image_uris_from_task_definition(ecs_client, task_def_arn)


# ────────────────────────────────────────────────
# ECR Image Age Check
# ────────────────────────────────────────────────

def parse_repo_and_tag_from_image_uri(image_uri: str) -> Tuple[Optional[str], str]:
    """Parse repository name and tag from ECR image URI."""
    try:
        repo_part = image_uri.split("/", 1)[1]
        if ":" in repo_part:
            repo_name, tag = repo_part.rsplit(":", 1)
        else:
            repo_name = repo_part
            tag = "latest"
        return repo_name, tag
    except Exception:
        return None, "unknown"


def is_ecr_image_older_than_threshold(
    ecr_client: Boto3Client,
    image_uri: str,
    max_days: int = MAX_IMAGE_AGE_DAYS,
) -> Tuple[bool, str]:
    """Check if ECR image push date exceeds the allowed threshold."""
    repo_name, tag = parse_repo_and_tag_from_image_uri(image_uri)
    if not repo_name:
        return True, f"Cannot parse ECR image URI: {image_uri}"

    now = datetime.datetime.now(datetime.timezone.utc)

    try:
        paginator = ecr_client.get_paginator("describe_images")
        for page in paginator.paginate(repositoryName=repo_name):
            for detail in page.get("imageDetails", []):
                for img_tag in detail.get("imageTags", []):
                    if img_tag == tag:
                        age_days = (now - detail["imagePushedAt"]).days
                        if age_days > max_days:
                            return True, f"{image_uri} is {age_days} days old (> {max_days})"
                        return False, f"{image_uri} is {age_days} days old"
        return True, f"Tag '{tag}' not found in repository: {repo_name}"

    except ClientError as exc:
        logger.error(f"Failed to describe images in {repo_name}", exc_info=True)
        return True, f"Failed to check image {image_uri}: {exc.response['Error']['Message']}"


def evaluate_all_used_images(
    ecr_client: Boto3Client,
    image_uris: Set[str],
) -> Tuple[str, str]:
    """Evaluate compliance of all used ECR images."""
    violations: List[str] = []

    for uri in image_uris:
        is_violation, message = is_ecr_image_older_than_threshold(ecr_client, uri)
        if is_violation:
            violations.append(message)

    if violations:
        return "NON_COMPLIANT", "; ".join(violations)[:500]

    count = len(image_uris)
    msg = (
        f"All {count} ECR images are within {MAX_IMAGE_AGE_DAYS} days"
        if count > 0
        else "No ECR images in use"
    )
    return "COMPLIANT", msg


# ────────────────────────────────────────────────
# Submit Evaluation
# ────────────────────────────────────────────────

def submit_config_evaluation(
    config_client: Boto3Client,
    resource_type: str,
    resource_id: str,
    compliance_type: str,
    annotation: str,
    ordering_timestamp: str,
    result_token: str,
) -> None:
    """Submit evaluation result to AWS Config."""
    try:
        config_client.put_evaluations(
            Evaluations=[
                {
                    "ComplianceResourceType": resource_type,
                    "ComplianceResourceId": resource_id,
                    "ComplianceType": compliance_type,
                    "Annotation": annotation[:400],
                    "OrderingTimestamp": ordering_timestamp,
                }
            ],
            ResultToken=result_token,
        )
        logger.info(f"Evaluation submitted: {resource_id} → {compliance_type}")
    except ClientError as exc:
        logger.error(f"Failed to submit evaluation for {resource_id}", exc_info=True)


# ────────────────────────────────────────────────
# Lambda Handler
# ────────────────────────────────────────────────

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for Config custom rule."""
    env_info = get_lambda_env_info(context)
    region = env_info["region"]
    account_id = env_info["account_id"]

    clients = initialize_clients(region)

    invoking_event = parse_invoking_event(event)
    resource = extract_evaluated_resource(invoking_event)

    if not is_supported_resource_type(resource["type"]):
        annotation = f"This rule only supports AWS::ECS::Service (got {resource['type']})"
        submit_config_evaluation(
            clients["config"],
            resource["type"],
            resource["id"],
            "NOT_APPLICABLE",
            annotation,
            invoking_event["notificationCreationTime"],
            event["resultToken"],
        )
        return {"statusCode": 200}

    # Core logic - pass region & account_id explicitly
    used_ecr_images = fetch_currently_used_ecr_images(
        ecs_client=clients["ecs"],
        service_arn_or_name=resource["arn"] or resource["id"],
        region=region,
        account_id=account_id,
    )

    compliance, annotation = evaluate_all_used_images(clients["ecr"], used_ecr_images)

    submit_config_evaluation(
        clients["config"],
        resource["type"],
        resource["id"],
        compliance,
        annotation,
        invoking_event["notificationCreationTime"],
        event["resultToken"],
    )

    return {"statusCode": 200, "body": "Evaluation completed"}