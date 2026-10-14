# Framework Direct Embed UI

Host: macOS. Scope: existing Research Web iframe presentation and route isolation.

The existing eleven embed asset directories are real static builds, not placeholder HTML.
Gold and Dollar use repository-owned relative assets and data snapshots. This iteration
removes the repeated outer hero and metadata band, puts the framework name in the product
topbar, loads the iframe eagerly, expands it to available viewport height, and uses equal
grid rows for framework cards. A slug guard prevents stale data rendering after a route switch.

Validation performed:

- Node syntax checks for frameworks.mjs, frameworks/embedded.mjs and shell.mjs passed.
- Direct Node assertions for embed rendering and stale framework isolation passed.
- Browser: Goldar overview and investment framework rendered; Dollar overview and data
  panorama rendered. Both use /frameworks-embed/ paths. Console error inspection was empty.
- Browser at 1280px: all eleven cards measured 551.5 x 324.1953125px. Gold outer document
  scrollWidth equaled clientWidth (1280px).
- Screenshots: /tmp/rwb-framework-ui-evidence-20261014/{gold,dollar,hub}.png.
- Standard pytest invocation was blocked by parent conftest requiring sqlalchemy.
  Using --confcutdir=tests/research_web ran the scoped suite: 6 passed, 3 failed.
  Failures cover old native snapshot/catalog expectations and DSH message/preset behavior;
  these are not accepted as a passing backend regression. Native canvas JavaScript tests
  still target the retired outer UI and were not represented as passing.

Boundaries: no new package installation, service restart or production
deployment in this iteration. Background collection, live refresh, dynamic Goldhub requests
and model scoring remain unported from standalone apps; static snapshots do not prove
functional parity for those operations. Mobile viewport and clean-install CI not run.

Rollback copies of the five edited UI modules/styles are retained at
/tmp/rwb-framework-ui-backup-20261014/.

## GitHub Branch Handoff

On user request, framework-only changes were applied with a three-way patch onto current
origin/master (38c18095) in an isolated managed worktree, branch
codex/research-framework-embeds-20261014. Both overlapping front-end additions from master
were retained while resolving shell imports and appended CSS. This branch includes 11
embedded apps and their static data. It excludes unrelated FinGPT local commits and an
unnecessary whitespace-only routes.py diff. JavaScript syntax checks passed after resolution.
The previously recorded failing backend tests remain disclosed; no complete regression or
clean-install acceptance is claimed. Credential-pattern and secret-file-name scans of
embedded resources found no matches. The branch is for review and is not merged into master.
