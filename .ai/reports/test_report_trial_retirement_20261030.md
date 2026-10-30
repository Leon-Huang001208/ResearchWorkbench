# Authorized trial retirement and resident deployment

Task resident-trial-retirement-deploy-20261030-8e40c9ad, macOS maintenance,
base db2ae9a48ceca365852072e622aa6627aa7d0b83. Root is the sole live writer.

The user explicitly authorizes discarding historical RWB trial sessions and
Wind UNKNOWN state while retaining accounts and model configuration. Those
historical states no longer independently veto deployment. Disposition must
remain user-authorized discard, never fabricated idle or cleanup success.

PR246 has actually merged as db2ae9a. Its three CI checkouts, Mac doctor and
7508 research + 91 unit case artifacts were checked. The original reviewed
delivery was formally transferred to the new main common and independently
verified; original receipts remain protected.

The new backup helper is a maintenance library, without deletion or deployment
authority. Independent review found and closed pinned-path, directory durability,
aggregate-capacity and same-FD free-space defects. The initial thirteen offline tests passed;
Black, Ruff, syntax and diff checks pass. A real read-only preview confirmed
15 account roots, 13 indices and 113 trial sessions, with 2 absent indices.
The sealed observation is stored privately in the resident logs. No account,
model, session or Wind state has been modified by this task.

Backup must run under the maintenance exclusion after verified old writers
have stopped. It preserves account DB, binding and indices/model settings;
session artifacts are outside this helper's receipt. Source Router, exact CI,
actual backup, trial disposal, version switch and authenticated acceptance are
not yet complete. Original peer owns the separate unreviewed c819 controller work;
this operator uses the existing maintenance transaction instead of that WIP.

The helper now includes report-workflows catalogs in its seal and backup; nineteen
tests pass. The offline retirement module has thirty-four tests, including actual
automation/report recovery interfaces with model callbacks trapped to prove no
replay, directory replacement ownership, legal termination drift, and manual
restore boundaries. Initial existing-operator plus new wiring regression passed
2791 cases; subsequent wiring and terminal recovery cases passed in scoped runs.
The frozen wiring adds 48 scoped cases; together with 34 retirement and 19 backup
cases, 101 pass. Independent SPEC and Python quality reviewers report no open
P1/P2 for wiring b1266407, trial 8ffdbd38 and backup 86d7c21e. The final full
regression and candidate-bound Router/CI are still pending.

Independent review found a completion-journal retention defect and a subsequent
terminal-recovery conflict; both were repaired with durable terminal intent and
immutable completed receipts. The terminal BirthFence release defect was also
repaired and tested through real outer fence acquisition, including a second
account's reservation. Recovery clears only this exact transaction; wrong-owner
cases retain journals and fencing. No unfinished review is marked PASS.
The existing recovery fixture's missing data_layer dependency reproduced against
the unmodified db2 operator; its explicit copied closure was minimally corrected,
with original failing logs retained and assertions unchanged.

Final pre-type frozen feature e43d13c0 completed the complete existing operator
and three new modules: 2869 passed, one original warning, 283.05 seconds. Subsequent
internal TypedDict/local annotations and two guarded bytes casts fixed fourteen
new mypy diagnostics. Type-erased AST bodies are identical and 53 module/backup
tests pass. The authoritative normal-config fresh-cache command without injected
PYTHONPATH retains exactly the original thirteen diagnostics in five unchanged
imports: FAIL_BASELINE, not PASS. A different-environment early zero was explicitly
marked non-authoritative. Formatting checks pass.

The first full Router run exposed missing required documentation updates; all
seventeen violations were corrected with relevant module documents and README
review. The final candidate will rebind the complete changed set and rerun its
selected gates. The feature has incorporated reviewed master c6e24e after PR254;
the deployed product target remains db2ae9a, distinct from the operator executor.

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"A fixed operator-authorized trial-discard profile extends the existing Native maintenance transaction, recovery and process identity checks; product and executor identities remain distinct. No service, DSH runtime or alternate deployment engine is added.","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"The privileged offline operator binds existing account roots and preserves account/model configuration while retiring explicitly authorized trial state; no public cross-tenant research API is added.","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"Three offline test modules and a maintenance import smoke are added to existing CI steps without new jobs, runners, dependencies or timeouts.","diagrams":[]} -->
