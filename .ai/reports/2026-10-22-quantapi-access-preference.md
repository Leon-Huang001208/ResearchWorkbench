# QuantAPI existing access credential repair

- Host: macOS; task type: Web feature defect repair. Local offline tests and the separately authorized Host metadata acceptance are recorded separately below.
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

Remaining: integration/full Router and integrity gates, exact-candidate Mac bootstrap CI and any deployment require their own evidence. Windows/Linux/Docker acceptance NOT_RUN. The policy schema is intentionally closed; vendor shape changes fail safely and require review. Metadata authentication is not market-data permission acceptance.


<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只调整既有Provider令牌选择及显式认证的官方元数据请求；原Host/DataHub/来源/快照拓扑与HTTP入口保持，无新数据集、schema、研究执行或供应商权限。","diagrams":[]} -->

Root独立SPEC/Python与质量复审均PASS，分别71项离线回归，未读取真实凭据。官方Skill已在独立新进程使用用户保存的已有access完成get_limit_policy HTTP200，user_type=free；该证据不等于此候选Host入口或行情权限通过，后者另行验收。

## Host 授权入口实测（2026-10-22，root 独立执行）

已读取并核对 root 的私有实测回执：候选 `3e214bfb3f8e858cb052d3361ff2ce1365c20534`，
Provider SHA-256 `6ae1ceab533690e4e0354cfc4696fe9fa3589c7f9616b6748b6b101b2bf0943e`。
真实 FastAPI 入口按 `config PUT → verify POST → config GET` 执行并返回 HTTP 200、
`authenticated`，仅向官方固定 `get_limit_policy` 发出一次 GET。
回执记录 access exchange=0、token rotation=false、market data queries=0、model prompts=0、
真实凭据后端调用=0；`data_permission_verified=false`、`data_queries=0` 保持。
此次验收采用内存凭据与 fail-closed 边界，临时目录已由 root 清理；NoModelsNative 夹具不是真实 DSH。
本次交付续跑只读取这份已有证据，不重复厂商请求，也不操作旧 18993 隔离验证实例。

| 私有证据（ignored，不提交原件） | SHA-256 |
| --- | --- |
| `logs/quantapi-host-acceptance/result.json` | `7675a018049fa4542a0b6b8ca2395d2452f83ea2ca5690f5d114452c041406c0` |
| `logs/quantapi-host-acceptance/host.log` | `8ce66fde4ef655827c926e34481510bbb13e9c779bb81460a71777278fdd028e` |

此 PASS 只证明候选 Host 授权路径真实使用已有 access 认证，不能证明行情权限、研究模型质量、
常驻已更新或安装 CI 已通过。报告后续提交只补证据文字，产品源码身份保持上述 SHA-256。

## 交付续跑本地门（2026-10-23）

在源检查点 `3e214bfb3f8e858cb052d3361ff2ce1365c20534` 基础上，只修改本报告补录证据。
受管运行时 manifest 的14个文件哈希全部相符；`git_safety check` 报告 fsck PASS、无原生锁。
完整13路径 Router 为 L4，命中 `documentation` 和兜底 `unknown-boundary`；
task context 显式补选既有 catalog 的 `project-constraints-local`、`research-web-checks`、
`research-web-bootstrap`，保留原 `project-constraints` 和全部本地门，不以路径漏选省略 Mac 安装验收。

- 三个近处 Python 模块重跑：76 passed in 0.26s，`logs/quantapi-access-preference-final-pytest.log`。
- L4 原治理/架构/预算/跨平台合同：112 passed，`logs/quantapi-verification-full.log`。
- Documentation governance：804文件、106 current、0 violations，`logs/quantapi-documentation-governance.log`。
- Python file index：已核对，`logs/quantapi-python-index.log`。
- Project Constraints 本地完整13路径：0 violations，`logs/quantapi-constraints-local.log`。

以上为 feature 工作区本地证据；待受管 prepare 后重新绑定集成候选、完整 changed set、独立评审及三项远端 CI。
准备/发布/合并按共享 Git 写窗口串行执行；不存在以 feature 本机通过代替集成或远端通过的声明。
