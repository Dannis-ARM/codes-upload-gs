import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.cloudtrail.CloudTrailClient;
import software.amazon.awssdk.services.cloudtrail.model.LookupEventsRequest;
import software.amazon.awssdk.services.cloudtrail.model.LookupAttribute;
import software.amazon.awssdk.services.cloudtrail.model.AttributeKey;
import software.amazon.awssdk.services.cloudtrail.model.Event;
import software.amazon.awssdk.services.cloudtrail.model.LookupEventsResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

public class CloudTrailFilter {

    // 使用 Jackson ObjectMapper 来解析 CloudTrailEvent 中的 JSON 字符串
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) {
        // --- 替换为您的查询参数 ---
        final String TARGET_ACCESS_KEY_ID = "ASIA..."; // 临时凭证 Access Key ID
        final String TARGET_ROLE_NAME_PART = "MyAssumedRole"; // 希望过滤的 Role Name 的一部分
        final Region REGION = Region.US_EAST_1; // AWS 区域
        final long DAYS_AGO = 3; 

        // 1. 初始化 AWS CloudTrail 客户端
        try (CloudTrailClient cloudTrailClient = CloudTrailClient.builder()
                .region(REGION)
                .build()) {

            filterAndDisplayEventsAscending(cloudTrailClient, TARGET_ACCESS_KEY_ID, TARGET_ROLE_NAME_PART, DAYS_AGO);

        } catch (Exception e) {
            System.err.println("发生错误: " + e.getMessage());
            e.printStackTrace();
        }
    }

    /**
     * 过滤 CloudTrail 事件，并按时间正序（旧到新）显示。
     */
    public static void filterAndDisplayEventsAscending(
            CloudTrailClient client, 
            String accessKeyId, 
            String targetRoleName, 
            long daysAgo) {

        Instant endTime = Instant.now();
        Instant startTime = endTime.minus(daysAgo, ChronoUnit.DAYS);

        System.out.println("--- 搜索范围: " + startTime + " 到 " + endTime + " ---");
        System.out.println("--- 按 Access Key ID: " + accessKeyId + " 进行初步过滤... ---");

        List<EventSummary> allMatchingEvents = new ArrayList<>();
        String nextToken = null;

        // 设置初步过滤条件 (AccessKeyId)
        LookupAttribute lookupAttribute = LookupAttribute.builder()
                .attributeKey(AttributeKey.ACCESS_KEY_ID)
                .attributeValue(accessKeyId)
                .build();

        // 2. 循环分页查询（Java SDK 2.x 的分页是手动处理 nextToken）
        do {
            LookupEventsRequest request = LookupEventsRequest.builder()
                    .lookupAttributes(lookupAttribute)
                    .startTime(startTime)
                    .endTime(endTime)
                    .nextToken(nextToken)
                    // 可以设置 MaxResults，但通常默认即可
                    .build();

            LookupEventsResponse response = client.lookupEvents(request);
            nextToken = response.nextToken();

            // 3. 遍历当前页的事件并进行二次过滤
            for (Event event : response.events()) {
                String cloudTrailEventJson = event.cloudTrailEvent();
                
                try {
                    // 解析事件详情的 JSON 字符串
                    JsonNode eventDetail = MAPPER.readTree(cloudTrailEventJson);
                    
                    // 提取 Assume Role 的名称 (userIdentity.sessionContext.sessionIssuer.userName)
                    String sessionIssuerName = eventDetail
                            .path("userIdentity")
                            .path("sessionContext")
                            .path("sessionIssuer")
                            .path("userName")
                            .asText();
                    
                    // --- 二次过滤：根据 Principal Assume Role Name 检查 ---
                    if (sessionIssuerName.contains(targetRoleName)) {
                        allMatchingEvents.add(new EventSummary(
                                event.eventTime(),
                                event.eventName(),
                                sessionIssuerName
                        ));
                    }
                } catch (Exception e) {
                    System.err.println("解析 CloudTrailEvent JSON 失败或提取字段失败: " + e.getMessage());
                    // 继续处理下一个事件
                }
            }
        } while (nextToken != null && !nextToken.isEmpty());
        
        // 4. 核心步骤：反转列表以实现时间正序（早到晚）
        // CloudTrail API 默认返回的是时间倒序，因此我们需要反转列表
        // 注意：这里使用 Collections.reverse() 直接修改列表顺序
        Collections.reverse(allMatchingEvents);

        // 5. 打印时间正序的结果
        System.out.println("\n找到并二次过滤后符合条件的事件总数: " + allMatchingEvents.size());
        System.out.println("\n--- 结果 (时间正序：旧事件在上，新事件在下) ---");
        
        for (EventSummary summary : allMatchingEvents) {
            System.out.printf("✅ %s | 事件: %s | Role Session: %s%n", 
                                summary.eventTime, summary.eventName, summary.roleSession);
        }
    }
    
    // 内部类，用于存储过滤后的关键事件摘要信息
    private static class EventSummary {
        final Instant eventTime;
        final String eventName;
        final String roleSession;

        public EventSummary(Instant eventTime, String eventName, String roleSession) {
            this.eventTime = eventTime;
            this.eventName = eventName;
            this.roleSession = roleSession;
        }
    }
}