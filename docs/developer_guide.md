# Developer Guide

This guide gives new developers all the context to work on the Zoolanding Data Dropper Lambda.

## Architecture

- Stateless Lambda function triggered by API Gateway (or compatible invoker) that forwards analytics payloads.
- Stores the original request body unmodified into S3 with a partitioned key for downstream analytics.

## Data Contract

Event (API Gateway proxy-like):

- `body`: JSON string with fields:
  - `appName` (string)
  - `timestamp` (number) – epoch seconds or milliseconds
- `isBase64Encoded` (bool) – if true, `body` is base64-encoded.
- `headers` – not required by the function.

Payload example is in `instructions.md`.

### Timestamp normalization

- If `timestamp >= 10^12`, treat as milliseconds.
- Else, treat as seconds and multiply by 1000.

### S3 key format

```text
<appName>/<YYYY>/<MM>/<DD>/<timestampMs>-<shortRequestId>.json
```
Where `shortRequestId` is the last 8 chars of `context.aws_request_id`.

## Code Walkthrough

`lambda_function.py`:

- `_decode_body` – reads `event.body`, handles base64, and returns a UTF-8 string.
- `_normalize_timestamp_to_ms` – validates and converts timestamp to milliseconds.
- `_derive_date_parts` – builds `YYYY`, `MM`, `DD` from timestamp in UTC.
- `_get_request_id` – extracts an 8-char id from the AWS request id for filenames.
- `_log` – structured JSON logging with `level`, `message`, and extra fields.
- `lambda_handler` – orchestrates validation, key building, and S3 upload.

## Local Development

Use the simple harness `local_test.py` to simulate an invocation.

- Dry-run mode skips actual S3 writes:

```powershell
$env:DRY_RUN = "1"
python .\local_test.py
```

- Real upload (requires AWS credentials):

```powershell
$env:DRY_RUN = "0"
$env:RAW_BUCKET_NAME = "zoolanding-data-raw"
python .\local_test.py
```

Notes:

- Install `boto3` locally if you want to hit S3 during development: `pip install boto3`.
- In AWS, `boto3` is provided by the runtime, so you don't need to package it.


## Testing Scenarios

- Happy path – valid `appName` and `timestamp` (ms): expect 200 and a key under `<appName>/YYYY/MM/DD`.
- Seconds timestamp – e.g., `1724832000`: expect conversion to `1724832000000` and proper key.
- Missing body – expect 400.
- Invalid JSON body – expect 400.
- Missing appName – expect 400.
- Missing/invalid timestamp – expect 400.
- Base64-encoded body – set `isBase64Encoded = true` and ensure decoding works.

## Logging

Logs are JSON-structured and include fields like `requestId`, `appName`, `timestampMs`, `bucket`, `key`, and `size` on success.

You can change verbosity with `LOG_LEVEL` env var: `DEBUG`, `INFO`, `ERROR`.

## Deployment

- Zip the repository (only Python files needed) and upload to Lambda, or deploy via SAM/Serverless/Terraform.
- Ensure the execution role has `s3:PutObject` on your destination bucket.
- Configure environment variables as needed.

## Extensibility Ideas

- Idempotency: use a client-provided `idempotencyKey` in the filename.
- Compression: accept gzipped bodies and set `ContentEncoding` accordingly.
- Metadata: add useful S3 object metadata for downstream services.
