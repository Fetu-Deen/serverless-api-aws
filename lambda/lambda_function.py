import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]
table = boto3.resource("dynamodb").Table(TABLE_NAME)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST",
}


def _to_json(value):
    # DynamoDB needs Decimal instead of float; turn it back into a number for the response.
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Type {type(value).__name__} is not JSON serializable")


def respond(status_code, body):
    # Proxy integration: Lambda owns the whole HTTP response, CORS headers included.
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=_to_json),
    }


def parse_payload(event):
    raw_body = event.get("body")
    if not raw_body:
        raise ValueError("Request body is required")

    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    try:
        payload = json.loads(raw_body, parse_float=Decimal)
    except json.JSONDecodeError:
        raise ValueError("Body must be valid JSON")

    if not isinstance(payload, dict) or not payload:
        raise ValueError("Body must be a non-empty JSON object")

    return payload


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "local")
    logger.info("request_id=%s method=%s path=%s", request_id, event.get("httpMethod"), event.get("path"))

    try:
        payload = parse_payload(event)
    except ValueError as err:
        logger.warning("request_id=%s rejected: %s", request_id, err)
        return respond(400, {"error": str(err), "requestId": request_id})

    item = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }

    try:
        table.put_item(Item=item)
    except ClientError as err:
        code = err.response["Error"]["Code"]
        logger.error("request_id=%s dynamodb_error=%s", request_id, code)
        return respond(500, {"error": "Could not save the item", "requestId": request_id})
    except Exception:
        # Anything unexpected still returns JSON with CORS headers instead of a bare 502.
        logger.exception("request_id=%s unexpected error", request_id)
        return respond(500, {"error": "Internal error", "requestId": request_id})

    logger.info("request_id=%s stored id=%s", request_id, item["id"])
    return respond(201, {"message": "Stored", "item": item})
