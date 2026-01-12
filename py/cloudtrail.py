import boto3
from datetime import datetime

def lookup_events_by_exact_time():
    client = boto3.client('cloudtrail')

    # 定义精确的开始时间：2026年1月11日 22点30分00秒 (UTC)
    # 注意：建议使用 UTC 时间，因为 AWS 后端是以 UTC 存储的
    start_time = datetime(2026, 1, 11, 22, 30, 0) 
    
    # 如果你想查询从 15 分钟前开始
    # from datetime import timedelta
    # start_time = datetime.utcnow() - timedelta(minutes=15)

    response = client.lookup_events(
        LookupAttributes=[
            {
                'AttributeKey': 'AccessKeyId',
                'AttributeValue': '你的AccessKeyID'
            }
        ],
        StartTime=start_time,
        MaxResults=10 # 每次返回的结果数
    )

    for event in response.get('Events', []):
        print(f"Time: {event['EventTime']}, Event: {event['EventName']}")

lookup_events_by_exact_time()