# 市场综合总览封闭部署操作员准备

日期：2026-11-06。宿主：macOS／Mac mini 开发职责；类型：功能开发与已授权常驻部署准备。
本报告只认证本子任务实现和静态检查，不认证部署成功；实际测试、评审、CI、现场切换与浏览器验收由根任务聚合。

## 固定身份与范围

- 产品检查点：`a2ee934f026d9f174d948a2f748213d0d5021f5b`。
- 新前版：`5ffecb5219d46a5d3e4148a4ddb630f23a09ab3b`，现场身份由根任务只读核实。
- 新封闭入口：`apply-market-live`／`reviewed-market-overview-live-v1`。
- 原 EVENT 的全部既有常量及 review_assets 组合祖先分支经 AST 与 HEAD 比较保持不变。
- 实读锁文件 SHA-256：`7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`；evidence：`193f4fcc7e27ab1fd9fd87c4d30a0ca200476fe74c6cc4c6c7dad6bb8ce63988`。

## 实现与保护

复用原 version4 三锁、BirthFence、业务索引／全账号 @events 原件保全和恢复。
新 closed family 仅扩展到市场 live 身份，复用日程关闭／冻结原件、Native 严格列表、Host／后台／Workflow／market inflight 空闲门。
目标配置持久 false，双 health 检查实际 MCP 严格 false 与配置／进程出生身份稳定；旧配置原样回滚。
review_assets 同时验证固定前版→产品→最终工具目标祖先关系和两份 diff 的路径并集、blob、文件模式。
仅 MODULE、TEST、docs、.ai/reports 允许产品检查点后的变化；额外 app/scripts/tests/README/outputs 均拒绝。
不修改 controller、evidence、依赖、账号、数据、模型、历史；不启用采集或 MCP，不进入 TRIAL。

## 验证记录

- PASS：共享环境 --check --json，healthy=true；无依赖安装。
- PASS：实际 Git merge-base --is-ancestor 5ffecb5219d46a5d3e4148a4ddb630f23a09ab3b a2ee934f026d9f174d948a2f748213d0d5021f5b，exit=0。
- PASS：两 Python 文件 ast.parse、旧 EVENT 固定常量及祖先分支 AST 比较。
- PASS：black --check、ruff check、isort --check-only，仅本子任务两个 Python 文件。
- PASS：git diff --check。
- 首次 ruff 发现参数化改动后的 unused fixture system 变量，已改为 _system，随后检查通过。
- NOT_RUN：pytest，按根任务要求由唯一最终批次统一运行，未建立临时 pytest 根。
- NOT_RUN：独评、最终 exact-SHA CI／Mac 干净安装、实际常驻切换、认证页面验收、资源收尾；不冒充完成。
- NOT_RUN：Windows／Linux 原生，交由对应设备。

## 测试设计与静态规模估计

原 ASSET_PROFILES 加入新 mode：覆盖真实 Git 并集／回退／模式、全账号索引、前进失败／回滚／恢复、独立 release clone 和配置保护。
13 个 EVENT 实际运行／MCP／恢复 test 函数参数化至两个 mode；旧 EVENT 专属祖先链测试仍只验证旧身份。
另新增新 profile 固定身份、10 项真实 Git 拒绝案例和操作员／文档允许变化正例。
按 AST 顶层参数装饰器静态估算，本文件原 2829 个 case → 2984 个 case（+155），35 个函数 case 数变化；此数字不是 pytest collect 或执行回执。

## 子任务文件 SHA-256

- `research_workbench_entrypoint/resident/model_provider_upgrade.py`: `a85571a93143e25f3b7085b46284a220bd25b683afc8afb8a3830212681d4a0a`
- `tests/research_web/test_model_provider_upgrade.py`: `1d238fcfc0c96295ba4773fd94c7b23728b2b9f2cf0c8c78159fdcdd320359be`
- `docs/research-web-gateway-upgrade.md`: `566cbc7ffb0ac5162af2150c3ff9f3fe985a37bd4c2aa47ab5f018c411c21bc6`

## MARKET_LIVE 回滚 MCP 门修补（2026-11-06 后续）

发现旧 EVENT/db2 的缺字段回滚兼容不应扩至已支持 MCP health 的5ff前版。
仅新增封闭 MCP_DISABLED_ROLLBACK_MODES={MARKET_LIVE_MODE}，不引入未合并NAV模式。
operate 初始读取、validate_configuration、validate_state 共同验证旧网关配置字段严格 false；
MARKET_LIVE 前进和回滚均读取 local/private 实际 health 并要求严格 false。
原加载／PID／出生身份／源码／配置前后观察窗不变，旧 EVENT/db2 回滚缺字段豁免完整保留。
本次所有既有 PREVIOUS／PAYLOAD 及 EVENT_* 常量与 HEAD 的 AST 比较保持不变。

LIVE fixture 原配置显式 false；原缺席断言仅保留EVENT。
新增4项旧配置恢复拒绝、8项双health回滚拒绝，以及依托原weekly fixture的8项实际operate旧配置拒绝。
旧 EVENT 缺字段回滚与 LIVE 成功回滚false保留复用原双mode正例。
Black/Ruff/isort及AST通过；没有提交、远端、生产或依赖操作。

正式WIP批次 mcp-rollback-strict-false-wip-v1 实际失败，不能声明测试通过：
pytest exit=4，0 tests ran，原因是新增operate测试节点漏写weekly_operate_protocol固有v1/v2参数。
--collect-only已确认实际节点为 reviewed-etf-weekly-admission-v1-missing 等8项；未执行fixture。
失败原件及唯一root保留，未新建第二root、修改回执或尝试覆盖失败证据：
- logs/market-live-mcp-rollback-wip-20261106.json
- logs/mcp-rollback-strict-false-wip-v1.{stdout,stderr,xml,result.json}
- /private/tmp/rwb-market-live-tests-20261106/rwb-test-market-overview-live-20261106-tofluf1w
- nonce: 3600f7c625ef4cafa16361eea58b43d1
后续测试恢复交由根任务按正式协议处理；本补丁执行验收仍 BLOCKED，未代替新候选独评和CI。

本次静态冻结摘要（下列文件后续变动需重新认证）：
- `research_workbench_entrypoint/resident/model_provider_upgrade.py`: `b76489fc670caf7b8e49c17cd2dbdea584603876f3f95d637994f022ac75d25f`
- `tests/research_web/test_model_provider_upgrade.py`: `492248d5f08f9c6d80f875061a1d1833c7a95ab13841090b3bbb24759691cdb4`
- `docs/research-web-gateway-upgrade.md`: `fcdedeb5e0dccf3908bf4b08e80ced9cd38462135fa423ac2130889b6a7a3ace`

### 唯一WIP lease 同源恢复准备（未执行）

仅新 test_market_live_actual_operate_rejects_old_mcp_before_prepare 缩定fixture范围：
联合 weekly_bridge,bad 参数固定原weekly-v1有效seed，ids为missing/None/0/True。
本测试显式执行MARKET_LIVE且在任何weekly/prepare前拒绝，因此weekly v2不是负例变量；
所有既有weekly/EVENT矩阵、产品模式及实际拒绝断言保持。
真实collect-only exit0，逐字比较原receipt的20 nodeIds，数量、顺序、selector完全一致。
证据：logs/mcp-rollback-wip-original-selectors-collection.stdout／stderr。

同root恢复草稿：logs/market-live-mcp-same-root-recovery.draft.py，尚未运行。
草稿固定原candidate95c714、receipt、root、nonce及20node；校验并保留原exit4／0run原件和owner字节／stat／hash。
仅在已核实原root只有owner且无占用时，归档RED原件并复用该root真实运行原20节点。
green输出位于原receipt.parent子目录，通过原admit_batch／retire_root处理；不修改selector或伪造JUnit。
900秒、512MiB根、64MiB输出、3GiB空间门保持；operator/test/retention及runtime.venv身份前后复核。
执行仍待根任务审查，当前测试接受状态仍BLOCKED。

### 根任务执行结果

根任务已审阅该恢复脚本并执行：原20个 selector 的真实 pytest 结果为20 PASS、0失败／跳过，
退出码0。原RED原件与nonce保持，修订仅纠正这条新测试的fixture范围；实际JUnit名称逐项与
原请求一致，未改断言或既有weekly/EVENT矩阵。原admit／retire协议已将同一root正式退休。
最新测试源码SHA为 `84ca3450b3f3c978a1f5e8b0f8ce9b4aeaea87b6237b6faddf321ca5ee0d4e92`。
此结果是95c714上的WIP修复证据，不代替后续NAV/LIVE合流后的独评、exact候选或CI。
