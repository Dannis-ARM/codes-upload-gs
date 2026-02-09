import boto3
import time
from datetime import datetime, timezone
from string import Template
from dateutil import parser

class CloudTrailAthenaClient:
    def __init__(self, region, s3_log_path, s3_output_path, database='default', table_name='org_cloudtrail_optimized'):
        """
        :param region: AWS region (e.g., 'us-east-1')
        :param s3_log_path: Root S3 path for logs (up to o-xxxxxx level)
        :param s3_output_path: S3 path to store Athena query results
        """
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
        """Execute DDL to ensure the Athena table exists with Partition Projection"""
        sql = self._load_sql_template(ddl_template, {
            'database': self.database,
            'table_name': self.table_name,
            's3_log_path': self.s3_log_path
        })
        print(f"--- Ensuring Athena table exists: {self.table_name} ---")
        return self._execute_wait(sql, timeout=60)

    def query_events(self, query_template, access_key_id, account_id, region, start_utc, end_utc=None, timeout=300):
        """
        Execute business query for specific Access Key within a UTC time range.
        :param start_utc: Start time string (e.g., '2026-02-01T00:00:00Z')
        :param end_utc: End time string. Defaults to current UTC time if None.
        :param timeout: Maximum wait time in seconds.
        """
        # Default to current UTC time if end_utc is not provided
        if end_utc is None:
            end_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Parse start_utc to extract partition keys (year, month) for performance
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
        
        print(f"--- Querying range: {start_utc} to {end_utc} ---")
        execution_id = self._execute_wait(sql, timeout=timeout)
        return self._get_full_results(execution_id)

    def _execute_wait(self, query, timeout):
        """Poll Athena query status, handle timeout, and report performance"""
        start_perf = time.perf_counter()
        response = self.client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.s3_output_path}
        )
        qid = response['QueryExecutionId']
        
        wait_time = 1
        while True:
            elapsed = time.perf_counter() - start_perf
            if elapsed > timeout:
                # Stop the query on AWS side to save costs if Python times out
                self.client.stop_query_execution(QueryExecutionId=qid)
                raise TimeoutError(f"Athena query {qid} timed out after {timeout}s.")

            status_resp = self.client.get_query_execution(QueryExecutionId=qid)
            state = status_resp['QueryExecution']['Status']['State']
            
            if state == 'SUCCEEDED':
                stats = status_resp['QueryExecution']['Statistics']
                print(f"Query Succeeded! Time: {time.perf_counter() - start_perf:.2f}s")
                print(f"Data Scanned: {stats.get('DataScannedInBytes', 0) / 1024**2:.2f} MB")
                return qid
            
            if state in ['FAILED', 'CANCELLED']:
                reason = status_resp['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Athena query {state}: {reason}")
            
            # Exponential backoff for polling
            time.sleep(min(wait_time, 10))
            wait_time *= 2

    def _get_full_results(self, qid):
        """Fetch all rows from Athena using paginator to bypass the 1000-row limit"""
        paginator = self.client.get_paginator('get_query_results')
        all_rows = []
        for page in paginator.paginate(QueryExecutionId=qid):
            for row in page['ResultSet']['Rows']:
                all_rows.append([val.get('VarCharValue', '') for val in row['Data']])
        return all_rows

# --- SQL Templates ---

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
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION '${s3_log_path}'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.account_id.type' = 'injected',
    'projection.region.type' = 'enum',
    'projection.region.values' = 'cn-north-1,cn-northwest-1',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2027',
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

# --- Execution Example ---

if __name__ == "__main__":
    REGION = 'cn-north-1'

    # Initialize client
    scanner = CloudTrailAthenaClient(
        region=REGION,
        s3_log_path="s3://your-log-bucket/AWSLogs/o-xxxxxxxxx/",
        s3_output_path="s3://your-result-bucket/athena-outputs/"
    )

    try:
        # Step 1: Initialize table structure (Run once)
        scanner.setup_table(DDL_TEMPLATE)

        # Step 2: Query events from specific start time to NOW (default)
        events = scanner.query_events(
            query_template=QUERY_TEMPLATE,
            access_key_id='AKIAXXXXXXXXXXXXXXXX',
            account_id='123456789012',
            region=REGION,
            start_utc='2026-02-09T00:00:00Z'  # From today 00:00 UTC until now
        )

        # Step 3: Print summary
        if len(events) > 1:
            print(f"\nRetrieved {len(events)-1} events.")
            for row in events[:5]: # Print header + first 4 results
                print(row)
        else:
            print("\nNo events found.")

    except Exception as e:
        print(f"\nExecution failed: {e}")