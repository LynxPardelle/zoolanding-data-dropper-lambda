---
name: test-driven-development
description: 'Repo-local TDD workflow for Zoolanding Lambda implementation work. Use before behavior-changing handler or helper code changes. Skip as the default path for docs-only or SAM-config-only edits.'
user-invocable: true
---

# Test-Driven Development

Write the failing proof first, then write the smallest code that makes it pass.

## Default Scope In This Repo

Use this for:

- handler behavior changes
- helper logic changes
- request validation or response behavior changes
- storage-contract changes that can be pinned to a reproducible event

Do not treat this as the default path for:

- docs-only changes
- SAM-config-only changes with no behavior change

## Workflow

1. Define the failing proof first.
   - Add or update the narrowest test or local harness case that demonstrates the intended behavior change.
   - If the repo lacks unit tests for the area, create the smallest reproducible event before implementation.

2. Verify the proof fails for the right reason.
   - Confirm the failure matches the missing or broken behavior.
   - Fix the test if it fails because of setup noise instead of the intended reason.

3. Write the minimal implementation.
   - Change only the code needed to satisfy the failing proof.
   - Avoid speculative helpers and unrelated cleanup.

4. Re-run the narrow proof.
   - Confirm the targeted test or harness case now passes.

5. Run the smallest adjacent regression check.
   - Add one nearby test or focused verification step when the change could break adjacent behavior.

6. Refactor only after green.
   - Keep behavior unchanged while improving structure.

## Repo-Specific Guidance

- Pair this skill with `karpathy-guidelines` for scope control.
- Use the existing local harness when a full unit test harness is not present.