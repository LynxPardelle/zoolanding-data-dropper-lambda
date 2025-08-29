# Zoolanding Data Dropper Lambda

A minimal AWS Lambda that receives analytics JSON, validates it, and stores the original payload into S3 using a date-partitioned key.

- Runtime: Python 3.13 (or 3.11+). In AWS, `boto3` is available by default.
- Handler: `lambda_function.lambda_handler`
- Target bucket: `zoolanding-data-raw` (configurable via env var `RAW_BUCKET_NAME`)

## How it works

- Expects an API Gateway–like event with a JSON string in `event.body`.
- Validates that `appName` (string) and `timestamp` (number) exist.
- Normalizes `timestamp` to milliseconds, derives `YYYY/MM/DD` in UTC.
- Uploads the ORIGINAL request body (unchanged) to:
  `appName/YYYY/MM/DD/<timestampMs>-<shortRequestId>.json`

Details and acceptance criteria are in `instructions.md`.

## Quick start (local)

- Optional: install boto3 locally if you want to actually hit S3.

```powershell
# Optionally create a venv
python -m venv .venv
. .venv/Scripts/Activate.ps1

# Optional: install boto3 for local S3 testing
pip install boto3
```

- Run the local harness with a sample event. By default, uploads are disabled via `DRY_RUN=1`.

```powershell
$env:DRY_RUN = "1"
python .\local_test.py
```

- To perform a real upload locally (requires configured AWS credentials), set your bucket name explicitly:

```powershell
$env:DRY_RUN = "0"
$env:RAW_BUCKET_NAME = "zoolanding-data-raw"
python .\local_test.py
```

## Deploy

- Zip and upload (no external deps needed), or use your preferred IaC (SAM/Serverless/Terraform).
- AWS console settings:
  - Runtime: Python 3.13 (or 3.11)
  - Handler: `lambda_function.lambda_handler`
  - Env vars (optional): `RAW_BUCKET_NAME`, `LOG_LEVEL`
  - Role policy must include `s3:PutObject` on `arn:aws:s3:::<bucket>/*`

## Environment variables

- `RAW_BUCKET_NAME` (default: `zoolanding-data-raw`)
- `LOG_LEVEL` = `DEBUG` | `INFO` | `ERROR` (default: `INFO`)
- `DRY_RUN` = `1` to skip actual S3 writes (handy for local dev; ignored in production)

## Troubleshooting

- ImportError: boto3 could not be resolved
  - In AWS: safe to ignore during deployment.
  - Locally: `pip install boto3` or keep `DRY_RUN=1` to avoid S3 calls.
- 400 responses:
  - Ensure `event.body` is a valid JSON string and contains `appName` (string) and `timestamp` (number).
- S3 key doesn't match expectations:
  - Check that `timestamp` units are correct (seconds vs milliseconds). The function converts seconds to ms automatically.

---

See `docs/developer_guide.md` for deeper details.
