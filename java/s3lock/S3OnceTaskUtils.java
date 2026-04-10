import software.amazon.awssdk.core.sync.ResponseTransformer;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;
import java.nio.charset.StandardCharsets;

public class S3OnceTaskUtils {

    /**
     * Execute a task exactly once in a distributed environment.
     * Race-condition safe, auto-expire, invalid content = expired.
     */
    public static <T> T executeOnce(
            S3Client s3Client,
            String bucket,
            String lockKey,
            long lockTtlSeconds,
            java.util.concurrent.Callable<T> task
    ) {
        long now = System.currentTimeMillis() / 1000;
        long newExpireTime = now + lockTtlSeconds;
        byte[] newLockBody = String.valueOf(newExpireTime).getBytes(StandardCharsets.UTF_8);

        // ==============================================
        // Step 1: Try to create lock atomically (if not exists)
        // ==============================================
        try {
            PutObjectRequest req = PutObjectRequest.builder()
                    .bucket(bucket)
                    .key(lockKey)
                    .ifNoneMatch("*")
                    .build();

            s3Client.putObject(req, software.amazon.awssdk.core.sync.RequestBody.fromBytes(newLockBody));
            return callTask(task);
        } catch (S3Exception e) {
            if (e.statusCode() != 412) {
                throw e;
            }
        }

        // ==============================================
        // Step 2: Read existing lock & validate
        // ==============================================
        Long expireTs = null;
        String etag = null;

        try {
            // Correct Java 2.x way to read bytes
            byte[] bodyBytes = s3Client.getObject(
                    GetObjectRequest.builder().bucket(bucket).key(lockKey).build(),
                    ResponseTransformer.toBytes()
            ).asByteArray();

            etag = s3Client.headObject(
                    software.amazon.awssdk.services.s3.model.HeadObjectRequest.builder()
                            .bucket(bucket).key(lockKey).build()
            ).eTag();

            try {
                String content = new String(bodyBytes, StandardCharsets.UTF_8).trim();
                expireTs = Long.parseLong(content);
            } catch (Exception ignored) {
                expireTs = 0L; // invalid content → expired
            }

            if (expireTs > now) {
                return null;
            }

        } catch (Exception ignored) {
            expireTs = 0L; // read failed → expired
        }

        // ==============================================
        // Step 3: Atomic takeover with IfMatch (NO RACE)
        // ==============================================
        try {
            PutObjectRequest.Builder builder = PutObjectRequest.builder()
                    .bucket(bucket)
                    .key(lockKey);

            if (etag != null) {
                builder.ifMatch(etag);
            }

            s3Client.putObject(builder.build(), software.amazon.awssdk.core.sync.RequestBody.fromBytes(newLockBody));
            return callTask(task);

        } catch (S3Exception e) {
            if (e.statusCode() == 412 || e.statusCode() == 404) {
                return null;
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