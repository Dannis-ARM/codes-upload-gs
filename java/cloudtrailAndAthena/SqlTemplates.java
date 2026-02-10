public class SqlTemplates {
    public static final String DDL = """
        CREATE EXTERNAL TABLE IF NOT EXISTS ${database}.${table_name} (
            eventVersion STRING,
            userIdentity STRUCT<
                type: STRING, principalId: STRING, arn: STRING,
                accountId: STRING, accessKeyId: STRING, userName: STRING
            >,
            eventTime STRING,
            eventName STRING,
            eventSource STRING,
            awsRegion STRING,
            sourceIPAddress STRING,
            errorCode STRING,
            errorMessage STRING
        )
        PARTITIONED BY (account_id string, region string, year string, month string, day string)
        ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.CloudTrailSerDe'
        STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
        OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
        LOCATION '${s3_log_path}'
        TBLPROPERTIES (
            'projection.enabled' = 'true',
            'projection.account_id.type' = 'injected',
            'projection.region.type' = 'enum',
            'projection.region.values' = 'cn-north-1,cn-northwest-1',
            'projection.year.type' = 'integer',
            'projection.year.range' = '${year_range}',
            'projection.month.type' = 'integer',
            'projection.month.range' = '01,12',
            'projection.month.digits' = '2',
            'projection.day.type' = 'integer',
            'projection.day.range' = '01,31',
            'projection.day.digits' = '2',
            'storage.location.template' = '${s3_log_path}${account_id}/CloudTrail/${region}/${year}/${month}/${day}/'
        )
        """;

    public static final String QUERY = """
        SELECT eventTime, eventName, userIdentity.arn, sourceIPAddress, errorCode
        FROM ${database}.${table_name}
        WHERE account_id = '${account_id}'
        AND region = '${region}'
        AND year = '${year}'
        AND month = '${month}'
        AND userIdentity.accessKeyId = '${access_key_id}'
        AND eventTime >= '${start_utc}'
        AND eventTime <= '${end_utc}'
        ORDER BY eventTime ASC
        """;
}