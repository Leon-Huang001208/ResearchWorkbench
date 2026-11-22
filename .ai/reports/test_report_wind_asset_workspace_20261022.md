# Wind资产工作区实施与验证报告

最后更新：2026-10-22。任务：`wind-asset-workspace-20261022`。宿主为macOS Mac mini，Web功能开发；本机macOS、适用通用仓库检查和同候选Mac安装CI为本平台范围。Windows/Linux原生证据单列NOT_RUN。当前为实现/文档检查点报告，主任务在最终验证后补齐exact SHA、CI、浏览器、部署及收尾，不把本页当作最终通过证书。

## 批准范围与改动

完整批准方案保存在[实施计划](../../docs/plans/2026-10-22-wind-asset-workspace.md)。Wind平面工作区保留全部旧字段/卡片/资讯/个人功能；48px页头、200px筹码、260px指标栏，副图默认VOL＋MACD并可账号内保存0至4栏。筹码只按已载入日线截至所选日期前缀计算，独立于缩放视窗和周/月覆盖层，桌面Y对齐≤1px，手机允许下移且共用价格域。

新历史任务近期2自然年、向前4年或全部扫描；三种复权模式沿原DataHub/CJPY，封闭factor_macro三种series、每次≤500日期，逐日精确因子与上市日证明。原始块/因子不可变并绑定账号/观察/会话/配置版本；全累计规范行及metadata原子发布，缺因子/锚点/IPO、冲突或版本变化失败关闭。旧观察和旧冻结材料继续可读，交接复制raw/factor/canonical/metadata自包含证据。

新增6项HTTP API与Store兼容键，无DB迁移、运行时依赖或第二研究引擎。取消联动真实call_id，Future结束前排空；close/purge/recovery与常驻空闲覆盖任务和实际Future。未知witness不能视为空闲，已取消DataHub查询终态不覆盖仍运行的Future。

| 源码责任 | 对应验证 | 文档/图证据 |
| --- | --- | --- |
| asset_history.py / asset_history_jobs.py / asset_routes.py / asset_workspace.py / store.py / service.py | test_asset_history.py及原资产/Store/服务回归 | UI、DataHub、03文件、04API、02模块图、04数据流图 |
| DataHub adjustment_contract/contracts/catalog/providers_cjpy/broker/__init__/snapshots | 原test_datahub/catalog/cjpy/broker及history回归；独立私有预检 | DataHub、03文件、API Atlas和架构映射 |
| UI app/core/controller/chart/workspace | 原JS图表/工作区回归；实际浏览器另验 | UI、README、批准计划 |
| main.py / resident model_provider_upgrade.py | 原resident/API/operator回归 | 常驻active和空闲证明合同 |
| 现有Checks Python清单 | 只追加本任务5个模块，无新job/runner/超时 | actions-budget、本报告；同候选Mac Bootstrap仍必需 |

## 已有检查点（不是最终候选全量验收）

- 已授权真实复权预检：18次调用，两只股票各676交易日及上市日；原报告SHA-256 `85fc23ae55255cdaec3e693753d4202c972a56ba29b9bd41b93750c273849cf3`，独立gate PASS；定义hash `76fb444109d027db7657b8baea96a4299b5d8ddb826aac7edc31dfb09df82fc5`。原始行情/因子/wire/授权仅在私有`logs/wind-adjustment-preflight/`，不提交。厂商原生前复权的精确全局锚点未知，不声明全市场/全历史或SDK保证，OHLC单位/币种未知。
- 上游执行者已报告Provider154、图表52、UI136例PASS，均为其阶段源码检查点；本报告没有将它们合并成最终SHA证据。
- 后端实现者回报history23、history＋DataHub86例PASS；`logs/wind-history-impl-files.json`绑定其源码清单。Ruff9/isort9、Black7及两新模块mypy `--check-untyped-defs` PASS。Store/snapshots全文件格式旧差异保留，只规范新增行；整体Provider mypy基线/候选均14项错误，尚需归因，不能称整体mypy通过。
- 主任务回报空闲相关359例PASS，`logs/wind-idle-green-3.log`；前两次测试插入位置NameError已修复并保留失败日志，原Origin/health断言未删除。
- 文档执行者已实际运行两图Archify validate/deliver，均showcase9/9、0错误/0警告；HTML与spec摘要由生成receipt绑定。两图visual-check四桌面视口均PASS，已实际查看各自1440深色/2048浅色最终截图并写入同hash复核记录；自动receipt的visualReview仍保留pending，不冒充产品UI浏览器验收。
- `check_doc_sync.py`最终PASS：80项变更的架构/API/图文检查无违规，文档治理783文件/100 current无违规，生成Python索引已核验。首轮缺少宽映射关联文档和同hash截图review的失败日志保留，补齐真实说明/截图核对后通过；没有放宽门禁。
- Actions只读API重新确认PUBLIC；最近5个成功基线run及实际持续时间已写actions-budget。它们不认证本候选CI。

## 本轮文档实际命令

日志目录：`logs/wind-docs/`。下表均为文档执行者实际命令和结果；上游实现checkpoint不冒充本执行者运行。

| 实际命令 | 结果及证据 |
| --- | --- |
| `node scripts/build_research_web_api_atlas.mjs` | PASS，`api-atlas-build.json`，按清单生成入口与API Atlas |
| `node /Users/leon/.codex/skills/archify/bin/archify.mjs validate architecture docs/architecture/research-web/diagrams/02-module-dependencies-final.json --quality showcase --json` | PASS，9/9、零错零警告，`02-validate.json` |
| `node /Users/leon/.codex/skills/archify/bin/archify.mjs validate dataflow docs/architecture/research-web/diagrams/04-data-file-flow.json --quality showcase --json` | PASS，9/9、零错零警告，首轮命令输出保留后复制到`04-validate.json` |
| `node /Users/leon/.codex/skills/archify/bin/archify.mjs deliver architecture docs/architecture/research-web/diagrams/02-module-dependencies-final.json outputs/research-web-architecture/02-module-dependencies.html --quality showcase --json` | PASS，实际spec/HTML摘要绑定对应`.receipt.json` |
| `node /Users/leon/.codex/skills/archify/bin/archify.mjs deliver dataflow docs/architecture/research-web/diagrams/04-data-file-flow.json outputs/research-web-architecture/04-data-file-flow.html --quality showcase --json` | PASS，实际spec/HTML摘要绑定对应`.receipt.json` |
| `node /Users/leon/.codex/skills/archify/bin/archify.mjs visual-check outputs/research-web-architecture/02-module-dependencies.html --json` | PASS，四视口及深浅PNG，同hash人工图像查看记录在visual-review.json |
| `node /Users/leon/.codex/skills/archify/bin/archify.mjs visual-check outputs/research-web-architecture/04-data-file-flow.html --json` | PASS，同上；产品页面浏览器验收仍独立 |
| `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py` | PASS，生成文档；后续`--check`由doc-sync执行并PASS |
| `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/check_doc_sync.py` | 首轮FAIL已保留；补齐后PASS，`doc-sync-final.log` |
| `gh api repos/Leon-Huang001208/ResearchWorkbench`、`gh api 'repos/Leon-Huang001208/ResearchWorkbench/actions/runs?status=success&per_page=5'` | 只读成功，PUBLIC及最近成功run原JSON留私有日志；无dispatch或rerun |

## 正式实现验收进展

- 真实全链经过 AssetWorkspace → DataHub → Broker → CJPY：兆易创新2261条（2016-08-18至2026-10-21）、贵州茅台6025条（2001-08-27至2026-10-21），各完成不复权、前复权、后复权。136次真实SDK调用全部返回且实际Future排空；逐日价格倍率、跨模式原始行和因子版本、量额保留及500条分页读全均已核验。主业务索引前后SHA一致，无凭据复制、模型调用或生产观察写入。许可数据仅留私有`logs/wind-live-history/`；汇总为`matrix-result.json`，有限两股证明不外推所有证券。
- Python独立评审APPROVE，23个文件绑定SHA；近处234项、摘要1项、resident27项及补齐取消夹具后的完整protocol81项均独立通过。数据摘要不携带数千条内部原始行/因子，完整冻结证据仍保存；未知任务、冲突状态及Future见证异常均保持非空闲。原Provider Mypy基线与候选同为14个既有错误，仅行号变化；新增模块定点检查通过，不宣称整个仓库类型检查通过。
- 正式静态资源的浏览器矩阵17项通过（含预览HTTP方法拒绝及旧快照首次扩展回归）：真实2261/6025条、三复权快照原子切换、实际大序列K线图元、0至4副图、鼠标和键盘历史选择、缩放/平移/周月不改变筹码截止日、三价格坐标误差≤1px、明暗透明与宽中窄屏、44px触控、旧10条兼容、来源和研究区域。错误及外网请求均为零。浏览器只回读真实冻结数据；任务轮询和偏好为明确的内存夹具，不能替代上述真实供应商链路。
- 完整JavaScript初轮870通过、2项既定跳过。完整Python初轮1699通过、29失败已保留：2处旧夹具缺新取消成员现已修复；其余失败来自复用环境中的包软链接或旧包，不削弱沙箱。改用现有实体依赖解释器、仅父进程加载测试库后，原生沙箱/冻结恢复/API相关216项通过，无新增依赖安装。完整Router仍为L4，17项本地门均已通过；原3项CI门仍待精确候选。wheel已与源码逐字节核对103项UI资源和新增模块，未引入依赖。

## 尚未验收与风险

首轮集成候选`9265e69`的Constraints和macOS干净安装已分别通过39717416229、39717416234；实际checkout为`0d48d9f`，父提交为5495与9265，同tree已由本地Git对象验证。Checks39717416265唯一失败为目录HTTP测试未显式注入MCP内存凭据后端，Ubuntu没有系统钥匙串；1716通过、11项条件跳过及失败日志完整保留。修补只改该夹具，机械拒绝系统后端后仍保留所有原断言，119项相关测试及独立评审通过，不放松生产凭据边界。

切换前另发现旧10条快照首次向左扩展应先建立规范版本；前端现将该首次操作转为独立近期构建，旧行/日期/标签保持到新版本原子替换，有规范版本后继续向前扩展。新增行为回归通过；修补沿原PR重新验证，不将旧候选Mac通过冒充新候选证据。

纠正测试环境后的首次完整Checks Python为1728通过及7子测试；修补相关119项、全JS871通过/2既有跳过、图表61项与浏览器17项均通过。17项本地Router按修补候选重新闭环，同候选通用CI与macos-14干净安装仍须取得精确候选证据。隔离交互预览已打开，常驻仍为5495基线，未部署；用户本轮已明确授权部署，但须产品合并后交付正式固定版本profile，持锁复核空闲、账号和业务数据保全再切换。Windows/Linux原生、CI及真实安装未执行，保持NOT_RUN。资源收尾未执行，不能标cleaned。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"Wind平面工作区和持久历史任务/账号偏好API消费已同步UI合同，既有模块图资产服务扩展为任务及偏好，DSH不变。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"workbench","structure":"changed","reason":"新增持久历史任务与固定锚点规范发布，模块与原始块/因子/规范快照流已更新既有02及04图，旧观察继续可读。","diagrams":["02-module-dependencies","04-data-file-flow"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"天软factor_macro只开放三种封闭复权查询，真实Future排空和自包含因子/原始数据交接已同步模块及资料流图。","diagrams":["02-module-dependencies","04-data-file-flow"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"新增六个历史任务和账号偏好端点，resident活动包含真实Future/任务；API清单与Atlas、02模块图已经同步。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"Store兼容添加历史任务/幂等索引/账号偏好，账号不可变缓存和规范快照保全写入03与04数据流图，无数据库迁移。","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service共享关闭流程加入历史任务排空，不改变Automation唯一调度、日程、触发和外发归属，原自动化图拓扑保留。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"既有Host活动和操作员空闲证明增加历史任务及真实Future，安装入口/依赖/进程/端口和部署事务不变，无新增运行节点。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"复用既有账号Store和Host，操作员读取明确任务及Future空闲；网关/身份/私网来源/凭据隔离不增加部署节点或权限。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅将本次测试模块加入现存Research Web Checks，不增job/runner/timeout或依赖；平台归属和同候选Mac安装门保持。","diagrams":[]} -->
