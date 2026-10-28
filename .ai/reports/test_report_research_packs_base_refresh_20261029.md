# Research packs: genuine master refresh

macOS Web source integration, original task `seek-packs-20261027-7bda5752`, PR245.

The previous local A+B candidate is `26c75a4f72fbccc7149a79194da6c6a913e60b15`.
Master genuinely advanced to `07220cd26533361512eeebe24b9d0fa5a444173b` after PR247.
This merge retains both candidates, the original PR and all three recorded CI repair attempts.
It does not authorize a fourth same-base repair or reset the counter.

Eight additive conflicts were resolved: Mac Bootstrap retains both the installed-wheel/pack
checks and watchlist import/static-resource checks; workflow and development documentation
retain both changes. Architecture groups are merged by identity and API declarations by
their full content, then the two generated HTML artifacts are regenerated. Four module
documents describe the shared Store boundary and preserve the separate execution/quality gates.

Actual checks: the initial architecture merge failed on duplicate reading modules; the
corrected three-way merge generated 416 declarations/413 unique operations. Architecture
then identified four missing changed-module documents; those were updated. Final architecture
check and `git diff --check` passed. The failed attempts remain in the control workspace logs.

Full changed-set Router, local acceptance, Native7, independent review and candidate CI
remain pending. This merge is not evidence of report quality, actual model/provider calls,
resident deployment or Windows/Linux product acceptance. No dependency was installed.
