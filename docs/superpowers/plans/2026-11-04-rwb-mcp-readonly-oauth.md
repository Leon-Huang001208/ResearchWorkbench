# RWB MCP private readonly OAuth v1 implementation

## Authority and Global Constraints

User explicitly requested implementation of the approved private shared, native OAuth, no connector plan. macOS development/local acceptance; no resident deployment, live-account authorization, new dependency installation, provider or product-model calls without separately permitted scope. Existing DSH pin/kernel, Providers, DataHub contracts, history and browser accounts remain compatible. Feature defaults off.

- Private existing canonical origin only; `/mcp`, no public exposure or local proxy/connector.
- Streamable HTTP, stateless handling, tools baseline2025-11-25, pinned `mcp==2.2.0`; no FastMCP import, SDK patch or dependency upgrade.
- Four tools only: rwb_capabilities_list, rwb_datasets_list, rwb_dataset_read, rwb_source_read. Dataset rows default100/max500; source text max12000characters. Request64KiB/response256KiB. Explicit partial/pagination and original digests/provenance.
- Existing authenticated user→existing RuntimePool backend; fixed existing read paths only; no arbitrary proxy or internal control key/client-cookie forwarding. Discovery does not allocate a backend; reads may use existing bounded runtime lifecycle but never create a new research session, send a model or fetch Provider data.
- Approved public/synthetic frozen objects only, allowlist binds account/context/kind/object/digest. Allowlist is trusted operator configuration, never a model/OAuth request's declaration. Empty approval defaults deny data. Existing frozen-result upstream authorization and report_invalid gates remain.
- OAuth authorization server and resource server logically separate in same gateway process; SDK auth routes/provider and token verifier with durable storage. Fixed public client rwb-codex-native, no DCR/CIMD endpoint or client secret. Loopback callback http://127.0.0.1/callback allows variable port, no other callback host/path. Response iss and token resource exact canonical origin/mcp binding.
- PKCE S256. Authcode60seconds/single-use; access600seconds; refresh604800seconds/rotation. Only token digests persist; raw token issued only in OAuth response, never logs.
- A single v1 scope `rwb.read` covers the four readonly operations; object allowlist further narrows every grant. No future query/write/run scope implicitly granted.
- Every request checks enabled account, current grant/scope/resource and approved object/digest. Recheck before returning bytes; account disable/reset-password revokes OAuth grants in same transaction. Ordinary browser logout does not revoke independent apps. Cookie alone cannot authenticate MCP.
- Consent and per-user authorized-app listing/revocation through existing browser login. No model tool can grant permissions or certify report quality. No tokens, passwords, cookies, auth codes/verifiers or unbounded bodies in logs/evidence.
- Native Codex actual login/read/report acceptance is separate from isolated HTTP acceptance. DSH/WorkBuddy nativeOAuth unverified stays NOT_RUN; no manual token/proxy fallback. Real deployment/accounts remain manual/explicit stage.
- Existing exact2.2 SDK gaps: standard metadata hardcodes secret methods; wrap to advertise none/actual grants, add iss success/error redirect; validate token-request resource before SDK ignores it. This is policy glue around typed SDK routing, not a second OAuth parser or crypto stack.
- Reuse already installed readable exact2.2 environment read-only with PYTHONDONTWRITEBYTECODE=1 and explicit feature PYTHONPATH; never write/delete another task's environment. No installation authorized.
- Latest AGENTS requires test_artifact_retention.py run, at most20 node IDs per batch, one task active tmp root, --mode wip for RED/GREEN uncommitted runs; success cleanup only formal tool, failed receipts retained. Logs retained total<=128MiB. See current AGENTS/docs.

## Route and evidence rulings

Ruling: managed git_safety check passed; start failed before receipt because GitHub SSH auth unavailable and github.com HTTPS times out. Latest GitHub master87b6cd99653d9f8160dc7eb0b3bea8d5d9ea93db verified with gh API and matches existing origin/master/object. Codex native managed worktree isolates local implementation at that exact commit. No delivery-controller bypass/patch or publication: after SSH recovery transfer own commits through normal managed feature and full prepare/review/CI path. Existing source checkout stays untouched. User has been asked once to unlock the existing registered SSH key; no private-key content read, new key, agent identity or globalGit config change.

Ruling: current locked SDK library source at parent .venv is dataless. Use readable exact2.2 environment only as installed libraries/interpreter, never historical RWB source; explicit imports must resolve to this feature checkout.

## Task 1: Durable OAuth and material authorization store

Allowed edits: app/research_web/mcp_facade/__init__.py, models.py, authorization_store.py; app/research_web/multiuser/accounts.py only additive schema and lifecycle revocation; tests/research_web/test_mcp_facade_store.py. No gateway/HTTP/SDK routes yet.

Implement persistent domain storage sharing existing Account SQLite identity/transactions (no second account database or browser-session reuse). Store fixed client metadata, authorization requests/codes, grants, access/refresh digests, operator-approved material metadata and grant-material selections. Framework-neutral methods must support SDK provider and consent in Task2: create/load consent request, issue/load/atomically exchange code, verify access, rotate refresh, revoke grant, list grants/materials, load fixed client. Document actual signatures for next implementer.

Material approval API is trusted internal/operator-only; classification public|synthetic and exact SHA256. No default-wide export. Consent can select only currently approved account-owned material IDs, grant is never inferred from user_id/tool args. A granted material revoked/changed or wrong context cannot read. Token/resource/issuer/client/scope/expiry persist and validate; atomic concurrent code exchange and refresh; replay rejected. Unknown client/callback/scopes and unsupported PKCE fail with stable secret-safe errors. Account lifecycle remains compatible including absentOAuth tables on older stores.

Tests first meaningful RED/GREEN: expiry/consumption/replay/concurrency, resource/client/redirect/scopes, hash/owner/context/material revoke, account disable/re-enable/reset/logout compatibility, SQLite restart, no plaintext tokens persisted/logged. Batch<=20 with retention wrapper. Commit only Task1 files. Report to SDD report file; no delegating or publishing.

## Task 2: SDK OAuth and readonly HTTP facade

Depends Task1 reviewed store APIs and exact2.2 SDK audit. Implement separate SDK Provider/Auth routes plus verifier, consent + per-user revoke views, gateway feature off integration, four readonly tool schemas and fixed backend read adapter. Use typed SDK handling/lifespan and genuine HTTP auth tests including metadata/iss/resource gaps, revocation mid-read, negative routes, caps and side-effect counters. No live deployment/accounts. Split into reviewed sub-batches if coupling warrants it; keep all user requirements.

## Task 3: Whole-feature integration, docs/Doctor/install and delivery

Use current project log/error conventions, docs architecture/map/API/security/install contracts, Doctor safe default-off/pendingAuth/actualVerification statuses. Add focused tests to existing CI steps with actual time reserve, no extra runners/timeouts or vendor/model calls. Run Router and required Mac local/CI/SDK clean-install gates. Independent Python/security and any JS review. Standard git_safety delivery once auth available; no native residency update. Keep actual Codex/private dual-device/other host acceptance unverified unless authorized setup and native evidence obtained. Record limitations rather than pass.
