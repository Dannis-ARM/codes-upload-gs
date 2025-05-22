import boto3

# Create CloudWatch client
cloudwatch = boto3.client('cloudwatch')

# CloudWatch Resource
cwres = boto3.resource('cloudwatch')

# Get Alarm Configuration
alarm = cwres.Alarm('My Alarm')

# Update alarm copying all attributes from local alarm variable
cloudwatch.put_metric_alarm(
    AlarmName=alarm.name,
    ComparisonOperator=alarm.comparison_operator,
    EvaluationPeriods=alarm.evaluation_periods,
    MetricName=alarm.metric_name,
    Namespace=alarm.namespace,
    Period=120,                    # changed attribute
    Statistic=alarm.statistic,
    Threshold=alarm.threshold,
    ActionsEnabled=alarm.actions_enabled,
    AlarmDescription=alarm.alarm_description,
    Dimensions=alarm.dimensions,
    Unit=alarm.unit
)