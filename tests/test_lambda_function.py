"""Local tests for the Lambda handler, using moto to fake DynamoDB (no AWS account needed).

Run from the repo root:
    pip install -r requirements-dev.txt
    pytest -v
"""
import importlib
import json
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda"))

TABLE = "coderco"


def load_event(name):
    return json.loads((ROOT / "events" / f"{name}.json").read_text())


@pytest.fixture
def fn(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", TABLE)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        module = importlib.reload(importlib.import_module("lambda_function"))
        yield module


def items():
    return boto3.resource("dynamodb").Table(TABLE).scan()["Items"]


def test_valid_submit_returns_201_and_stores_item(fn):
    response = fn.lambda_handler(load_event("submit-ok"), None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 201
    assert body["item"]["payload"] == {"name": "Mo", "module": "AWS"}
    assert {"id", "timestamp", "payload"} <= body["item"].keys()
    assert len(items()) == 1


def test_decimal_number_is_stored_and_returned_as_number(fn):
    response = fn.lambda_handler(load_event("submit-float"), None)

    assert response["statusCode"] == 201
    assert json.loads(response["body"])["item"]["payload"]["score"] == 9.5


@pytest.mark.parametrize(
    "event, message",
    [
        (load_event("submit-bad-json"), "Body must be valid JSON"),
        ({"body": None}, "Request body is required"),
        ({"body": "[1, 2]"}, "Body must be a non-empty JSON object"),
        ({"body": "{}"}, "Body must be a non-empty JSON object"),
    ],
)
def test_invalid_input_returns_400_and_stores_nothing(fn, event, message):
    response = fn.lambda_handler(event, None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == message
    assert items() == []


def test_dynamodb_failure_returns_500_with_cors_headers(fn):
    boto3.client("dynamodb").delete_table(TableName=TABLE)

    response = fn.lambda_handler(load_event("submit-ok"), None)

    assert response["statusCode"] == 500
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"


@pytest.mark.parametrize("event_name", ["submit-ok", "submit-bad-json"])
def test_every_response_is_a_valid_proxy_response(fn, event_name):
    response = fn.lambda_handler(load_event(event_name), None)

    assert set(response) == {"statusCode", "headers", "body"}
    assert isinstance(response["body"], str)
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
