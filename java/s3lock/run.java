// Lock expires after 1 hour (3600 seconds)
boolean executed = ObsOnceTaskUtils.executeOnceWithExpire(
        obsClient,
        "my-bucket",
        ".locks/process-s3-data",
        3600,
        () -> {
            // Your non-idempotent operation here
            System.out.println("Task executed once");
        }
);