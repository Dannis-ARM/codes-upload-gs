// 1 hour expiration
boolean executed = S3OnceTaskUtils.executeOnce(
        s3Client,
        "your-bucket",
        ".locks/your-task-id",
        3600,
        () -> {
            // Your non-idempotent logic here
            System.out.println("Task executed ONCE");
        }
);