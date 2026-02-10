import boto3
import time
from datetime import datetime, timezone
from string import Template
from dateutil import parser

class CloudTrailAthenaClient:
    def __init__(self, region, s3_log_path, s3_output_path, database='default', table_name='org_cloudtrail_china'):
        """
        :param region: AWS China region ('cn-north-1' or 'cn-northwest-1')
        :param s3_log_path: S3 root path (e.g., s3://my-bucket/AWSLogs/o-xxxxxx/)
        :param s3_output_path: S3 path for Athena query results
        """
        # Ensure you are using the correct region for the Boto3 client
        self.client = boto3.client('athena', region_name=region)
        self.s3_log_path = s3_log_path.rstrip('/') + '/'
        self.s3_output_path = s3_output_path.rstrip('/') + '/'
        self.database = database
        self.table_name = table_name

    def _load_sql_template(self, sql_content, mapping):
        """Substitute variables in the SQL template string"""
        template = Template(sql_content)
        return template.safe_substitute(mapping)

    def setup_table(self, ddl_template):
        """
        Update table with dynamic year range and China regions.
        """
        current_year = datetime.now(timezone.utc).year
        # Coverage: 20 years ago to next year
        year_range = f"{current_year - 20},{current_year + 1}"
        
        sql = self._load_sql_template(ddl_template, {
            'database': self.database,
            'table_name': self.table_name,
            's3_log_path': self.s3_log_path,
            'year_range': year_range
        })
        
        print(f"--- Updating Athena table for China Regions (Range: {year_range}) ---")
        return self._execute_wait(sql, timeout=60)

    def query_events(self, query_template, access_key_id, account_id, region, start_utc, end_utc=None, timeout=300):
        """
        Query CloudTrail events with auto end_utc (defaults to NOW).
        """
        if end_utc is None:
            end_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        dt_start = parser.isoparse(start_utc)
        
        sql = self._load_sql_template(query_template, {
            'database': self.database,
            'table_name': self.table_name,
            'account_id': account_id,
            'region': region,
            'year': dt_start.year,
            'month': f"{dt_start.month:02d}",
            'access_key_id': access_key_id,
            'start_utc': start_utc,
            'end_utc': end_utc
        })
        
        print(f"--- Executing search in {region} from {start_utc} to {end_utc} ---")
        execution_id = self._execute_wait(sql, timeout=timeout)
        return self._get_full_results(execution_id)
    
    def _execute_wait(self, query, timeout, kms_key=None):
        """
        Monitor Athena query status with encryption.
        :param kms_key: If provided, uses SSE_KMS. If None, uses SSE_S3.
        """
        start_perf = time.perf_counter()
        
        # Define encryption configuration
        encryption_config = {
            'EncryptionOption': 'SSE_KMS' if kms_key else 'SSE_S3'
        }
        if kms_key:
            encryption_config['KmsKey'] = kms_key

        response = self.client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={
                'OutputLocation': self.s3_output_path,
                'EncryptionConfiguration': encryption_config
            }
        )
        qid = response['QueryExecutionId']
        
        # ... (Polling logic remains the same) ...
        wait_time = 1
        while True:
            elapsed = time.perf_counter() - start_perf
            if elapsed > timeout:
                self.client.stop_query_execution(QueryExecutionId=qid)
                raise TimeoutError(f"Athena query {qid} timed out.")

            status_resp = self.client.get_query_execution(QueryExecutionId=qid)
            state = status_resp['QueryExecution']['Status']['State']
            
            if state == 'SUCCEEDED':
                print(f"Success! (Encrypted) Time: {time.perf_counter() - start_perf:.2f}s")
                return qid
            
            if state in ['FAILED', 'CANCELLED']:
                reason = status_resp['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Athena error ({state}): {reason}")
            
            time.sleep(min(wait_time, 10))
            wait_time *= 2

    def _get_full_results(self, qid):
        """Retrieve all results using pagination"""
        paginator = self.client.get_paginator('get_query_results')
        all_rows = []
        for page in paginator.paginate(QueryExecutionId=qid):
            for row in page['ResultSet']['Rows']:
                all_rows.append([val.get('VarCharValue', '') for val in row['Data']])
        return all_rows

# --- China-Specific SQL Templates ---

# Note the 'projection.region.values' updated for China
DDL_TEMPLATE = """
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
LOCATION '${s3_log_path}''
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
    'storage.location.template' = '${s3_log_path}${{account_id}}/CloudTrail/${{region}}/${{year}}/${{month}}/${{day}}/'
)
"""

QUERY_TEMPLATE = """
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
"""

# --- Main Logic ---

if __name__ == "__main__":
    # Example: Beijing region
    CHINA_REGION = 'cn-north-1' 
    # Replace with your actual China S3 paths
    S3_LOGS = "s3://your-china-bucket/AWSLogs/o-xxxxxxxxx/"
    S3_TEMP = "s3://your-china-bucket/athena-results/"

    scanner = CloudTrailAthenaClient(
        region=CHINA_REGION,
        s3_log_path=S3_LOGS,
        s3_output_path=S3_TEMP
    )

    try:
        # Step 1: Initialize/Update table with China region configs
        scanner.setup_table(DDL_TEMPLATE)

        # Step 2: Search events in China region
        events = scanner.query_events(
            query_template=QUERY_TEMPLATE,
            access_key_id='AKIAXXXXXXXXXXXXXXXX', # Your China Access Key
            account_id='123456789012',           # Your China Account ID
            region='cn-north-1',                 # Specific region to scan
            start_utc='2026-02-01T00:00:00Z'
        )

        print(f"\nTotal events found: {len(events)-1}")
        for row in events[:6]:
            print(row)

    except Exception as e:
        print(f"Error: {e}")