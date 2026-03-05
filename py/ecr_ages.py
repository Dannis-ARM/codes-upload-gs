import boto3
import json
import datetime
from typing import Dict, Any, Set, Tuple, List, Optional
from botocore.exceptions import ClientError
import logging

# Use Any for boto3 clients (practical approach)
from typing import Any as Boto3Client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_IMAGE_AGE_DAYS = 90
RESOURCE_TYPE = "AWS::ECS::Service"


# ────────────────────────────────────────────────
# Environment & Clients
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
    """Create boto3 clients."""
    return {
        "ecs": boto3.client("ecs", region_name=region),
        "ecr": boto3.client("ecr", region_name=region),
        "config": boto3.client("config", region_name=region),
    }


# ────────────────────────────────────────────────
# ECS Service Discovery
# ────────────────────────────────────────────────

def list_all_ecs_clusters(ecs_client: Boto3Client) -> List[str]:
    """List all ECS cluster ARNs in the account/region."""
    clusters: List[str] = []
    paginator = ecs_client.get_paginator("list_clusters")
    for page in paginator.paginate():
        clusters.extend(page.get("clusterArns", []))
    return clusters


def list_services_in_cluster(
    ecs_client: Boto3Client, cluster_arn: str
) -> List[str]:
    """List all active service ARNs in a given cluster."""
    services: List[str] = []
    paginator = ecs_client.get_paginator("list_services")
    for page in paginator.paginate(cluster=cluster_arn):
        services.extend(page.get("serviceArns", []))
    return services


def get_service_name_from_arn(service_arn: str) -> Optional[str]:
    """Extract service name from full ARN."""
    parts = service_arn.split("/")
    return parts[-1] if len(parts) >= 2 else None


def build_service_evaluation(
    service_arn: str,
    compliance: str,
    annotation: str,
    ordering_timestamp: str,
) -> Dict[str, Any]:
    """Build one evaluation item for put_evaluations."""
    return {
        "ComplianceResourceType": RESOURCE_TYPE,
        "ComplianceResourceId": service_arn,  # 使用完整 ARN 作為 resourceId
        "ComplianceType": compliance,
        "Annotation": annotation[:400],
        "OrderingTimestamp": ordering_timestamp,
    }


# ────────────────────────────────────────────────
# Core logic (same as before)
# ────────────────────────────────────────────────

def parse_cluster_and_service_from_arn(service_arn: str) -> Tuple[Optional[str], Optional[str]]:
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
    try:
        resp = ecs_client.describe_services(cluster=cluster_arn, services=[service_name])
        services = resp.get("services", [])
        if not services or services[0]["status"] != "ACTIVE":
            return None

        for dep in services[0].get("deployments", []):
            if dep["status"] == "PRIMARY":
                return dep["taskDefinition"]
        return None
    except ClientError as exc:
        logger.warning(f"Failed to describe service {service_name} in {cluster_arn}", exc_info=True)
        return None


def extract_ecr_image_uris_from_task_definition(
    ecs_client: Boto3Client, task_def_arn: str
) -> Set[str]:
    try:
        resp = ecs_client.describe_task_definition(taskDefinition=task_def_arn)
        images: Set[str] = set()
        for c in resp["taskDefinition"].get("containerDefinitions", []):
            img = c.get("image", "")
            if ".dkr.ecr." in img and ".amazonaws.com" in img:
                images.add(img)
        return images
    except ClientError as exc:
        logger.warning(f"Failed to describe task def {task_def_arn}", exc_info=True)
        return set()


def fetch_currently_used_ecr_images(
    ecs_client: Boto3Client,
    service_arn: str,
    region: str,
    account_id: str,
) -> Set[str]:
    cluster_name, service_name = parse_cluster_and_service_from_arn(service_arn)
    if not cluster_name or not service_name:
        return set()

    cluster_arn = f"arn:aws:ecs:{region}:{account_id}:cluster/{cluster_name}"
    td_arn = get_primary_task_definition_arn(ecs_client, cluster_arn, service_name)
    if not td_arn:
        return set()

    return extract_ecr_image_uris_from_task_definition(ecs_client, td_arn)


def parse_repo_and_tag_from_image_uri(image_uri: str) -> Tuple[Optional[str], str]:
    try:
        repo_part = image_uri.split("/", 1)[1]
        if ":" in repo_part:
            return repo_part.rsplit(":", 1)
        return repo_part, "latest"
    except Exception:
        return None, "unknown"


def is_ecr_image_older_than_threshold(
    ecr_client: Boto3Client, image_uri: str, max_days: int = MAX_IMAGE_AGE_DAYS
) -> Tuple[bool, str]:
    repo_name, tag = parse_repo_and_tag_from_image_uri(image_uri)
    if not repo_name:
        return True, f"Invalid ECR URI: {image_uri}"

    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        paginator = ecr_client.get_paginator("describe_images")
        for page in paginator.paginate(repositoryName=repo_name):
            for detail in page.get("imageDetails", []):
                if tag in detail.get("imageTags", []):
                    age = (now - detail["imagePushedAt"]).days
                    if age > max_days:
                        return True, f"{image_uri} is {age} days old (> {max_days})"
                    return False, f"{image_uri} is {age} days old"
        return True, f"Tag {tag} not found: {image_uri}"
    except ClientError as exc:
        return True, f"ECR error for {image_uri}: {exc.response['Error']['Message']}"


def evaluate_images(
    ecr_client: Boto3Client, image_uris: Set[str]
) -> Tuple[str, str]:
    violations = []
    for uri in image_uris:
        old, msg = is_ecr_image_older_than_threshold(ecr_client, uri)
        if old:
            violations.append(msg)

    if violations:
        return "NON_COMPLIANT", "; ".join(violations)[:500]
    count = len(image_uris)
    msg = f"All {count} ECR images ≤ {MAX_IMAGE_AGE_DAYS} days" if count else "No ECR images in use"
    return "COMPLIANT", msg


# ────────────────────────────────────────────────
# Submit to Config
# ────────────────────────────────────────────────

def submit_evaluations(
    config_client: Boto3Client,
    evaluations: List[Dict[str, Any]],
    result_token: Optional[str] = None,
) -> None:
    """Submit batch of evaluations to AWS Config."""
    if not evaluations:
        return

    try:
        config_client.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token or "scheduled-evaluation",  # scheduled 時可自訂或留空
        )
        logger.info(f"Submitted {len(evaluations)} evaluations to Config")
    except ClientError as exc:
        logger.error("Failed to submit evaluations to Config", exc_info=True)


# ────────────────────────────────────────────────
# Main Handler - Scheduled Event
# ────────────────────────────────────────────────

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for scheduled Lambda (every 12 hours)."""
    env = get_lambda_env_info(context)
    region = env["region"]
    account_id = env["account_id"]
    clients = initialize_clients(region)

    # 從 event 拿 timestamp，如果沒有就用現在時間
    try:
        invoking = json.loads(event.get("invokingEvent", "{}"))
        ordering_ts = invoking.get("notificationCreationTime", datetime.datetime.utcnow().isoformat() + "Z")
    except Exception:
        ordering_ts = datetime.datetime.utcnow().isoformat() + "Z"

    evaluations: List[Dict[str, Any]] = []

    # 掃描所有 cluster & service
    clusters = list_all_ecs_clusters(clients["ecs"])
    logger.info(f"Found {len(clusters)} ECS clusters")

    for cluster_arn in clusters:
        service_arns = list_services_in_cluster(clients["ecs"], cluster_arn)
        logger.info(f"Cluster {cluster_arn} has {len(service_arns)} services")

        for svc_arn in service_arns:
            images = fetch_currently_used_ecr_images(
                clients["ecs"], svc_arn, region, account_id
            )

            compliance, annotation = evaluate_images(clients["ecr"], images)

            eval_item = build_service_evaluation(
                service_arn=svc_arn,
                compliance=compliance,
                annotation=annotation,
                ordering_timestamp=ordering_ts,
            )
            evaluations.append(eval_item)

    # 批量送出
    submit_evaluations(clients["config"], evaluations)

    return {
        "statusCode": 200,
        "body": f"Processed {len(evaluations)} ECS services"
    }