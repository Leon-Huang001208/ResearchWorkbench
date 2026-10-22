# iFinD existing access authorization and history request repair

- Host: macOS; task type: Web feature defect repair. Local offline tests and the separately authorized Host metadata acceptance are recorded separately below.
- Base managed worktree task: `datahub-quantapi-auth-20261022`; the first implementation checkpoint performed no Git mutation. Subsequent report commit, managed integration and PR190 publication were coordinated through the shared Git window. No dependency installation, service operation or real vendor/model request was performed by this implementer.
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


<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"调整既有Provider令牌选择、显式认证元数据请求和既有历史dataset的官方URL/单层reqBody；原Host/DataHub/来源/快照拓扑与Host HTTP入口保持，无新数据集、schema、研究执行或供应商权限。全null保留原值并标记partial，未提升单位或正式回测。","diagrams":[]} -->

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

## 历史行情续修（2026-10-23，未发布新候选）

原授权修复的 PR190/head `0e7e3911399566d0bd44e475202fd5f8ee851b42` 保持冻结；
本节实现位于同一受管 integration 工作区，尚未提交或重新发布。旧报告中的文件hash和CI只认证其当时检查点，不能认证以下新增历史请求行为。

只读比对已安装的官方 Skill 1.1.0 历史行情文档与仓内目录发现：legacy dataset
`cmd_history_quotation` 仍指向同名旧URL，而官方 THS_HQ 必须调用 `/api/v1/history_data` 并以
`reqBody` 包装整个请求。旧仓内历史测试只有 `arguments_json={}`、模拟time/table响应，没有
functionpara字符串或其他旧语法的可用性证据。官方文档仅支持functionpara对象。

TDD先新增flat/reqBody两例MockTransport断言：旧实现 **2 failed, 5 deselected**，明确捕获旧URL。
另新增全null回归先观察 **1 failed, 23 passed**：旧结果错误标为snapshot。
修复保留dataset ID及研究仓白名单，纠正固定HTTPS出口；合法flat精确包一次、原生reqBody不再包，
混合/未知字段/空白超长证券或指标/坏日期及不支持functionpara格式先于取密安全拒绝。
仅接受已声明选项，不静默丢弃字段或补币种/复权/填充默认值，不增加EDB、日期序列或PIT。
日期支持官方三种形式；Interval/SampleInterval互斥。连接仍使用Host connections和已有access优先，
401不自动交换refresh；实现者未读取全局Skill token文件、Keychain或真实配置，未调用厂商或模型。

成功保持官方tables/thscode/time/table逐项对齐与原始字节，错误码非零/坏shape失败、empty明确为空；
null不填零，全null返回partial/history_values_missing并保留原件，不满足既有完整原生快照准入。
请求币种或复权方式不等于独立口径核验，provider_defined和formal-backtest拒绝仍保留。

本地四模块合计 **137 passed in 0.72s**：原auth/external/numeric及research_snapshot_store；
日志 `logs/quantapi-history-green.log`。此处真实供应商形状基于官方文档及原封闭envelope夹具，
root先前单点close9.66/dataVol1仅是独立官方Skill样本，未保存原件，不冒充本候选Host历史数据通过。
新产品冻结后仍须root一次受控Host 1-cell验收、两级独立评审、最新基线和同候选原三CI。

历史修复本地冻结（未提交）：Provider SHA-256
`33a9749f6008c6cd4057bbbee2b946f3406a0bf531476848f72c8338046c54d3`；
目录JSON `315139449c782eb78781d394b62cdb2fc8eb781e6bac7a50a186be98168ed8cc`；
数值回归 `47cdf32d92e08331bc3d6754631d1aff16421fbdd87bb3adc6b18b7b2b07c0db`。
四模块137项日志SHA-256 `3d75b03574792b710b5b3ad21870e3948d2b38c75df01bc601cd2cf90e15016a`。
新增/完整 changed set 共16路径，Router仍为L4兜底并保留原三CI补选；
L4 JS112项、完整Constraints、documentation governance（806文件/106 current/0 violations）、
Python index及black/isort/ruff/mypy均通过。旧0e7e上的CI不得沿用为这些新字节通过。

按本任务唯一临时根再验证：`--basetemp=logs/quantapi-history-pytest-x2LAGU`，同四模块
137 passed in 0.68s；上下文记录 `logs/quantapi-history-test-context.json`，
日志 `logs/quantapi-history-owned-temp-pytest.log` SHA-256
`ebbb9654cabb003df973d7103524bf2a250d122cee57e29f97ac9e21f62f7178`。
该临时目录由本任务新建，不复用其他任务basetemp或真实业务/凭据目录。

### SPEC P2 规模修复

独立SPEC评审发现：返回行数limit只裁本地结果，原请求缺少上游工作量门，短日期多证券/指标或
长日期请求仍可能消耗过量cells。该发现保留，不以首轮137项通过替代修复。
新增回归先得到 **9 failed, 19 passed, 15 deselected**（5项通配/表达式拒绝，4项预算拒绝）。
修复后证券／指标只接受显式逗号列表；Host单次保守上限5000 cells，按证券项数×指标项数×
包含首尾的日历天跨度估算，取密前拒绝。该上限不是账户或供应商额度，不受结果limit影响，
周/月及SampleInterval不放宽，不拆批、截断、默认或删除参数；日志只含固定错误码。
新增5000/5001边界、长日期少项、短日期多项及weekly/sample反绕过；原混合body、未知字段、
反射、null、失败与字节保真测试全部保留。

本任务独立临时根 `logs/quantapi-history-budget-pytest-jyQpLF` 四模块 **148 passed in 0.68s**；
日志 `logs/quantapi-history-budget-green.log`、上下文 `logs/quantapi-history-budget-context.json`。
首轮历史冻结hash已被本修正替代，新的产品hash另行冻结供SPEC复核、质量评审及root受控Host验收。

P2修正后的冻结Provider SHA-256 `6d417ad7a16168dd379f63534879adc8f9cd089e331f33fa467462cb4dc32e90`；
numeric测试 `29eb5624973058deaea7f1c939b095b75f3fd196344689b7d893d64e19d898cb`，目录JSON仍为
`315139449c782eb78781d394b62cdb2fc8eb781e6bac7a50a186be98168ed8cc`。
148项日志SHA-256 `e3edf06206a8d397031f496c686483386e198596719f859b5f2736edb2d0c308`。
同新字节的L4 JS112项、完整16路径Constraints、docs/index与black/isort/ruff/mypy再验均通过；
最终候选与CI仍须在主线合流后重新绑定。
