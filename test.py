def filter_events_by_access_key_id(access_key_id, days_ago=7):
    """
    根据 Access Key ID 调用 CloudTrail lookup_events() 并进行过滤。
    """
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days_ago)

    filtered_events = []
    
    # 使用 Paginator 处理可能超出 MaxResults (默认50) 的大量结果
    paginator = client.get_paginator('lookup_events')
    
    # AccessKeyId 属性对应 AccessKeyId
    pages = paginator.paginate(
        LookupAttributes=[
            {
                'AttributeKey': 'AccessKeyId',
                'AttributeValue': access_key_id 
            },
        ],
        StartTime=start_time,
        EndTime=end_time
    )

    print(f"--- 正在搜索 Access Key ID: {access_key_id} 的事件 (从 {start_time.strftime('%Y-%m-%d')} 开始) ---")

    for page in pages:
        for event in page.get('Events', []):
            # 获取事件的完整 JSON 字符串并解析
            cloudtrail_event_json = event.get('CloudTrailEvent')
            if cloudtrail_event_json:
                try:
                    event_detail = json.loads(cloudtrail_event_json)
                    
                    # 检查 Assume Role Name (二次过滤)
                    user_identity = event_detail.get('userIdentity', {})
                    session_name = user_identity.get('sessionContext', {}).get('sessionIssuer', {}).get('userName')

                    # 假设 Assumed Role Name 的格式为 'RoleName/SessionName'
                    # 你需要根据实际的 Assumed Role Name 格式进行调整
                    if session_name:
                        print(f"事件时间: {event.get('EventTime')}, 事件名称: {event.get('EventName')}, Session Name: {session_name}")
                        filtered_events.append(event_detail)

                except json.JSONDecodeError as e:
                    print(f"解析 CloudTrailEvent JSON 失败: {e}")

    return filtered_events

# --- 示例调用 ---
# 替换为你要查询的实际临时 Access Key ID
TARGET_ACCESS_KEY_ID = 'ASIA...' 

# 假设你知道目标临时 Access Key ID
# events = filter_events_by_access_key_id(TARGET_ACCESS_KEY_ID, days_ago=3)
# print(f"\n找到符合条件的事件总数: {len(events)}")