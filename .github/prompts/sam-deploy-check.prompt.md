---
name: "SAM Deploy Check"
description: "Review this raw analytics Lambda for AWS SAM deploy readiness. Use when preparing to deploy changes that may affect POST /analytics, request validation, S3 key layout, env vars, IAM, or documentation in zoolanding-data-dropper-lambda."
argument-hint: "Changed files, diff, or deploy concern"
agent: "agent"
---

Review this repository for deploy readiness after the current change.

Follow [Zoolanding Lambda Workflow](../skills/zoolanding-lambda-workflow/SKILL.md) and inspect the contract files:

- [README](../../README.md)
- [Implementation Guide](../../instructions.md)
- [SAM Template](../../template.yaml)
- [SAM Config](../../samconfig.toml)

Use the user's arguments plus the current diff or changed files.

Check specifically for:

- handler and template wiring for `POST /analytics`
- drift in request validation or response shape
- S3 key contract changes and timestamp normalization behavior
- env var, IAM, or parameter-override mismatches
- docs drift between code, README, instructions, and SAM template

Return:

1. findings first, ordered by severity
2. the deploy command to use, or a note that plain `sam deploy` is sufficient
3. the smallest post-deploy smoke test
4. doc or config updates still required