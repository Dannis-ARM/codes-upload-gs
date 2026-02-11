import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.athena.AthenaClient;
import software.amazon.awssdk.services.athena.model.*;
import software.amazon.awssdk.services.athena.paginators.GetQueryResultsIterable;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class CloudTrailAthenaClient {

    private final AthenaClient athenaClient;
    private final String s3OutputPath;
    private final String database;
    private final String tableName;

    public CloudTrailAthenaClient(String region, String s3OutputPath, String database, String tableName) {
        this.athenaClient = AthenaClient.builder()
                .region(Region.of(region))
                .build();
        this.s3OutputPath = s3OutputPath.endsWith("/") ? s3OutputPath : s3OutputPath + "/";
        this.database = database;
        this.tableName = tableName;
    }

    /**
     * 简单的变量替换方法，模拟 Python 的 Template.safe_substitute
     */
    private String resolveTemplate(String template, Map<String, Object> values) {
        String result = template;
        for (Map.Entry<String, Object> entry : values.entrySet()) {
            result = result.replace("${" + entry.getKey() + "}", String.valueOf(entry.getValue()));
        }
        return result;
    }

    /**
     * 初始化/更新 Athena 表
     */
    public void setupTable(String ddlTemplate, String s3LogPath) {
        int currentYear = java.time.Year.now().getValue();
        String yearRange = String.format("%d,%d", currentYear - 20, currentYear + 1);

        String sql = resolveTemplate(ddlTemplate, Map.of(
                "database", database,
                "table_name", tableName,
                "s3_log_path", s3LogPath,
                "year_range", yearRange));

        System.out.println("--- Updating Athena table for China Regions ---");
        executeAndVisibleWait(sql, 60);
    }

    /**
     * 执行查询并返回结果列表
     */
    public List<List<String>> queryEvents(String queryTemplate, String accessKeyId, String accountId,
            String region, String startUtc, String endUtc) {

        String finalEndUtc = (endUtc == null)
                ? Instant.now().atOffset(ZoneOffset.UTC).format(DateTimeFormatter.ISO_INSTANT)
                : endUtc;

        // 解析年份和月份用于分区裁剪
        Instant startTs = Instant.parse(startUtc);
        var dateTime = startTs.atOffset(ZoneOffset.UTC);

        String sql = resolveTemplate(queryTemplate, Map.of(
                "database", database,
                "table_name", tableName,
                "account_id", accountId,
                "region", region,
                "year", dateTime.getYear(),
                "month", String.format("%02d", dateTime.getMonthValue()),
                "access_key_id", accessKeyId,
                "start_utc", startUtc,
                "end_utc", finalEndUtc));

        System.out.printf("--- Executing search in %s from %s to %s ---%n", region, startUtc, finalEndUtc);
        String queryExecutionId = executeAndVisibleWait(sql, 300);
        return getFullResults(queryExecutionId);
    }

    private String executeAndVisibleWait(String query, int timeoutSeconds) {
        StartQueryExecutionRequest startRequest = StartQueryExecutionRequest.builder()
                .queryString(query)
                .queryExecutionContext(QueryExecutionContext.builder().database(database).build())
                .resultConfiguration(ResultConfiguration.builder()
                        .outputLocation(s3OutputPath)
                        .encryptionConfiguration(EncryptionConfiguration.builder()
                                .encryptionOption(EncryptionOption.SSE_S3)
                                .build())
                        .build())
                .build();

        String queryExecutionId = athenaClient.startQueryExecution(startRequest).queryExecutionId();

        long startTime = System.currentTimeMillis();
        while (System.currentTimeMillis() - startTime < timeoutSeconds * 1000L) {
            GetQueryExecutionResponse statusResp = athenaClient.getQueryExecution(
                    GetQueryExecutionRequest.builder().queryExecutionId(queryExecutionId).build());

            QueryExecutionStatus status = statusResp.queryExecution().status();
            QueryExecutionState state = status.state();

            if (state == QueryExecutionState.SUCCEEDED) {
                return queryExecutionId;
            } else if (state == QueryExecutionState.FAILED || state == QueryExecutionState.CANCELLED) {
                throw new RuntimeException("Athena query failed: " + status.stateChangeReason());
            }

            try {
                Thread.sleep(2000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }

        athenaClient.stopQueryExecution(StopQueryExecutionRequest.builder().queryExecutionId(queryExecutionId).build());
        throw new RuntimeException("Query timed out after " + timeoutSeconds + " seconds");
    }

    public record CloudTrailEvent(
        String eventTime,
        String eventName,
        String userArn,
        String sourceIpAddress,
        String errorCode
    ) {
        // 可以在内部添加一些辅助方法，比如转换为 Instant
        public Instant getInstant() {
            return Instant.parse(eventTime);
        }
    }

    private List<CloudTrailEvent> getFullResults(String queryExecutionId) {
        List<CloudTrailEvent> events = new ArrayList<>();

        // 使用分页器获取结果
        GetQueryResultsIterable responses = athenaClient.getQueryResultsPaginator(
                GetQueryResultsRequest.builder().queryExecutionId(queryExecutionId).build());

        boolean isFirstRow = true;

        for (GetQueryResultsResponse response : responses) {
            for (Row row : response.resultSet().rows()) {
                // 跳过 CSV 表头（Athena 查询结果的第一行通常是字段名）
                if (isFirstRow) {
                    isFirstRow = false;
                    continue;
                }

                List<String> columns = row.data().stream()
                        .map(Datum::varCharValue)
                        .map(val -> val == null ? "" : val)
                        .toList();

                // 根据 SQL 模板中的字段顺序进行映射:
                // SELECT eventTime, eventName, userIdentity.arn, sourceIPAddress, errorCode
                if (columns.size() >= 5) {
                    events.add(new CloudTrailEvent(
                            columns.get(0), // eventTime
                            columns.get(1), // eventName
                            columns.get(2), // userArn
                            columns.get(3), // sourceIpAddress
                            columns.get(4) // errorCode
                    ));
                }
            }
        }
        return events;
    }
}