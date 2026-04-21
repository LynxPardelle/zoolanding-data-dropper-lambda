---
name: risk-review
description: 'Repo-local findings-first review workflow for Zoolanding Lambda diffs, deploy candidates, and contract changes. Use when reviewing for bugs, regressions, rollout risk, weak validation, or missing tests.'
user-invocable: true
---

# Risk Review

This repo-local version is for review-only work. Lead with findings, not summaries.

## Review Targets

- local diffs or pull requests
- request or response contract changes
- storage, lifecycle, or payload behavior changes
- deploy-readiness and regression checks

## Output Contract

Each finding should include:

- severity
- concrete failure mode
- exact file or surface when available
- the smallest useful fix direction or missing test

If there are no findings, say that explicitly and note any residual testing gap.

## Review Workflow

1. Identify the intended change.
   - What behavior is meant to change?
   - What behavior must remain stable?

2. Inspect the highest-risk surfaces.
   - request and response validation
   - state transitions and persisted output
   - error handling and fallback behavior
   - env vars, IAM assumptions, and template wiring
   - tests, harness coverage, and docs drift

3. Challenge unproven assumptions.
   - Missing fields, malformed payloads, stale env vars, and partial deployments matter more than the happy path.

4. Prefer evidence.
   - Ground findings in code, tests, runtime output, or a concrete deploy-readiness gap.

5. Return findings in priority order.
   - bugs and release risks first
   - then fragile behavior or missing tests
   - then lower-value clarity issues only if they affect correctness

## Severity Guide

- `High`: likely broken behavior, data loss, or release blocker
- `Medium`: works in the happy path but is fragile or untested in an important case
- `Low`: clarity or maintainability issue with real defect risk
- `Question`: unresolved ambiguity that could hide a defect