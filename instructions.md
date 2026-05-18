# Zoolanding Data Dropper Lambda — Implementation Guide

This document is the full specification and build guide for a simple Lambda function that receives analytics JSON, validates it, and stores the original payload into S3 in a date-partitioned path.

## Overview

- Language/runtime: Python 3.13 (no external dependencies; `boto3` is available in AWS runtime)
- Trigger: API Gateway (HTTP/REST) or any invoker providing an API Gateway–like `event`
- Target bucket: `zoolanding-data-raw` (already provisioned with correct IAM policies)
- Behavior: Parse request body, validate required fields, derive S3 key as `appName/YYYY/MM/DD/<filename>.json`, and upload the raw JSON payload unchanged.

## Data Contract

Incoming event is expected to follow API Gateway proxy integration shape:

- `event.body`: stringified JSON payload (may be base64-encoded when `event.isBase64Encoded` is true)
- `event.headers` (optional): not required for core logic
- `context.aws_request_id` (from Lambda context): used for logging and default filename uniqueness

Payload (JSON) must contain:

- `appName` (string): application identifier; used as the top-level S3 prefix
- `timestamp` (number): Unix epoch time of the event
  - Unit handling: If `timestamp >= 10^12`, treat as milliseconds; otherwise treat as seconds
- `timezone` (string, optional): IANA timezone name from the viewer environment, for example `America/Mexico_City`
- Any other fields: preserved and stored as-is; no schema enforced

Example payload:

```json
{
  "battery": "{\"charging\":true,\"level\":1,\"chargingTime\":0,\"dischargingTime\":null}",
  "category": "cta",
  "colorDepth": 24,
  "connection": null,
  "cookies": "",
  "cookiesEnabled": true,
  "doNotTrack": null,
  "geolocationAccuracy": 999,
  "geolocationLatitude": -999.9999999999999999,
  "geolocationLongitude": -999.9999999999999999,
  "ip": "127.0.0.1",
  "label": "hero:primary",
  "language": "es",
  "localId": "361cf121-1022-4a7b-872a-c199dab792f8",
  "meta": {
    "location": "hero",
    "variant": "primary"
  },
  "name": "cta_click",
  "platform": "Win32",
  "screenHeight": 2160,
  "screenWidth": 3840,
  "sessionId": "1d2707fe-2439-40a2-b996-d98ae2e3579a",
  "timestamp": 1756276595877,
  "timezone": "America/Mexico_City",
  "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
  "vendor": "Google Inc.",
  "appName": "zoo_landing_page"
}
```

## S3 Object Layout

- Bucket: `zoolanding-data-raw` (configurable via env var `RAW_BUCKET_NAME`)
- Key prefix: `appName/YYYY/MM/DD/`
  - `YYYY`, `MM`, `DD` derived from `timestamp` in UTC
- Filename: `<timestampMs>-<shortRequestId>.json`
  - `timestampMs` is the timestamp normalized to milliseconds
  - `shortRequestId` is the last 8 chars of `context.aws_request_id` (or a random 8-char hex if context missing)
- Full example key: `zoo_landing_page/2024/09/01/1725148800000-1a2b3c4d.json`
- User metadata:
  - Always: `timestamp-ms`, `event-time-utc`
  - When `timezone` is a valid IANA name: `event-timezone`, `event-time-local`, `event-local-date`, `event-local-hour`

Rationale: The prefix scheme enables efficient partitioned queries downstream and avoids overwrites while staying human-readable.
The UTC key stays stable for partitioning. Local viewer time is metadata because the stored payload remains the original request body.

## Validation Rules

Reject the request with HTTP 400 if any is true:

- `event.body` is missing or empty
- JSON parse fails (invalid JSON)
- Parsed JSON body is not an object
- `appName` missing or not a non-empty string
- `timestamp` missing or not a finite number

Edge handling:

- Convert seconds to milliseconds if `timestamp < 10^12` (heuristic)
- Clamp absurdly old/new timestamps only for folder derivation; still store as given (do not mutate payload)
- If `timezone` is absent or invalid, keep the event and report only UTC-derived time fields. The Lambda cannot infer the viewer's exact local timezone without a client-provided timezone.

## Response Contract

- Success (200):

  ```json
  {
    "ok": true,
    "bucket": "zoolanding-data-raw",
    "key": "<final-s3-key>",
    "size": <bytesUploaded>,
    "eventTime": {
      "timestampMs": 1756272600000,
      "utc": "2025-08-27T05:30:00Z",
      "timezone": "America/Mexico_City",
      "local": "2025-08-26T23:30:00-06:00",
      "localDate": "2025-08-26",
      "localHour": "23"
    }
  }
  ```

- Client error (400):

  ```json
  { "ok": false, "error": "<message>" }
  ```

- Server error (500):

  ```json
  { "ok": false, "error": "Internal error" }
  ```

## IAM Requirements

Lambda execution role must allow:

- `s3:PutObject` on `arn:aws:s3:::zoolanding-data-raw/*`
- If bucket enforces KMS encryption: `kms:Encrypt`, `kms:GenerateDataKey` for the bucket’s CMK

No other AWS services required.

## Configuration

- Env vars:
  - `RAW_BUCKET_NAME` (optional): defaults to `zoolanding-data-raw`
  - `LOG_LEVEL` (optional): `INFO` (default), `DEBUG`, or `ERROR`
- Timeout: 10 seconds is plenty
- Memory: 128–256 MB

## Logging

Use JSON-structured logs to CloudWatch with at least:

- `level`, `message`, `requestId`, `appName`, `timestampMs`, `s3Key` (on success), and error details on failure

## Pseudocode

```text
def lambda_handler(event, context):
    request_id = (context.aws_request_id[:8] if context and getattr(context, 'aws_request_id', None) else random_hex(8))
    raw_bucket = os.getenv('RAW_BUCKET_NAME', 'zoolanding-data-raw')

    # 1) Get body (handle base64)
    body_str = event.get('body')
    if not body_str:
        return http_400('Missing body')
    if event.get('isBase64Encoded'):
        body_str = base64.b64decode(body_str).decode('utf-8')

    # 2) Parse JSON
    try:
        payload = json.loads(body_str)
    except Exception:
        return http_400('Body is not valid JSON')

    # 3) Validate fields
    app_name = payload.get('appName')
    ts = payload.get('timestamp')
    if not isinstance(app_name, str) or not app_name.strip():
        return http_400('Missing or invalid appName')
    if not isinstance(ts, (int, float)) or not math.isfinite(ts):
        return http_400('Missing or invalid timestamp')

    # 4) Normalize timestamp to ms, derive UTC date parts, and optional local time metadata
    ts_ms = int(ts if ts >= 10**12 else ts * 1000)
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    yyyy, mm, dd = dt.strftime('%Y'), dt.strftime('%m'), dt.strftime('%d')
    event_time = event_time_from_payload(ts_ms, payload)

    # 5) Build S3 key and upload original string body
    key = f"{app_name}/{yyyy}/{mm}/{dd}/{ts_ms}-{request_id}.json"
    s3.put_object(
        Bucket=raw_bucket,
        Key=key,
        Body=body_str.encode('utf-8'),
        ContentType='application/json',
        Metadata=event_time.to_s3_metadata(),
    )

  return http_200({
      'ok': True,
      'bucket': raw_bucket,
      'key': key,
      'size': len(body_str.encode('utf-8')),
      'eventTime': event_time.to_response(),
  })
```

## Example API Gateway Test Event

```json
{
  "resource": "/",
  "path": "/analytics",
  "httpMethod": "POST",
  "headers": {
    "Content-Type": "application/json"
  },
  "isBase64Encoded": false,
  "body": "{\n  \"appName\": \"zoolanding-web\",\n  \"timestamp\": 1724832000000,\n  \"analytics\": {\n    \"event\": \"page_view\",\n    \"path\": \"/\"\n  }\n}"
}
```

## Local Smoke Test (without AWS)

You can invoke the handler locally to validate parsing and key creation. This won’t reach S3 unless you have AWS creds and network.

Python snippet:

```python
from lambda_function import lambda_handler

event = {
  "isBase64Encoded": False,
  "body": "{\"appName\":\"zoolanding-web\",\"timestamp\":1724832000000,\"foo\":\"bar\"}"
}

class Ctx: aws_request_id = "12345678-aaaa-bbbb-cccc-1234567890ab"

print(lambda_handler(event, Ctx()))
```

## Deployment Notes

- Zip upload or IaC (SAM/Serverless/Terraform); no third-party libs needed
- Runtime: Python 3.13
- Handler: `lambda_function.lambda_handler`
- Env var (optional): set `RAW_BUCKET_NAME=zoolanding-data-raw` to be explicit

## Acceptance Criteria (Definition of Done)

- [ ] Valid requests return 200 with `{ ok: true, bucket, key, size }`
- [ ] Invalid requests return 400 with a clear error message
- [ ] S3 key layout is exactly `appName/YYYY/MM/DD/<timestampMs>-<shortRequestId>.json`
- [ ] Stored object body matches the original request body string byte-for-byte
- [ ] Valid IANA `timezone` values produce viewer-local time in the response and S3 object metadata without changing the raw body
- [ ] Logs include requestId, appName, timestampMs, and s3Key on success
- [ ] No external dependencies beyond AWS SDK included in runtime

## Nice-to-haves (Optional)

- Idempotency: allow client to pass `idempotencyKey` to use in filename to prevent duplicates
- Compression: set `ContentEncoding: gzip` if client sends gzipped body and `isBase64Encoded=true`
- Additional metadata: add S3 object metadata such as `x-amz-meta-app-name`, `x-amz-meta-timestamp-ms`

---

Implement the function in `lambda_function.py` according to this guide. If anything is unclear, prefer explicit validation and returning 400 rather than guessing.
