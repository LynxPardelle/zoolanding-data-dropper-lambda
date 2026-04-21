---
name: zoolanding-lambda-workflow
description: 'Zoolanding Lambda workflow for the raw analytics sink. Use when changing request validation, S3 key layout, API responses, local harness behavior, or SAM deployment for zoolanding-data-dropper-lambda.'
user-invocable: true
---

# Zoolanding Lambda Workflow

Use this skill for work in the raw analytics Lambda.

## Repo Focus

- Validate and store the original analytics payload unchanged.
- Preserve the S3 key contract: `appName/YYYY/MM/DD/<timestampMs>-<requestId>.json`.
- Keep the frontend repo as the source of truth for cross-platform analytics behavior.

## Workflow

1. Read the contract first.
   - Start with `README.md` and `instructions.md` before editing behavior.

2. Keep the handler simple.
   - Validate `appName` and `timestamp` explicitly.
   - Normalize seconds vs milliseconds without mutating the stored request body.
   - Preserve the original payload bytes on write.

3. Keep changes surgical.
   - Avoid broad abstractions unless they directly simplify request parsing or S3 writes.
   - Do not change the response shape or key layout casually.

4. Verify locally.
   - Prefer `DRY_RUN=1` with `python .\\local_test.py` for handler checks.
   - Use a focused event that exercises timestamp normalization or validation edges.

5. Verify deployment assumptions.
   - If the change affects API shape, env vars, or IAM expectations, update `README.md` and `instructions.md` in the same diff.

## Recommended Repo-Local Skills

- Pair this workflow with the repo-local `karpathy-guidelines` skill for scoped implementation, `systematic-debugging` for root-cause analysis, `risk-review` for review-only asks, and `test-driven-development` for behavior-changing code.
- Use the repo-local `zoolanding-pr-followup` skill for CI, reviewer, and merge-readiness work.
- For shared workspace customization audits or consolidated cross-repo summaries, use the community prompts [Workspace AI Customization Audit](../../../../zoolandingpage/.github/prompts/workspace-ai-customization-audit.prompt.md) and [Workspace Change Summary](../../../../zoolandingpage/.github/prompts/workspace-change-summary.prompt.md).
- Use the repo-local `zoolanding-production-readiness` agent for deploy-gate review and the repo-local `zoolanding-config-platform-audit` agent when a change may require coordinated updates in the frontend or sibling services.
- Use the repo-local `sam-deploy-check` prompt before shipping contract or SAM changes.

## Resources

- [Validation Checklist](./references/validation-checklist.md)