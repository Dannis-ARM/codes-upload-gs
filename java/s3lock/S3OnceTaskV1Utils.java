import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.AmazonS3Exception;
import com.amazonaws.services.s3.model.PutObjectRequest;
import java.io.ByteArrayInputStream;
import java.util.Date;

/**
 * A utility to run a non-idempotent task ONLY ONCE across distributed servers, using AWS S3 lock.
 * Works with AWS Java SDK V1 (com.amazonaws).
 */
public final class S3OnceTaskV1Utils {

    private static final ByteArrayInputStream EMPTY_CONTENT = new ByteArrayInputStream(new byte[0]);

    /**
     * Execute a task exactly once in a distributed environment using S3 atomic lock.
     * Lock will automatically expire after the given seconds.
     *
     * @param s3Client       AWS S3 client (SDK V1)
     * @param bucket         S3 bucket name
     * @param lockKey        Unique lock file path (e.g. ".locks/process_data")
     * @param expireSeconds  Lock expiration time in seconds
     * @param task           Non-idempotent task to run once
     * @return true if executed by this node, false if skipped
     */
    public static boolean executeOnce(AmazonS3 s3Client,
                                      String bucket,
                                      String lockKey,
                                      long expireSeconds,
                                      Runnable task) {
        try {
            // Build lock upload request
            PutObjectRequest request = new PutObjectRequest(bucket, lockKey, EMPTY_CONTENT);

            // Critical: atomic lock - create only if object does NOT exist
            request.withIfNoneMatch("*");

            // Set auto-expiration time
            Date expireDate = new Date(System.currentTimeMillis() + expireSeconds * 1000);
            request.withExpires(expireDate);

            // Atomic create: only one server succeeds
            s3Client.putObject(request);

            // Run the non-idempotent operation
            task.run();
            return true;

        } catch (AmazonS3Exception e) {
            // 412 Precondition Failed = lock already exists
            if (e.getStatusCode() == 412) {
                return false;
            }
            // Re-throw other errors
            throw new RuntimeException("Failed to acquire S3 lock", e);
        }
    }
}