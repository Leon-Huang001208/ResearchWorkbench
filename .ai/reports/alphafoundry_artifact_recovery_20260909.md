# AlphaFoundry artifact recovery

Date: 2026-09-09

## Scope

The former `/Users/leon/Desktop/Projects/AlphaFoundry` directory was not a Git repository. Before replacing it with this ResearchWorkbench worktree, the directory was archived in full and its SHA-256 was recorded in the external reconciliation inventory.

## Evidence reviewed

The directory contained only:

- local Harness records;
- Playwright console and page snapshots;
- a generated Graphify graph and cache;
- five `research-workbench-chat-*.png` screenshots.

The tracked ResearchWorkbench documentation contains no reference to those five screenshots or to the generated Graphify files. The product documentation explicitly states that the current ResearchWorkbench interface does not copy AlphaFoundry demonstration data.

## Recovery decision

No binary or generated artifact is imported. This avoids adding unreferenced screenshots, local Harness state, browser logs, or Graphify cache to the repository. The complete original directory remains recoverable from the external archive:

- `research-workbench/alphafoundry-original.tar.gz`
- SHA-256: `f1707db6e925fb918f5e1f168f9139b42f52c0ca3fcb958afed98265510485ee`

This report is the traceable retirement record for the former standalone AlphaFoundry directory. AlphaFoundry development now continues as branches and worktrees of ResearchWorkbench.
