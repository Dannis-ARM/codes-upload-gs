# AWS Private Certificate Authority (AWS PCA) and Amazon S3 Integration

**AWS Private Certificate Authority (AWS PCA)** is a fully managed, highly available service that enables organizations to create and manage private certificate authorities in the AWS Cloud. It allows you to issue private certificates for internal applications, microservices, IoT devices, code signing, and more — without the operational burden of running your own PKI infrastructure.

One of the most important integrations of AWS PCA is with **Amazon S3**, which serves as the storage backbone for two critical components: **Certificate Revocation Lists (CRLs)** and **Audit Reports**.

## What is AWS Private CA?

AWS PCA lets you build a complete private CA hierarchy (Root CA + Subordinate CAs) using the AWS Management Console, CLI, or SDK. Key benefits include:

- Fully managed infrastructure with built-in high availability across multiple Availability Zones
- Hardware Security Modules (HSMs) for private key protection (FIPS 140-2 Level 3)
- Pay-as-you-go pricing (monthly CA fee + per-certificate issuance)
- Seamless integration with AWS Certificate Manager (ACM), ELB, CloudFront, API Gateway, EKS, and more
- Support for certificate templates, custom extensions, and revocation mechanisms

## AWS PCA Integration with Amazon S3

AWS PCA uses Amazon S3 to automatically store and distribute two essential artifacts:

### 1. Certificate Revocation List (CRL) — Primary Integration

When a certificate is revoked, AWS PCA generates and maintains a **CRL** (a list of revoked certificate serial numbers). The service automatically uploads the latest CRL to your designated S3 bucket.

**Key Features:**
- AWS PCA periodically updates the CRL and deposits it in S3
- CRL files are stored under a path like `crl/<CA-ID>.crl`
- Supports **CustomCname** to hide the actual S3 bucket name and use a friendly domain (commonly paired with Amazon CloudFront)
- Two ACL options:
  - `PUBLIC_READ` — CRL is publicly accessible (simpler but less secure)
  - `BUCKET_OWNER_FULL_CONTROL` — Private object (recommended for security; requires CloudFront + Origin Access Control for client access)

**Why S3?**  
Clients (browsers, applications, devices, TLS libraries) need a reliable HTTP/HTTPS endpoint to download the CRL for revocation checking. S3 provides durable, highly available storage with global edge access when combined with CloudFront.

### 2. Audit Reports

You can generate detailed audit reports that list all certificates issued or revoked by your CA, including private key usage events.

- Reports are saved as CSV or JSON files in your specified S3 bucket
- Useful for compliance (SOC 2, PCI-DSS, internal audits)
- Can be automated using Lambda + EventBridge + S3 event notifications

## Configuration Overview

### Preparing the S3 Bucket
- Create a dedicated S3 bucket (or use an existing one)
- Attach a bucket policy allowing the AWS PCA service principal (`acm-pca.amazonaws.com`) to perform:
  - `s3:PutObject`
  - `s3:GetBucketAcl`
  - `s3:GetBucketLocation`
- Enable server-side encryption (SSE-S3 or SSE-KMS) for added security
- Consider enabling S3 Block Public Access (BPA) and using CloudFront for private CRL distribution

### Example: CRL Configuration (CLI)

```bash
aws acm-pca update-certificate-authority \
    --certificate-authority-arn arn:aws:acm-pca:us-east-1:123456789012:certificate-authority/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
    --revocation-configuration '{
        "CrlConfiguration": {
            "Enabled": true,
            "ExpirationInDays": 7,
            "S3BucketName": "my-pca-crl-bucket",
            "S3ObjectAcl": "BUCKET_OWNER_FULL_CONTROL",
            "CustomCname": "crl.example.internal"
        }
    }'