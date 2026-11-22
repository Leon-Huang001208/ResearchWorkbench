# 插件固定包与现有能力中心集成验收

宿主 macOS；Web 功能开发；隔离 worktree datahub-plugins-20261022，基线 5de7e5f2db95b8b501905af9cfdc30e8fe84db0b。只做本地候选与自有夹具；不 push、prepare、merge、部署、安装依赖、复制秘密或调用真实模型。父任务独立负责 DataHub，插件分支未修改 public-data.mjs/依赖/CI/现有服务或外盘。

## 变更与证据

| 源变更 | 测试 | 合同与证据 |
| --- | --- | --- |
| plugins/packages/service | test_plugins.py：四种格式、恶意归档、immutable摘要、精确权限、原生目录、旧会话pin/升级/撤权/回滚 | docs/research-web-plugins.md；能力与文件合同 |
| plugin_routes、multiuser/plugin_routes、proof、tenant_policy | test_plugins_mcp_security.py 与多用户/原MCP回归：真实角色、限定签名/nonce/owner/body、旧token/未受审安装/非原生边界拒绝 | API Atlas、真实临时AccountStore浏览器证据 |
| mcp_policy、mcp_runtime/service、launch_runtime | 原MCP安装/会话grant回归；实际artifact/config/schema改动失效；mcp=None延期反例 | MCP原生确认/OAuth/grant没有替代；外部供应商未调用 |
| runtime_restart、RuntimePool、main/service | test_plugins_runtime_restart.py：真实自有无害子进程、活动/未知deferred、出生冻结、generation、超时/恢复/丢响应、幂等 | 双阶段回包释放租约后冻结，仅Pool自有PID；未知保留fence |
| sandbox_runner | test_plugins.py：独立Seatbelt、拒绝越界/网络、bounded取消/deny、固定脚本摘要 | macOS builtin-only Shell子集；其他平台unsupported；没有第三方脚本 |
| runtime/plugins.mjs、guard、mcp-adapter | research_web_plugins*.test.mjs 与 multiuser policy；固定DSH ToolRuntime真实注册/output schema、经原守卫嵌套subagent离线执行 | 无第二Agent/模型引擎；实际固定DSH 7ecf564f2e09b829240c5553687223bdd1e2df73；不发模型请求 |
| capability-workspace/plugins-workspace/core/app/styles | JS控件回归与两个实际浏览器脚本：预览/默认未选权限/审核/启用/撤权/升级回滚/MCP原生链/管理员共享+个人/reader拒绝 | outputs/plugin-browser/evidence.json、server-evidence.json、01至05截图及source-manifest.json |
| architecture-map/checker/API Atlas/index | architecture checker原回归与新真实gateway直接mount正反例 | 静态检查仅承认真实CLI gateway+精确import/include，不豁免新API；生成Python索引 |

## 实际执行

- pytest 使用既有隔离环境 `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python`，从本 worktree 导入。`--confcutdir=tests/research_web` 经父任务批准，避免根 legacy SQLAlchemy 未安装；没有安装任何包。
- `python -m pytest --confcutdir=tests/research_web tests/research_web/test_plugins.py tests/research_web/test_plugins_mcp_security.py tests/research_web/test_plugins_runtime_restart.py tests/research_web/test_multiuser_runtime.py tests/research_web/test_multiuser_gateway.py tests/research_web/test_mcp_runtime_integration.py tests/research_web/test_mcp_runtime_routes.py tests/research_web/test_mcp_installation.py tests/research_web/test_mcp_authorization.py -q`：146 PASS，1条既有Starlette弃用warning。日志 /tmp/plugin-final-chain-pytest.log（最终源码复跑146 PASS）。
- `RWB_DSH_TEST_SOURCE=/Users/leon/.research-workbench/runtime/dsh/7ecf564f2e09b829240c5553687223bdd1e2df73 node --test tests/javascript/research_web_plugins*.test.mjs tests/javascript/research_web_multiuser_policy.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs`：44 PASS，0 skip；/tmp/plugin-final-js.log。
- 两个 `tests/e2e/research_web_plugins*_browser.mjs`，既有 playwright-core、自己headless Chrome、自己18991/18992夹具：PASS，pageErrors=[]，modelPrompts=0；/tmp/plugin-final-browser.log、/tmp/plugin-final-gateway-browser.log。正式AccountStore登录cookie验证admin/reader及个人owner拒绝。Gateway fixture的tenant backend复用单用户Native Host夹具/模拟DSH，**不声称完整真实tenant DSH启动或厂商MCP/OAuth验收**；独立Pool fixture测试承担进程/并发边界。
- 固定DSH离线注册是真实ToolRuntime+Cordis+SystemPrompt，模拟subagent不执行模型。Native MCP fixture是真实MCPRuntimeService/installer协议与bounded mock Host，无供应商网络/账号。
- 首轮测试命令误写不存在 test_mcp_runtime.py/test_tenant_policy.py，收集退出4，无测试运行；已纠正为上述实际存在目标并通过。首轮Black发现12文件格式问题，已运行Black修正后重查；不将失败覆盖成通过。
- 宽mypy首次发现本任务launch_runtime 1项可迭代类型错误已修；依赖遍历另有14项既有wind_adapter/providers_cjpy/hot_*错误，不改无关代码。最终 `mypy --follow-imports=silent` 对13个本任务源文件 PASS；完整依赖遍历14个既有错误保留。完整性结果在verification.json记录，未通过不冒充通过。

## 评审修复与支持限制

独立限定spec/JS评审原P1/P2已由父任务确认关闭：升级默认不等于撤权；仍批准旧版会话继续使用原Skill/Command/Agent/Hook字节，显式撤权即时拒绝。launcher mcp=None不再status AttributeError，旧MCP无法并存时明确deferred并保留旧pin。后端freeze已生效但HTTP回包丢失时以原freeze身份恢复，恢复不确定保持unknown与manager/backend fence，不假称rolled_back。

未实现任意Claude/Codex stdio命令、HTTP/prompt/agent Hook、未知宿主事件、闭源UI/cloud API；均在支持表受限/unsupported。MCP必须明确原生Registry映射，服务器OAuth回调未适配，真实外部OAuth和供应商MCP **NOT_RUN**。真实研究、真实模型质量、模型预算和数据语义验收 **NOT_RUN**。跨平台Windows/Linux Hook与安装验证 **NOT_RUN/unsupported**，不从macOS推导支持。

安装contract核对：requirements/web.in/web.lock、scripts/setup_web.py、setup-web.sh/setup-web.cmd和Bootstrap未改；没有开发者新全局包依赖。最终候选macos-14干净安装/固定DSH/3081+8088/doctor、通用Project Constraints和Research Web Checks仍由父任务正式交付，不把本机或旧SHA CI复用。Windows条件门交对应真机，Mac不dispatch。

初始自有浏览器夹具遗漏关闭既有Framework scheduler，启动过GoldCollector免费公开采集；发现后仅停确认证明的自有PID，之后三个scheduler启动方法在夹具进程内显式no-op，automations=0。没有真实模型/付费调用或现有服务变更；原日志 /tmp/rwb-plugin-browser-20261022-1718.log 保留。最终夹具仅绑定127.0.0.1，结束后只回收本任务进程，数据/日志保留可复核。浏览器截图旧失败诊断server-diagnostic.png为历史诊断，不列最新通过凭证。

## 架构结构判断

当前图的粒度为浏览器、API/Host、能力/MCP状态、每用户Pool与唯一DSH节点。插件属于这些既有节点内的受审资源/适配与固定控制路由，没有新引擎、常驻进程或网络目的地，因此保留原部署/模块/资料图拓扑；新增协议与不可变文件流在插件合同逐项描述、API Atlas按真实声明扩充，不伪造新图截图或套用旧截图证明新UI。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "插件适配位于既有浏览器、Host能力/MCP状态与每用户Pool节点内部，唯一DSH和既有服务/资料拓扑保持；新增固定路由、版本审批和冻结协议已由插件合同及API Atlas单独登记。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "插件适配位于既有浏览器、Host能力/MCP状态与每用户Pool节点内部，唯一DSH和既有服务/资料拓扑保持；新增固定路由、版本审批和冻结协议已由插件合同及API Atlas单独登记。", "diagrams": []} -->

<!-- architecture-review {"group": "mcp-runtime", "structure": "unchanged", "reason": "插件适配位于既有浏览器、Host能力/MCP状态与每用户Pool节点内部，唯一DSH和既有服务/资料拓扑保持；新增固定路由、版本审批和冻结协议已由插件合同及API Atlas单独登记。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "插件适配位于既有浏览器、Host能力/MCP状态与每用户Pool节点内部，唯一DSH和既有服务/资料拓扑保持；新增固定路由、版本审批和冻结协议已由插件合同及API Atlas单独登记。", "diagrams": []} -->

<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "插件适配位于既有浏览器、Host能力/MCP状态与每用户Pool节点内部，唯一DSH和既有服务/资料拓扑保持；新增固定路由、版本审批和冻结协议已由插件合同及API Atlas单独登记。", "diagrams": []} -->

<!-- architecture-review {"group": "private-multiuser", "structure": "unchanged", "reason": "插件适配位于既有浏览器、Host能力/MCP状态与每用户Pool节点内部，唯一DSH和既有服务/资料拓扑保持；新增固定路由、版本审批和冻结协议已由插件合同及API Atlas单独登记。", "diagrams": []} -->

<!-- architecture-review {"group": "documentation", "structure": "unchanged", "reason": "文档与API Atlas仍沿既有固定清单、安全阅读器与生成门，新插件模块和网关挂载仅增加既有清单项目，不添加文档服务、任意文件读取或新的图节点。", "diagrams": []} -->

## 最终收尾记录

- Black/Ruff/isort 对22个新增/修改Python文件 PASS，git diff --check PASS；实际执行 generate_py_file_index.py 与 build_research_web_api_atlas.mjs，静态API清单349项声明/346唯一操作。
- check_doc_sync.py、project-constraints.mjs、check_research_architecture.mjs 对完整改动集均零违规；documentation governance/文件索引包含在doc sync真实子检查。架构JS84 PASS；Router要求的架构/文档/Actions/跨平台契约/UI组合200 PASS；最终插件UI样式回归3 PASS。
- 最终浏览器日志为 /tmp/plugin-final-source-browser.log 与 /tmp/plugin-final-source-gateway-browser.log，根 /tmp/rwb-plugin-browser-20261022-final-source、/tmp/rwb-plugin-gateway-20261022-final-source；人工查看最新共享管理员截图，确认卸载文字可见。执行前所用源码和5张截图/2份证据JSON的SHA-256均在source-manifest.json。
- 已逐一核对确切Python进程参数和根路径后，仅SIGTERM自有fixture PID75502/75504；lsof确认18991/18992均无监听。没有停止任何现有RWB进程；私有临时根/日志作为复核材料保留，未称资源全部cleaned。
- Git安全入口check：/usr/bin/git、fsck PASS、无native locks、commonDirectory正确，原gc.auto=0/maintenance.auto=false保持。delivery --help无此选项，返回CLI_OPTION_INVALID且无Git动作，未执行prepare/publish。
- 现有Research Web Checks Python步骤显式枚举文件，尚未纳入新增三个test_plugins*.py；本任务遵守“不改CI”边界，父任务集成应把它们加入原步骤，无需新增job或依赖。新JS通配符可发现插件测试，固定DSH本地集成测试需RWB_DSH_TEST_SOURCE，未设时明确skip，不能把CI skip计为真实DSH通过。

广Router Python首轮726 PASS/11 FAIL/1 skip；11项均为本轮初始化兼容回归，未作为baseline忽略。已修dispatch只在tenant mutation读取运行服务；冷恢复缺省frozen状态兼容，模型凭据错误先于Hook。相关23项原目标PASS；完整广套件最终737 PASS/1 skip/1既有Starlette warning，313.24秒；日志 /tmp/plugin-final-router-pytest-rerun.log。11项原失败全部关闭。

额外将service/main/gateway也显式纳入 `mypy --follow-imports=silent`：16源文件中1项原service report_context索引类型错误（当前2094行，与基线同一未改语句）；保留FAILED_BASELINE，未以13文件定点PASS掩盖此扩展检查结果。默认依赖遍历最终实跑确认为6文件14个既有错误。

最终changed-set Router保守评为full-delivery/L4，完整改动集共76文件；本地必需组合737Py、146Py、200JS、固定DSH/插件44JS均已执行。外部CI、平台、模型与OAuth门保持NOT_RUN。最终只允许本地checkpoint，父任务在数据阶段之后按最新master重建Git-bound交付计划，合并后需重新生成合并API清单/Atlas/索引避免覆盖双方新增项目。
