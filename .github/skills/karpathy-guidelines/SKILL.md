---
name: karpathy-guidelines
description: 'Repo-local execution discipline for Zoolanding Lambda tasks. Use when implementing, debugging, refactoring, reviewing, or planning Python handler, helper, SAM template, or local harness changes in this repository.'
user-invocable: true
---

# Karpathy Guidelines

Use this repo-local version to keep disciplined execution portable across clones of this Zoolanding Lambda repo.

## When to Use

- behavior-changing handler or helper work
- contract-sensitive request or response changes
- local harness or test changes
- SAM template, env var, or deploy-surface updates
- any task where ambiguity or over-engineering would create risk

## Workflow

1. Define the target.
   - Restate the requested outcome.
   - Name the narrowest proof that would show the task is done.
   - Call out what is out of scope.

2. Read the real contract first.
   - Read `README.md`, `instructions.md` when present, `lambda_function.py`, and `template.yaml` before editing behavior.
   - Read tests or local harness files before changing verification strategy.

3. Choose the smallest affected surface.
   - Prefer a surgical change in `lambda_function.py`, shared helpers, tests, or `template.yaml`.
   - Reuse the current contract and deployment boundaries before inventing abstractions.

4. Make the smallest working change.
   - Avoid speculative helpers, flags, or extension points.
   - Keep unrelated cleanup out of the diff.

5. Verify concretely.
   - Use the narrowest relevant test, local harness run, or SAM check.
   - If packaging or deploy wiring changed, verify the deployment assumptions explicitly.

6. Close with signal.
   - Summarize what changed.
   - State what was verified and what was not.
   - Call out residual risks or assumptions.

## Repo-Specific Rules

- Prefer the repo-local `zoolanding-lambda-workflow` skill before falling back to generic patterns.
- Keep API shape, env vars, and storage contracts stable unless the task explicitly changes them.
- Update docs with the code when contract or deployment behavior changes.