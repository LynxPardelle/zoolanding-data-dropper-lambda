# Zoolanding Data Dropper Lambda

A minimal AWS Lambda that receives analytics JSON, validates it, and stores the original payload into S3 using a date-partitioned key.

- Runtime: Python 3.13 (or 3.11+). In AWS, `boto3` is available by default.
- Handler: `lambda_function.lambda_handler`
- Target bucket: `zoolanding-data-raw` (configurable via env var `RAW_BUCKET_NAME`)

## Where this fits in Zoolanding

This Lambda is the raw analytics sink for the Zoolanding frontend platform.

- The Angular app sends `POST` requests to `environment.apiUrl + /analytics`.
- The frontend service boundary lives in `../zoolandingpage/src/app/shared/services/analytics.service.ts`.
- The app-level analytics behavior and event model are documented in `../zoolandingpage/docs/05-analytics-tracking.md`.
- Platform architecture and the relationship between this Lambda and the config/runtime services are documented in `../zoolandingpage/docs/02-architecture.md`.
- Blog/content hub analytics events use this same generic endpoint when they include safe `contentHubId` and `articleId` values.

This repository documents the Lambda itself. The main frontend repo is the source of truth for cross-platform behavior.

## How it works

- Expects an API Gateway–like event with a JSON string in `event.body`.
- Validates that `appName` (string) and `timestamp` (number) exist.
- Normalizes `timestamp` to milliseconds, derives `YYYY/MM/DD` in UTC, and reports viewer-local time when the payload includes a valid IANA `timezone`.
- Uploads the ORIGINAL request body (unchanged) to:
  `appName/YYYY/MM/DD/<timestampMs>-<shortRequestId>.json`
- Adds S3 object metadata for `timestamp-ms` and `event-time-utc`; when `timezone` is valid, also adds `event-timezone`, `event-time-local`, `event-local-date`, and `event-local-hour`.
- Rejects blog analytics events that include obvious personal or credential fields.

Details and acceptance criteria are in `instructions.md`.
For future analytics processing, start with `docs/etl-starting-point.md`; it documents how to reconstruct timezone by `sessionId` during ETL without requiring every event to repeat `timezone`.

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

- Run the unit tests:

```powershell
python -m unittest discover -s tests
```

- To perform a real upload locally (requires configured AWS credentials), set your bucket name explicitly:

```powershell
$env:DRY_RUN = "0"
$env:RAW_BUCKET_NAME = "zoolanding-data-raw"
python .\local_test.py
```

## Deploy

For repeatable deployments from this repository:

```bash
sam deploy
```

The checked-in `samconfig.toml` includes `test` and `prod` deployment profiles in `us-east-1`.

- `test` writes to `zoolanding-data-raw-test`.
- `prod` writes to `zoolanding-data-raw`.

Pushes to `dev` run CI only and must not provision or deploy AWS resources. Protected promotions follow `feature -> dev -> test -> main`; promotion PRs into `test` or `main` must originate in this repository. Test and production build and test without OIDC, transfer the validated SAM build through a one-day same-run artifact with a SHA-256 manifest, verify both PR parents and the protected branch tip again, and only then request AWS credentials. The OIDC job uses pinned actions, does not check out or execute repository code, and deploys only the manifest-verified build.

The equivalent first non-interactive deployment command is:

```bash
sam deploy --stack-name zoolanding-data-dropper --region us-east-1 --capabilities CAPABILITY_IAM --resolve-s3 --no-confirm-changeset --no-fail-on-empty-changeset --parameter-overrides RawBucketName=zoolanding-data-raw LogLevel=INFO
```

This repo now includes a SAM template that exposes:

- `POST /analytics`
- CORS preflight for `POST,OPTIONS`
- output `ApiUrl` for the deployed endpoint

After `sam deploy`, make sure the shared API CloudFront front door routes `/analytics` to this SAM API origin with origin path `/Prod`. The frontend calls `https://api.zoolandingpage.com.mx/analytics`, not the raw `execute-api` output directly.

If you still need a manual console fallback:

- Runtime: Python 3.13 (or 3.11)
- Handler: `lambda_function.lambda_handler`
- Env vars (optional): `RAW_BUCKET_NAME`, `LOG_LEVEL`
- Role policy must include `s3:PutObject` on `arn:aws:s3:::<bucket>/*`

## Environment variables

- `RAW_BUCKET_NAME` (default: `zoolanding-data-raw`)
- `ENVIRONMENT_NAME`
- `LOG_LEVEL` = `DEBUG` | `INFO` | `ERROR` (default: `INFO`)
- `DRY_RUN` = `1` to skip actual S3 writes (handy for local dev; ignored in production)

## Blog analytics validation

Events are treated as blog events when `feature` is `blog`, `contentType` is a blog/article value, or `name` starts with `blog_`.

Blog events must include safe lowercase IDs:

```json
{
  "name": "blog_view",
  "feature": "blog",
  "contentHubId": "main",
  "articleId": "primer-post"
}
```

The same IDs may be sent inside the frontend analytics `meta` object when the app records component/runtime events:

```json
{
  "name": "blog_view",
  "feature": "blog",
  "meta": {
    "hubId": "main",
    "articleId": "primer-post"
  }
}
```

The Lambda recursively rejects blog analytics events that include obvious personal or credential fields or values such as `email`, `phone`, `password`, `token`, `authorization`, `commentBody`, `message`, `body`, email addresses, phone numbers, bearer tokens, AWS access key markers, or signed-url credential markers. Comments and forms should use a moderated feature endpoint, not raw analytics.

Successful responses do not include the raw bucket name or object key; storage details remain operational and server-side.

## Troubleshooting

- ImportError: boto3 could not be resolved
  - In AWS: safe to ignore during deployment.
  - Locally: `pip install boto3` or keep `DRY_RUN=1` to avoid S3 calls.
- 400 responses:
  - Ensure `event.body` is a valid JSON string and contains `appName` (string) and `timestamp` (number).
  - The parsed JSON body must be an object, not an array or scalar.
- S3 key doesn't match expectations:
  - Check that `timestamp` units are correct (seconds vs milliseconds). The function converts seconds to ms automatically.
- Local time is missing in the response or object metadata:
  - Ensure the payload includes a valid IANA timezone such as `America/Mexico_City`. The Lambda cannot infer a viewer's exact local time from a timestamp alone.

---

See `docs/developer_guide.md` for deeper implementation details and `docs/etl-starting-point.md` for future ETL guidance.
