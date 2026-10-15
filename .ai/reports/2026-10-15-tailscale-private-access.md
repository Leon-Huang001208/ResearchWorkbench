# Tailscale private access compatibility

Host: Mac mini / macOS. Task: feature repair; Native access and macOS CI only.
User authorized exact Tailscale Host/Origin support and resident update. No new dependency,
model request, network membership/policy change, Funnel, or Windows/Linux dispatch.

Reproduction: Serve TLS verified, but Host returns HTTP 400 Invalid host header.
The failed Serve configuration was rolled back; local 8088 remained HTTP 200.
Root cause: fixed loopback Host allowlist. Added opt-in RESEARCH_WEB_PRIVATE_ORIGIN,
one exact HTTPS Tailscale hostname, same-origin guard and default port/HTTPS enforcement.
Doctor reads applied mode from the owned running Host, not the invoking shell environment.
Default access, private RPC authentication, CSP, data/model settings are preserved.

RED: 10 new focused tests failed on the original implementation. Initial GREEN: 15 focused
tests passed, before adding the same-origin API lifecycle test. Evidence: logs/tailscale-private/.
Independent read-only Python/security review APPROVE; all 16 focused cases passed.
Actual Tailscale Serve to isolated Uvicorn/fixture candidate: verified TLS, root/static/runtime
HTTP 200, applied exact origin, evil Host 400 and cross-origin/cross-site 403. Fixture transport
is not real-model acceptance. Preview proxy and owned process stopped after verification.
Ruff/Black/isort/mypy (--follow-imports=silent) passed. Initial index/constraints failures required
regenerated Python index, README review and module docs; repaired checks passed, failures retained.
Existing Python 3.12 test tools reused read-only; no package installed or lock changed.
Routed checks, independent review, Mac Bootstrap CI, merge, deployment and tailnet HTTP
acceptance remain pending. Cross-device/external-network and real SSE/model are NOT_RUN.

Full routed Python invocation: 600 PASS/7 FAIL in 445.57s; all seven were Doctor's extra
HTTP read violating existing no-extra-request/error-response fixtures. Repaired production
diagnostics to reuse its existing runtime read, reset unknown on every diagnosis, and preserve
the model diagnostic return contract. Original failing tests unchanged. Entire service manager
rerun: 348 PASS in 12.10s; API/protocol tests from the first run had no failures. Independent
repair review APPROVE; Ruff and mypy silent-import check passed again. Original failure log
and repaired run retained separately; no single all-green combined invocation is claimed.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"现有回环Host增加显式精确Tailscale origin并保留认证与同源门，无新运行节点或研究引擎；默认部署不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"原Native进程与回环端口不变，Doctor增加运行中Host访问模式的只读投影。","diagrams":[]} -->
