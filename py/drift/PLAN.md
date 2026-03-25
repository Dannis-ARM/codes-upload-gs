# Service Catalog Drift Detection CLI

## Overview
A CLI tool to detect and compare drift between Service Catalog provisioned products and their underlying CloudFormation stacks.

## Features
- Detect drift using provisioned product ID
- Extract CloudFormation Stack ARN from Service Catalog outputs
- Compare actual stack state vs expected state
- Human-readable output format

## Usage

### Input Parameters
| Parameter | Description |
|-----------|-------------|
| `--provisioned-product-id` | Service Catalog provisioned product ID (required) |
| `--region` | AWS region (optional, defaults to config) |
| `--profile` | AWS profile (optional) |

### Output Formats
| Format | Description |
|--------|-------------|
| `--human` | Human-readable format with table view |

## Core Logic

### 1. Get Provisioned Product Info
- Call `servicecatalog.describe_provisioned_product()` with product ID
- Extract CloudFormation Stack ARN from `Outputs`

### 2. Drift Detection
- Call `cloudformation.detect_stack_drift()` on the extracted Stack ARN
- Poll `describe_stack_drift_detection_status()` until complete
- Call `cloudformation.describe_stack_resource_drifts()` to get detailed diffs

### 3. Compare & Output
- Categorize resources: `MODIFIED`, `DELETED`, `ADDED`, `NOT_CHECKED`, `IN_SYNC`
- Format differences in human-readable table

## Human Output Format
```
=== Service Catalog Drift Report ===
Product ID:    prod-xxxxx
Region:        us-east-1
Stack ARN:     arn:aws:cloudformation:us-east-1:123456789:stack/...
Drift Status:  DRIFTED / IN_SYNC / UNKNOWN
Detected At:   2026-03-25T10:00:00Z

📋 Drift Summary:
  MODIFIED:   3
  DELETED:    1
  ADDED:      0
  NOT_CHECKED: 0
  IN_SYNC:    15

📋 Resources with Drift:
+-----------------------+------------------------------+-----------+------------------+------------------+
| Logical ID            | Resource Type                | Status    | Expected         | Actual           |
+-----------------------+------------------------------+-----------+------------------+------------------+
| MyInstance            | AWS::EC2::Instance           | MODIFIED  | t3.micro         | t3.small         |
| MySecurityGroup       | AWS::EC2::SecurityGroup      | DELETED   | -                | -                |
+-----------------------+------------------------------+-----------+------------------+------------------+
```

## File Structure
```
py/drift/
├── PLAN.md                    # This plan
└── service_catalog_drift.py   # Main CLI script
```

## Dependencies
- boto3
- Python >= 3.10

## Error Handling
- Handle missing provisioned product
- Handle stack not found
- Handle drift detection timeout
- Handle API throttling

## Logging
- Use Python logging module
- Configurable log level via environment variable `LOG_LEVEL`
