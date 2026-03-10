import logging

import boto3

logger = logging.getLogger()

_sns = boto3.client("sns")


def publish(topic_arn: str, message: str, subject: str = "News Alert") -> None:
    _sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject=subject[:100],  # SNS subject max is 100 chars
    )
    logger.info(f"Notification published to {topic_arn}")
