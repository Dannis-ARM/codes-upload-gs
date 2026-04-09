// Your existing SDK V1 S3 client
AmazonS3 s3Client = ...;

// Run task once, lock expires after 1 hour (3600s)
boolean executed = S3OnceTaskV1Utils.executeOnce(
    s3Client,
    "your-bucket",
    ".locks/your-task-name",
    3600,
    () -> {
        // Your non-idempotent logic here
        System.out.println("Task executed ONCE across all servers");
    }
);