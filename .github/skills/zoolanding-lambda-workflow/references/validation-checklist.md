# Validation Checklist

## Contract

- `event.body` must exist and parse as JSON.
- `appName` must be a non-empty string.
- `timestamp` must be numeric and normalized only for key derivation.
- Stored S3 object body must match the original request body string.

## Local Verification

- Use `DRY_RUN=1` with `python .\\local_test.py` for safe local checks.
- Exercise both seconds and milliseconds timestamps.
- Verify 400 responses remain clear for invalid body, appName, or timestamp.

## Change Discipline

- Do not move cross-platform analytics docs into this repo.
- Update `README.md` and `instructions.md` when the Lambda contract changes.
