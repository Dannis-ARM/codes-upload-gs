#!/usr/bin/env python3
"""
Service Catalog Drift Detection CLI

Detect and compare drift between Service Catalog provisioned products
and their underlying CloudFormation stacks.
"""

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class DriftStatus(str, Enum):
    """Stack drift status."""
    DRIFTED = "DRIFTED"
    IN_SYNC = "IN_SYNC"
    UNKNOWN = "UNKNOWN"


class ResourceDriftStatus(str, Enum):
    """Resource-level drift status."""
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    ADDED = "ADDED"
    NOT_CHECKED = "NOT_CHECKED"
    IN_SYNC = "IN_SYNC"


@dataclass
class StackInfo:
    """CloudFormation stack information."""
    stack_name: str
    stack_arn: str
    drift_status: DriftStatus


@dataclass
class ResourceDrift:
    """Individual resource drift information."""
    logical_id: str
    physical_id: str
    resource_type: str
    status: ResourceDriftStatus
    expected_hash: Optional[str]
    actual_hash: Optional[str]
    property_differences: list


@dataclass
class DriftReport:
    """Complete drift detection report."""
    product_id: str
    region: str
    stack_info: StackInfo
    detected_at: str
    resource_drifts: list[ResourceDrift]
    
    @property
    def summary(self) -> dict:
        """Get drift summary counts."""
        summary = {
            "MODIFIED": 0,
            "DELETED": 0,
            "ADDED": 0,
            "NOT_CHECKED": 0,
            "IN_SYNC": 0,
        }
        for drift in self.resource_drifts:
            summary[drift.status.value] += 1
        return summary
    
    @property
    def has_drift(self) -> bool:
        """Check if any drift detected."""
        for drift in self.resource_drifts:
            if drift.status != ResourceDriftStatus.IN_SYNC:
                return True
        return False


class ServiceCatalogDriftDetector:
    """Service Catalog drift detection handler."""
    
    POLL_INTERVAL = 5  # seconds
    MAX_POLL_ATTEMPTS = 60
    
    def __init__(self, region: Optional[str] = None, profile: Optional[str] = None):
        """Initialize with optional region and profile."""
        session_kwargs = {}
        if profile:
            session_kwargs["profile_name"] = profile
        if region:
            session_kwargs["region_name"] = region
            
        self.session = boto3.Session(**session_kwargs)
        self.sc_client = self.session.client("servicecatalog")
        self.cf_client = self.session.client("cloudformation")
        self.region = self.session.region_name or "us-east-1"
        
        logger.info(f"Initialized detector for region: {self.region}")
    
    def get_stack_arn_from_product(self, product_id: str) -> str:
        """Extract CloudFormation Stack ARN from provisioned product."""
        logger.info(f"Describing provisioned product: {product_id}")
        
        try:
            response = self.sc_client.describe_provisioned_product(
                Id=product_id
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                raise ValueError(f"Provisioned product not found: {product_id}")
            raise
        
        pp_detail = response["ProvisionedProductDetail"]
        
        # Try to get CloudFormation stack ARN from outputs
        stack_arn = pp_detail.get("CloudFormationStackArn")
        if not stack_arn:
            raise ValueError(
                f"No CloudFormation stack associated with product: {product_id}"
            )
        
        logger.info(f"Found stack ARN: {stack_arn}")
        return stack_arn
    
    def detect_stack_drift(self, stack_arn: str) -> tuple[DriftStatus, str]:
        """Initiate and poll drift detection."""
        stack_name = stack_arn.split("/")[-1]
        logger.info(f"Starting drift detection for stack: {stack_name}")
        
        # Start drift detection
        response = self.cf_client.detect_stack_drift(
            StackName=stack_arn
        )
        detection_id = response["StackDriftDetectionId"]
        logger.info(f"Drift detection started: {detection_id}")
        
        # Poll for completion
        for attempt in range(self.MAX_POLL_ATTEMPTS):
            status_response = self.cf_client.describe_stack_drift_detection_status(
                StackDriftDetectionId=detection_id
            )
            
            status = status_response["DetectionStatus"]
            logger.debug(f"Poll {attempt + 1}: status={status}")
            
            if status == "DETECTION_COMPLETE":
                drift_status = DriftStatus.DRIFTED if status_response["StackDriftStatus"] == "DRIFTED" else DriftStatus.IN_SYNC
                detected_at = status_response["DetectionStatus"].replace("DETECTION_COMPLETE", "")
                return drift_status, status_response["LastCheckTimestamp"].isoformat()
            
            if status == "DETECTION_FAILED":
                raise RuntimeError("Drift detection failed")
            
            time.sleep(self.POLL_INTERVAL)
        
        raise TimeoutError(f"Drift detection timed out after {self.MAX_POLL_ATTEMPTS} attempts")
    
    def get_stack_info(self, stack_arn: str) -> StackInfo:
        """Get current stack information."""
        try:
            response = self.cf_client.describe_stacks(
                StackName=stack_arn
            )
            stack = response["Stacks"][0]
            
            drift_status = DriftStatus.DRIFTED if stack.get("DriftInformation", {}).get("StackDriftStatus") == "DRIFTED" else DriftStatus.IN_SYNC
            
            return StackInfo(
                stack_name=stack["StackName"],
                stack_arn=stack_arn,
                drift_status=drift_status,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationError":
                raise ValueError(f"Stack not found: {stack_arn}")
            raise
    
    def get_resource_drifts(self, stack_arn: str) -> list[ResourceDrift]:
        """Get detailed resource drift information."""
        logger.info("Fetching resource drifts...")
        
        drifts = []
        paginator = self.cf_client.get_paginator("describe_stack_resource_drifts")
        
        try:
            for page in paginator.paginate(StackName=stack_arn):
                for drift in page["StackResourceDrifts"]:
                    drifts.append(ResourceDrift(
                        logical_id=drift["LogicalResourceId"],
                        physical_id=drift.get("PhysicalResourceId", "-"),
                        resource_type=drift["ResourceType"],
                        status=ResourceDriftStatus(drift["StackResourceDriftStatus"]),
                        expected_hash=drift.get("ExpectedProperties"),
                        actual_hash=drift.get("ActualProperties"),
                        property_differences=drift.get("PropertyDifferences", []),
                    ))
        except ClientError as e:
            logger.warning(f"Error fetching resource drifts: {e}")
        
        logger.info(f"Found {len(drifts)} resources")
        return drifts
    
    def detect(self, product_id: str) -> DriftReport:
        """Main detection workflow."""
        # Step 1: Get stack ARN from product
        stack_arn = self.get_stack_arn_from_product(product_id)
        
        # Step 2: Get stack info
        stack_info = self.get_stack_info(stack_arn)
        
        # Step 3: Detect drift
        drift_status, detected_at = self.detect_stack_drift(stack_arn)
        stack_info.drift_status = drift_status
        
        # Step 4: Get resource drifts
        resource_drifts = self.get_resource_drifts(stack_arn)
        
        return DriftReport(
            product_id=product_id,
            region=self.region,
            stack_info=stack_info,
            detected_at=detected_at,
            resource_drifts=resource_drifts,
        )


class HumanOutputFormatter:
    """Format drift report for human readability."""
    
    @staticmethod
    def format(report: DriftReport) -> str:
        """Format report as human-readable text."""
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("Service Catalog Drift Report")
        lines.append("=" * 60)
        lines.append(f"Product ID:    {report.product_id}")
        lines.append(f"Region:        {report.region}")
        lines.append(f"Stack ARN:     {report.stack_info.stack_arn}")
        lines.append(f"Stack Name:    {report.stack_info.stack_name}")
        lines.append(f"Drift Status:  {report.stack_info.drift_status.value}")
        lines.append(f"Detected At:   {report.detected_at}")
        lines.append("")
        
        # Summary
        summary = report.summary
        lines.append("Drift Summary:")
        lines.append(f"  MODIFIED:    {summary['MODIFIED']}")
        lines.append(f"  DELETED:     {summary['DELETED']}")
        lines.append(f"  ADDED:       {summary['ADDED']}")
        lines.append(f"  NOT_CHECKED: {summary['NOT_CHECKED']}")
        lines.append(f"  IN_SYNC:     {summary['IN_SYNC']}")
        lines.append("")
        
        # Resource table
        drifted_resources = [r for r in report.resource_drifts if r.status != ResourceDriftStatus.IN_SYNC]
        
        if drifted_resources:
            lines.append("Resources with Drift:")
            lines.append("+" + "-" * 23 + "+" + "-" * 30 + "+" + "-" * 12 + "+" + "-" * 20 + "+" + "-" * 20 + "+")
            lines.append("| {:<21} | {:<28} | {:<10} | {:<18} | {:<18} |".format(
                "Logical ID", "Resource Type", "Status", "Expected", "Actual"
            ))
            lines.append("+" + "-" * 23 + "+" + "-" * 30 + "+" + "-" * 12 + "+" + "-" * 20 + "+" + "-" * 20 + "+")
            
            for drift in drifted_resources:
                expected = HumanOutputFormatter._get_diff_summary(drift.expected_hash, drift.actual_hash, "expected")
                actual = HumanOutputFormatter._get_diff_summary(drift.actual_hash, drift.expected_hash, "actual")
                
                lines.append("| {:<21} | {:<28} | {:<10} | {:<18} | {:<18} |".format(
                    drift.logical_id[:21],
                    drift.resource_type[:28],
                    drift.status.value[:10],
                    expected[:18],
                    actual[:18],
                ))
            
            lines.append("+" + "-" * 23 + "+" + "-" * 30 + "+" + "-" * 12 + "+" + "-" * 20 + "+" + "-" * 20 + "+")
        else:
            lines.append("No resources with drift detected.")
        
        return "\n".join(lines)
    
    @staticmethod
    def _get_diff_summary(current: Optional[str], other: Optional[str], which: str) -> str:
        """Extract summary from property diff."""
        if not current or current == other:
            return "-"
        
        # Parse JSON if possible
        try:
            import json
            data = json.loads(current)
            if isinstance(data, dict):
                # Return first key=value for brevity
                if data:
                    key = list(data.keys())[0]
                    return f"{key}: {str(data[key])[:10]}"
        except (json.JSONDecodeError, ValueError):
            return current[:18] if len(current) > 18 else current
        
        return current[:18] if len(current) > 18 else current


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Detect drift in Service Catalog provisioned products"
    )
    
    parser.add_argument(
        "--provisioned-product-id",
        required=True,
        help="Service Catalog provisioned product ID"
    )
    parser.add_argument(
        "--region",
        help="AWS region (defaults to config)"
    )
    parser.add_argument(
        "--profile",
        help="AWS profile (overrides config)"
    )
    parser.add_argument(
        "--human",
        action="store_true",
        default=True,
        help="Human-readable output (default: True)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    try:
        detector = ServiceCatalogDriftDetector(
            region=args.region,
            profile=args.profile,
        )
        
        logger.info(f"Detecting drift for product: {args.provisioned_product_id}")
        report = detector.detect(args.provisioned_product_id)
        
        if args.human:
            output = HumanOutputFormatter.format(report)
            print(output)
        else:
            # Default to human format
            output = HumanOutputFormatter.format(report)
            print(output)
        
        # Exit with non-zero if drift detected
        sys.exit(1 if report.has_drift else 0)
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        sys.exit(2)
    except (ClientError, BotoCoreError) as e:
        logger.error(f"AWS error: {e}")
        sys.exit(3)
    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        sys.exit(4)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(5)


if __name__ == "__main__":
    main()
