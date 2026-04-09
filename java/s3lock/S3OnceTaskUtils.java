import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.time.Instant;

/**
 * Utility to execute a task ONLY ONCE across multiple servers, using AWS S3 atomic lock.
 * Supports automatic lock expiration.
 */
public final class S3OnceTaskUtils {

    private static final InputStream EMPTY_CONTENT = new ByteArrayInputStream(new byte[0]);

    /**
     * Execute a non-idempotent task exactly once in a distributed system.
     * Uses S3 conditional create (if-none-match) + object expiration for auto-release.
     *
     * @param s3Client AWS S3 client
     * @param bucket S3 bucket name
     * @param lockKey unique lock path (e.g. ".locks/task_process_data")
     * @param expireSeconds lock will expire after this many seconds
     * @param task task to run once
     * @return true if this node executed the task; false if skipped
     */
    public static boolean executeOnce(S3Client s3Client,
                                      String bucket,
                                      String lockKey,
                                      long expireSeconds,
                                      Runnable task) {
        try {
            // Build request: atomically create lock ONLY IF IT DOES NOT EXIST
            PutObjectRequest request = PutObjectRequest.builder()
                    .bucket(bucket)
                    .key(lockKey)
                    .ifNoneMatch("*")  // Core atomic lock: create only if not exists
                    .expires(Instant.now().plusSeconds(expireSeconds))  // Auto expire lock
                    .build();

            // Atomic upload: only one server succeeds
            s3Client.putObject(request, EMPTY_CONTENT);

            // Run the non-idempotent task
            task.run();
            return true;

        } catch (S3Exception e) {
            // 412 Precondition Failed = lock already exists
            if (e.statusCode() == 412) {
                return false;
            }
            // Throw other errors (network, permission, etc.)
            throw new RuntimeException("Failed to acquire S3 lock", e);
        }
    }
}