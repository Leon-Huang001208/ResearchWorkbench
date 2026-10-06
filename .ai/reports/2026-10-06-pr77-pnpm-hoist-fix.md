# PR77 production pnpm hoist topology repair

## Source-bound remote failure

Head6ebc1d43f97c992d0cb035c8915b3ac54d4e38fd, base d17459edeff5696d2a2641c4072c2d08e9ae84d0. Docker checkout proves tested merge8cdbf0b549344c1855b94719e44d7ccb7a9a45e0. Constraints37409919144, Checks37409919136 and macOS Bootstrap37409919238 PASS. Docker37409919147 amd64 build/import PASS but initial_start FAIL; arm64 CANCELLED. Artifact11388868823 still has runtime_wait RuntimeError child exit1 and no launcher stage within the bounded 200-line tail. That missing record alone cannot certify Node or pre-logging failure.

## Reproduced local defect

An independent Mac fixture uses the existing fixed source c919b2a460753859665db3f60143d525fb9140cf and existing bundled Node24.19.0. Full source verification and derived inventory verification PASS; actual launcher exec then Node exit1, no listener. 124 public plugin package names could not resolve, although their selected entities and CLI/profile aliases existed. Original asset count28001, source closure11084. This is a non-sensitive isolated HOME/data/state/memory-keyring fixture; original source and user data are untouched.

Native custom loader resolves its optional platform addon from its own anchor and relies on pnpm shared .pnpm/node_modules aliases. stage_assets copied selected entities and direct dependency aliases but omitted that shared hoist tree. Native platform binary itself loads directly; complete-tree helper exposes Node internal loader, derived-tree helper cannot find usable binding. Cordis then swallows that helper error and falls back to bare plugin imports from vendor/loader/lib/index.js. This establishes a concrete local derived-image topology defect and a candidate explanation for Linux CI, not Linux acceptance.

## Minimal repair and RED → GREEN

Preserve hoist symlinks only when the resolved target belongs to already selected production/optional/peer entities. Hoists never add a dependency or alter locks/source versions. Real scope directories are supported; hoist root alias, target race or conflicting output fails closed. Resolve membership before strict recheck so uninstalled, unselected development-platform aliases do not cause spurious staging failure. Selected links remain fully inventoried, hashed and verified before launch.

Behavior RED uses a synthetic native helper, separate dispatcher and platform dependency: complete source succeeds; derived runtime fails MODULE_NOT_FOUND from dispatcher. GREEN covers ordinary and scoped names and excludes both installed devkit and an uninstalled dev-platform alias. Full staged tests44 PASS. The initial actual post-fix staging failed on two uninstalled development aliases; that failure is retained before the stricter selection fix.

The same actual Mac probe then passes fixed source and asset verification, launcher exec, and DSH loopback listener readiness, with MODULE_NOT_FOUND=0 and launcher_failed=0. Final asset count28535 includes506 selected shared hoist aliases, source closure remains11084. Fixture subprocess group was stopped/reaped. This is listener evidence, not authenticated Docker/Web health or Linux image acceptance. Raw fixture application logs are kept only in private task temp directories, not uploaded. Safe summaries are in logs/pr74-pr77-repair/.

## Acceptance boundaries

Fresh packaging/staged/runtime/mode/Docker/CLI Python closure362 PASS in28.58s; JavaScript194 PASS in5.514350209s. Read-only Python review found no new P1/P2. No timeout, health, nonroot, matrix, authentication, permission, cleanup or persistence weakening. No dependencies installed/upgraded. Remaining selected local gates reuse unchanged source/test/lock/platform evidence from6ebc1d43f; full delivery is replanned from master.

requirements/web.in, requirements/web.lock, scripts/setup_web.py, Dockerfile and bootstrap workflow are unchanged; installation compatibility still needs the new automatic CI. Windows/real-machine/Docker Desktop and unavailable style tools remain unverified. New exact-head remote Docker gates NOT_RUN, mergeReady=false,releaseReady=false. No push/rerun/dispatch/merge executed.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Restores selected production pnpm alias topology inside the derived image; deployment, API, health and source contracts stay unchanged.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Documents hoist selection invariant, reproduced defect, listener evidence and missing Linux gates; no diagram change.","diagrams":[]} -->
