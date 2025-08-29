"""
Local test harness for lambda_function.lambda_handler.
- DRY_RUN=1 by default to avoid S3 writes.
- Adjust the sample event as needed.
"""
import os
import json

# Ensure dry-run by default to avoid S3 calls and allow missing boto3 locally
os.environ.setdefault("DRY_RUN", "1")

from lambda_function import lambda_handler

class Ctx:
    aws_request_id = "12345678-aaaa-bbbb-cccc-1234567890ab"

sample_payload = {
    "appName": "zoo_landing_page",
    "timestamp": 1756276595877,
    "name": "cta_click",
}

sample_event = {
    "isBase64Encoded": False,
    "body": json.dumps(sample_payload),
}

if __name__ == "__main__":
    resp = lambda_handler(sample_event, Ctx())
    print(json.dumps(resp, indent=2))
