import boto3

# Initialize the CloudWatch client
cloudwatch_client = boto3.client('cloudwatch')

# Define the alarm name
alarm_name = 'HighCPUUtilization'  # Replace with your actual alarm name

# Retrieve the existing alarm configuration
response = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])
alarm = response['MetricAlarms'][0]

# Extract the existing configuration
metric_name = alarm['MetricName']
namespace = alarm['Namespace']
statistic = alarm['Statistic']
period = alarm['Period']
threshold = alarm['Threshold']
comparison_operator = alarm['ComparisonOperator']
evaluation_periods = alarm['EvaluationPeriods']
dimensions = alarm['Dimensions']
alarm_actions = alarm.get('AlarmActions', [])
ok_actions = alarm.get('OKActions', [])

# Add the SNS topic ARN to the OK actions if not already present
sns_topic_arn = 'arn:aws:sns:us-west-2:123456789012:cloudwatch-pagerduty'  # Replace with your SNS topic ARN
if sns_topic_arn not in ok_actions:
    ok_actions.append(sns_topic_arn)

# Update the alarm with the new OK actions
cloudwatch_client.put_metric_alarm(
    AlarmName=alarm_name,
    MetricName=metric_name,
    Namespace=namespace,
    Statistic=statistic,
    Period=period,
    Threshold=threshold,
    ComparisonOperator=comparison_operator,
    EvaluationPeriods=evaluation_periods,
    AlarmActions=alarm_actions,
    OKActions=ok_actions,
    Dimensions=dimensions
)

print(f"Updated CloudWatch alarm: {alarm_name} with OK actions")