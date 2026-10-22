# QuantAPI existing access credential repair

- Host: macOS; task type: Web feature defect repair. This report covers local offline tests only.
- Base managed worktree task: `datahub-quantapi-auth-20261022`; no Git mutation, dependency installation, service operation or real vendor/model request was performed by this implementer.
- Root cause: `credentials()` exchanged refresh before considering existing access. Explicit authorization rejected plain access and required refresh even when access was valid.
- TDD reproduction: the updated `test_quantapi_authorization.py` initially produced **2 failed, 2 passed**, demonstrating both defects, using only `httpx.MockTransport` and synthetic secrets.
- Repair: prefer bounded existing access (JSON or legacy string); only refresh-only configuration exchanges once. Explicit existing-access verification uses one fixed HTTPS metadata GET to `get_limit_policy`, a 12-second total budget, 8-second HTTP timeout, 1MiB response cap, no redirects or environment proxies, and the six-field native policy shape supplied from the root's separately authorized metadata observation. Policy content and raw vendor errors are not published. Business queries do not retry 401 or rotate tokens.
- Preserved: refresh-only explicit exchange contract; `data_queries=0`, `data_permission_verified=false`, `token_rotated=false`; Host actor/configuration-epoch checks, numeric envelopes and missing-data semantics.

Validation used `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python`:

```text
-m pytest --confcutdir=tests/research_web tests/research_web/test_quantapi_authorization.py tests/research_web/test_external_sources.py tests/research_web/test_datahub_numeric_sources.py -q
76 passed in 0.21s
-m black --check app/research_web/datahub/providers_external.py tests/research_web/test_quantapi_authorization.py tests/research_web/test_external_sources.py
3 files would be left unchanged
-m isort --check-only [same three Python files]
passed
-m ruff check [same three Python files]
All checks passed
-m mypy --follow-imports=silent app/research_web/datahub/providers_external.py
Success: no issues found in 1 source file
```

Test log: `logs/quantapi-access-preference-pytest.log`, SHA-256 `a77025c7c2bdd26b06e3451d96eba261d3ef13785236bca6897e617fa75392f4`.

Frozen file SHA-256:

| File | SHA-256 |
| --- | --- |
| `app/research_web/datahub/providers_external.py` | `6ae1ceab533690e4e0354cfc4696fe9fa3589c7f9616b6748b6b101b2bf0943e` |
| `tests/research_web/test_quantapi_authorization.py` | `27839d3c43b01638602878649c32dff5b264b07342e56affe4049e57787017bb` |
| `tests/research_web/test_external_sources.py` | `e15f706ff296a0007285ac1c37a4bbe08793cb6b7c4f26730b2e8be4e3330ebf` |
| `docs/research-web-datahub.md` | `4961f24f6de3bb2bf484d6ddc4ac8ec0f97b44797b2954856b680d7c5981a646` |

Remaining: root independent review, integration/full Router and integrity gates, exact-candidate Mac bootstrap CI, authenticated Host authorization acceptance and any deployment are outside this implementer's evidence. Windows/Linux/Docker acceptance NOT_RUN. The policy schema is intentionally closed; vendor shape changes fail safely and require review. Metadata authentication is not market-data permission acceptance.


<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只调整既有Provider令牌选择及显式认证的官方元数据请求；原Host/DataHub/来源/快照拓扑与HTTP入口保持，无新数据集、schema、研究执行或供应商权限。","diagrams":[]} -->

Root独立SPEC/Python与质量复审均PASS，分别71项离线回归，未读取真实凭据。官方Skill已在独立新进程使用用户保存的已有access完成get_limit_policy HTTP200，user_type=free；该证据不等于此候选Host入口或行情权限通过，后者另行验收。
