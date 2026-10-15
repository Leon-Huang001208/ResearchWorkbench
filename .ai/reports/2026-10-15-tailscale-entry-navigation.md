# Clicked private entry navigation repair

Host macOS/Mac mini; feature bugfix. Base da2e8b71e. User authorizes secure clicked-link access,
standing reviewed PR delivery and updating the local private service. No new dependency, model
call, credentials, public Funnel, network policy or Windows/Linux product dispatch.

Root reproduction: a user-activated cross-site GET navigation to / returns origin_denied 403;
direct address navigation is 200. The global Origin guard incorrectly treats the static app-shell
navigation like an API fetch. 21 new cases: RED 9 FAIL/12 PASS; eight valid shell-entry variants
were rejected and invalid-Host navigation was handled by origin denial before Host enforcement.
Production fix admits only GET / + navigate/document/?1 with absent/same Origin; existing
Host/HTTPS guard, foreign/null Origin denial, API/resource/iframe rejection, internal auth and
CSP remain. Log successful admission only after the final response is HTTP 200.

No lock, installer or dependency changes; existing Web Python 3.12 tools reused without installing
packages. web.in/web.lock, setup_web.py and Bootstrap workflow retain existing contracts.
Because this is a security-boundary repair, select registered supplemental full Web and macOS
Bootstrap gates; Bootstrap is macOS-only workflow_dispatch for this exact candidate branch when
the existing pull-request path filter does not select main.py. This is not Windows/Linux dispatch.

Focused GREEN and full relevant tests, review, local live browser/HTTP, CI, publication and
activation are recorded in logs/entry-nav and the final task receipt as they actually complete.
No new model generation, MacBook physical browser or Windows/Linux product evidence claimed.

Focused GREEN: 31 PASS in 0.71s. Read-only independent Python/security review APPROVE.
Playwright real-browser click from http://localhost:18885 to the isolated candidate at
127.0.0.1:18886/#/fingpt: HTTP 200, FinGPT title rendered, browser-generated Fetch Metadata
cross-site/navigate/document/?1, absent Origin. Screenshot, snapshot and request proof saved
under logs/entry-nav; fixture uses no real model or production data. Owned browser/fixture
processes stopped after verification. This is local macOS browser proof, not a MacBook claim.
Managed runtime manifest, Ruff, mypy, all selected Node/constraints/doc/index checks passed.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有Host中仅根路径静态壳的用户导航例外，API同源与内部认证保持，无新节点或接口路径。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"入口只加载原UI，Web/DSH进程、会话协议、SSE和预算边界均不变。","diagrams":[]} -->
