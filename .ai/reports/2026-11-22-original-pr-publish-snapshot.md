# Original PR publication candidate snapshot

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"The project wrapper and its pinned shared delivery controller use the same actual integration candidate for publication and original PR reuse. Existing task identity, verification, Git, quota, backup and branch protection remain; no research runtime, service, schema or execution node is added.","diagrams":[]} -->

## Problem and scope

Original PR #285 continues under its original task. A later local revision retained the previous prepared candidate, while the real shared publisher reads the current integration HEAD. The project publication callback previously captured the earlier receipt, so it could compare the pushed current head against the old candidate and reject the original PR as `PR_HEAD_MISMATCH`.

The actual prepared-amend attempt was refused with `UNPUBLISHED_STATE_INVALID` because the task already has historical remote publication. That strict contract remains unchanged. This tooling task addresses publication snapshot consistency; it does not reset the business task or edit its historical receipts.

## Validation and delivery boundaries

The regression must use the real shared controller with independently read receipt objects and a local Git remote. Source checks, independent review and exact-candidate CI are recorded separately. No real GitHub publication, live service, model, provider, task resume or deployment is part of the local regression. Original PR/task ancestry and refusal on changed or ambiguous identities remain required.

The 17-line source correction freezes the current integration candidate after the existing feature/worktree checks. The callback uses that snapshot for original-PR reuse and new-PR text, rejects changed candidates/remotes and checks the returned PR URL belongs to the same repository. The strict amend contract and pinned shared controller are unchanged.

The actual old implementation reproduced `PR_HEAD_MISMATCH` after a forward push to the local bare remote. Focused regression checks passed 15/15; the complete GitSafety module passed 162/162 without skips in 284.457 seconds. Independent TypeScript review found no remaining P1/P2. Documentation governance, Python index and all seven changed-path project constraints passed at the source checkpoint. Exact prepared-candidate checks and GitHub CI remain pending here.

The new callback checks cover first publication and reuse of an original PR; the existing `pr`-mode repair direct-push path is unchanged. Candidate drift can be detected after a push has occurred; refusal to adopt a receipt does not undo that external write. Such results require reconciliation and retained evidence, not a fabricated rollback or replacement task.

Product-Progress: not-required — 本次只修复本地受管Git交付工具的候选快照绑定，不改变用户功能或常驻版本。
