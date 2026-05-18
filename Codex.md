# Zoolanding Data Dropper Lambda Codex Memory

## Current Decisions

- 2026-05-13 18:48 CT timezone closeout: keep the raw analytics body unchanged and keep the S3 key partition in UTC as `appName/YYYY/MM/DD/<timestampMs>-<shortRequestId>.json`. When a payload includes a valid IANA `timezone`, the Lambda computes viewer-local time with Python `zoneinfo` and exposes it in the response, logs, and S3 object metadata. If `timezone` is missing or invalid, accept the event with UTC-only time fields; do not infer local time from the Lambda region, IP, or incomplete headers.
- 2026-05-13 18:59 CT deployment closeout: `sam deploy` created or updated the `zoolanding-data-dropper` stack in `us-east-1`. The public API CloudFront distribution needed an explicit `/analytics` behavior pointed at the SAM API origin; after the CloudFront deployment completed, synthetic requests from both `https://test.zoolandingpage.com.mx` and `https://zoolandingpage.com.mx` returned `eventTime` and wrote S3 object metadata. Avoid committing raw distribution IDs, API IDs, account IDs, or temporary audit object keys in docs.
- 2026-05-13 19:14 CT ETL handoff decision: do not change Zoolandingpage just to repeat `timezone` on every analytics event. Future ETL should connect events by `sessionId`, choose a session timezone from the first valid IANA `timezone` in the session, and apply it to later events that omit timezone while preserving raw payloads and UTC partitions.

## Verification Commands

- `python -m unittest discover -s tests`
- `$env:DRY_RUN = "1"; python .\local_test.py`

## Security Notes

- Timezone is useful context but can still be sensitive. Do not add IP, precise geolocation, cookies, or other sensitive analytics enrichment without the configured consent flow and compliance review.
