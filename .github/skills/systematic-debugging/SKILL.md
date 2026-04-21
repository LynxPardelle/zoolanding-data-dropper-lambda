---
name: systematic-debugging
description: 'Repo-local root-cause debugging workflow for Zoolanding Lambda issues. Use before fixing handler validation bugs, storage-contract mismatches, local harness failures, test failures, or unexpected SAM behavior.'
user-invocable: true
---

# Systematic Debugging

No fixes without root-cause investigation.

## Primary Targets In This Repo

- request parsing and validation
- storage-key or payload contract mismatches
- local harness or unit test failures
- SAM template, env var, or deployment wiring issues

## Workflow

1. Reproduce the failure.
   - Capture the exact event, command, or request that fails.
   - Save the observable symptom: handler output, stack trace, failing assertion, or deployment error.

2. Localize the failing surface.
   - Decide whether the first bad state is in handler logic, a helper, input shape, or template wiring.
   - Reduce the failure to the smallest reproducible event or command.

3. Trace to the first wrong state.
   - Follow data flow from the symptom back to the first incorrect assumption, payload field, env var, or storage decision.
   - Prefer code evidence over intuition.

4. Fix the root cause.
   - Apply the smallest change that corrects the first wrong state.
   - Avoid defensive edits until the root cause is understood.

5. Verify the fix.
   - Re-run the failing command, event, or test.
   - Run the smallest adjacent regression check that would catch the same class of failure.

## When You Are Stuck

- Add short-lived diagnostics at handler and storage boundaries.
- Build a minimal event fixture that isolates the contract edge.
- Compare code, README, and template assumptions instead of assuming they still match.