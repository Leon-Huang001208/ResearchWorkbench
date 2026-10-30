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
aggregate-capacity and same-FD free-space defects. Thirteen offline tests pass;
Black, Ruff, syntax and diff checks pass. A real read-only preview confirmed
15 account roots, 13 indices and 113 trial sessions, with 2 absent indices.
The sealed observation is stored privately in the resident logs. No account,
model, session or Wind state has been modified by this task.

Backup must run under the maintenance exclusion after verified old writers
have stopped. It preserves account DB, binding and indices/model settings;
session artifacts are outside this helper's receipt. Source Router, exact CI,
actual backup, trial disposal, version switch and authenticated acceptance are
not yet complete. Original peer owns the unreviewed c819 controller work and
its remaining P1 repairs; it must not be used for production yet.

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"This helper supplies bounded configuration preservation to the existing resident maintenance transaction. It adds no service, runtime, research API, deletion authority or alternate deployment engine.","diagrams":[]} -->
