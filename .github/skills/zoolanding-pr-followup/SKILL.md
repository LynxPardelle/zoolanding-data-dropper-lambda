---
name: zoolanding-pr-followup
description: 'Repo-local GitHub PR follow-up workflow for Zoolanding repo work. Use when checking CI status, reviewer feedback, merge readiness, unresolved threads, or when preparing a safe response plan for an active PR.'
user-invocable: true
---

# Zoolanding PR Follow-Up

Use this repo-local skill for PR follow-up work tied to Zoolanding changes.

## When to Use

- current-branch PR checks
- reviewer feedback triage
- unresolved thread follow-up
- merge-readiness and update-branch checks
- planning a safe response before posting replies or pushing fixes

## Workflow

1. Inspect the PR state.
   - Identify the target PR, branch state, failing checks, reviewer requests, and unresolved threads.

2. Produce a dry-run diagnosis.
   - List blocking items first.
   - Map each reviewer point or failing check to a concrete fix direction.

3. Separate read work from write work.
   - Reading PR status, checks, and comments is safe.
   - Replying, resolving threads, pushing commits, or notifying reviewers requires explicit user approval.

4. Fix in priority order.
   - correctness and CI failures first
   - then review comments that materially affect behavior or mergeability

5. Re-verify before writing back.
   - Confirm the branch is in the expected state and the proposed reply text matches the implemented change.

## Tooling Guidance

- Pair this skill with `risk-review` for findings-first diff review.
- If installed, combine it with GitHub-focused global skills such as `gh-pr-check`, `gh-fix-pr`, or `gh-address-comments`.
- Do not post, resolve, or notify on a PR without an explicit dry-run summary and user approval.