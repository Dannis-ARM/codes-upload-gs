package s3lock;

public import com.obs.services.ObsClient;
import com.obs.services.exception.ObsException;
import com.obs.services.model.PutObjectRequest;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.util.Date;

/**
 * Utility to run a task only once across distributed servers, with automatic lock expiration.
 */
public final class ObsOnceTaskUtils {

    private static final InputStream EMPTY_CONTENT = new ByteArrayInputStream(new byte[0]);

    /**
     * Execute a task only once globally, with lock auto-expire.
     *
     * @param obsClient OBS client
     * @param bucketName OBS bucket name
     * @param lockKey unique key for lock object
     * @param expireAfterSeconds lock will expire after this many seconds
     * @param task non-idempotent task to run once
     * @return true if executed by this node, false if skipped
     */
    public static boolean executeOnceWithExpire(ObsClient obsClient,
                                                String bucketName,
                                                String lockKey,
                                                long expireAfterSeconds,
                                                Runnable task) {
        try {
            PutObjectRequest req = new PutObjectRequest();
            req.setBucketName(bucketName);
            req.setObjectKey(lockKey);
            req.setInput(EMPTY_CONTENT);
            req.setIfNoneMatchTag("*");

            // Set object expiration time
            long expireTimeMs = System.currentTimeMillis() + expireAfterSeconds * 1000;
            req.setExpires(new Date(expireTimeMs));

            // Atomic create only if not exists
            obsClient.putObject(req);

            // Run the task
            task.run();
            return true;

        } catch (ObsException e) {
            // Lock already exists
            if (e.getResponseCode() == 412) {
                return false;
            }
            throw new RuntimeException("Failed to acquire OBS lock", e);
        }
    }
} {
    
}
