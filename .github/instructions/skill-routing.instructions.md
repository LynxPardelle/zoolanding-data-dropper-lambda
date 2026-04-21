---
name: 'Zoolanding Lambda Skill Routing'
description: 'Use when deciding which installed general skills fit this Zoolanding Lambda repo. Steers the agent toward repo-local workflow skills and away from irrelevant cloud or IaC workflows.'
applyTo: '**'
---

- Prefer repo-local workflow skills, prompts, and vendored repo-local skills before installed global skills.
- Default to the repo-local `karpathy-guidelines` skill for Python handler, helper, SAM template, and local harness work.
- Invoke the repo-local `systematic-debugging` skill before fixing bugs, failing local harness runs, or unexpected behavior.
- Use the repo-local `test-driven-development` skill for behavior-changing handler or helper code, not for docs-only or SAM-config-only edits.
- Use the repo-local `risk-review` skill for review-only asks, regression hunting, and findings-first diff review.
- Use the repo-local `zoolanding-pr-followup` skill for PR follow-up workflows; pair it with GitHub globals only when they are available.
- Use the repo-local custom agents `zoolanding-production-readiness` and `zoolanding-config-platform-audit` for release-readiness and cross-repo contract reviews.
- Use the repo-local `sam-deploy-check` prompt before deploy-readiness review.
- Reach for `devops-rollout-plan` only for risky deploy or infrastructure coordination work.
- De-prioritize `cloud-design-patterns` and `terraform-skill` unless the task is explicit architecture or Terraform or IaC work.