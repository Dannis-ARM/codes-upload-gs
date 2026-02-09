CREATE EXTERNAL TABLE IF NOT EXISTS ${database}.${table_name} (
    eventVersion STRING,
    userIdentity STRUCT<
        type: STRING,
        principalId: STRING,
        arn: STRING,
        accountId: STRING,
        accessKeyId: STRING,
        userName: STRING
    >,
    eventTime STRING,
    eventName STRING,
    awsRegion STRING,
    sourceIPAddress STRING,
    errorCode STRING,
    errorMessage STRING
)
PARTITIONED BY (account_id string, region string, year string, month string, day string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION '${s3_log_path}'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.account_id.type' = 'injected',
    'projection.region.type' = 'enum',
    'projection.region.values' = 'us-east-1,us-west-2,ap-northeast-1',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2023,2027',
    'projection.month.type' = 'integer',
    'projection.month.range' = '01,12',
    'projection.month.digits' = '2',
    'projection.day.type' = 'integer',
    'projection.day.range' = '01,31',
    'projection.day.digits' = '2',
    'storage.location.template' = '${s3_log_path}${{account_id}}/CloudTrail/${{region}}/${{year}}/${{month}}/${{day}}/'
)