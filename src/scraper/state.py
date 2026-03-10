import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

_ssm = boto3.client("ssm")


def get_last_hash(key: str) -> str | None:
    try:
        resp = _ssm.get_parameter(Name=key)
        return resp["Parameter"]["Value"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return None
        raise


def put_last_hash(key: str, content_hash: str) -> None:
    _ssm.put_parameter(
        Name=key,
        Value=content_hash,
        Type="String",
        Overwrite=True,
    )
    logger.info(f"State updated for {key}")
