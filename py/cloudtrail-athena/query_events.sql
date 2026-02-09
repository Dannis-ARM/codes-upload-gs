SELECT 
    eventTime, 
    eventName, 
    userIdentity.arn as user_arn, 
    sourceIPAddress, 
    errorCode
FROM ${database}.${table_name}
WHERE account_id = '${account_id}'
AND region = '${region}'
AND year = '${year}'
AND month = '${month}'
AND userIdentity.accessKeyId = '${access_key_id}'
AND eventTime >= '${start_utc}'
AND eventTime <= '${end_utc}'
ORDER BY eventTime ASC