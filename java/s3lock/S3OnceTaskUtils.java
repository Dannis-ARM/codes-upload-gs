import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;
import java.nio.charset.StandardCharsets;

public class S3OnceTaskUtils {

    /**
     * Execute a task exactly once in distributed environment.
     * Safe from race conditions, supports auto-expiration, treats invalid content as expired.
     *
     * @param s3Client AWS Java SDK v2 S3 client
     * @param bucket S3 bucket name
     * @param lockKey lock key path
     * @param lockTtlSeconds lock TTL
     * @param task task to run once
     * @return task result if executed, null if skipped
     */
    public static <T> T executeOnce(
            S3Client s3Client,
            String bucket,
            String lockKey,
            long lockTtlSeconds,
            java.util.concurrent.Callable<T> task
    ) {
        long now = System.currentTimeMillis() / 1000;
        long newExpire = now + lockTtlSeconds;
        byte[] newLockContent = String.valueOf(newExpire).getBytes(StandardCharsets.UTF_8);

        // ==============================================
        // Step 1: Try to create lock atomically (if not exists)
        // ==============================================
        try {
            PutObjectRequest req = PutObjectRequest.builder()
                    .bucket(bucket)
                    .key(lockKey)
                    .ifNoneMatch("*")
                    .build();

            s3Client.putObject(req, software.amazon.awssdk.core.sync.RequestBody.fromBytes(newLockContent));
            return callTask(task);
        } catch (S3Exception e) {
            if (e.statusCode() != 412) {
                throw e;
            }
        }

        // ==============================================
        // Step 2: Lock exists – read and validate
        // ==============================================
        Long expireTs = null;
        String etag = null;

        try {
            GetObjectResponse getResp = s3Client.getObject(
                    GetObjectRequest.builder().bucket(bucket).key(lockKey).build(),
                    software.amazon.awssdk.core.sync.ResponseTransformer.toBytes()
            );

            etag = getResp.eTag();
            byte[] body = getResp.contentAsByteArray();

            try {
                String content = new String(body, StandardCharsets.UTF_8).trim();
                expireTs = Long.parseLong(content);
            } catch (Exception ignored) {
                expireTs = 0L; // invalid body → treat as expired
            }

            // Not expired → skip
            if (expireTs > now) {
                return null;
            }

        } catch (Exception ignored) {
            expireTs = 0L; // read failed → treat as expired
        }

        // ==============================================
        // Step 3: Atomic takeover (IfMatch = no race condition)
        // ==============================================
        try {
            PutObjectRequest.Builder builder = PutObjectRequest.builder()
                    .bucket(bucket)
                    .key(lockKey);

            if (etag != null) {
                builder.ifMatch(etag);
            }

            s3Client.putObject(builder.build(), software.amazon.awssdk.core.sync.RequestBody.fromBytes(newLockContent));
            return callTask(task);

        } catch (S3Exception e) {
            if (e.statusCode() == 412 || e.statusCode() == 404) {
                return null; // lost race
            }
            throw e;
        }
    }

    private static <T> T callTask(java.util.concurrent.Callable<T> task) {
        try {
            return task.call();
        } catch (Exception e) {
            throw new RuntimeException("Task execution failed", e);
        }
    }
}