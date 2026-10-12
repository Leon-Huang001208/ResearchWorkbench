# 本机集成状态可信、Office受控自动验证、页面精简

## PROGRESS

### 当前候选与范围

- macOS Native + Web，功能开发；隔离工作树 `/Users/leon/.codex/worktrees/local-integration-clarity-20261009/ResearchWorkbench`，分支 `codex/local-integration-clarity-20261009`。
- base/远端master（开始时fetch并核对）`7d9d5a5cb9e95cdce88b5b9723ef48fbfc900a18`。当前候选为未提交diff（authorized-candidate.patch SHA256 `e74d102e9c144f978d09ecb9674a3190cecaf7a7733b624a19dd24135573d23b`，29个changed paths）；主树的未跟踪报告未动。没有push、PR、merge、tag、Release、依赖安装或生产升级。
- Harness task `local-integration-clarity-20261009` 已启动。受管runtime valid=true；仓库验收kernel manifest source `f853b1b268a1b39c537136d867ddf5a570f9730e`，14文件哈希无漂移。
- Node v25.9.0、Python 3.12.13。只读复用用户指定 `.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`；未安装、修复或修改该环境。

### 基线、修复与设计

- 8088 PID33651的cwd/app-dir仍为主树；主树HEAD `4a5e7523d7407525d108757727c64f10783203f4`。静态connections.mjs与主树摘要一致：`1467b8c1e78c02ee73a0665aedc5631513b1eedce8516c779698c116bd81626f`。结束时仍同PID/argv；3081未操作。
- 原汇总available=1/user_action=3/system_fault=7/not_delivered=3/total=14；明细同时显示Office三款与桥可用。已读基线，只读请求未触发真实验证。
- 原7项归因：Excel/Word/PowerPoint以当前有效真实证据为可用；Wind终端待验证；iFinD专业终端Mac不适用；Chrome待验证；Edge未发现。前三占位（文件夹同步、扩展配对、本地MCP）仍not_delivered，不建设、不假PASS。
- 修复：协调器与本机响应统一在协调器锁内获取、投影同一快照，携带scope/时间/local_revision；不接收外部旧快照覆盖。新增unverified/stale/not_detected/not_applicable，真实异常仍system_fault；失败时间不冒称成功时间。桥保留独立事实但仅计一项Excel能力。
- 本机scope与Office同意的恢复不读取DataHub目录/连接凭据元数据；data/all延迟恢复既有DataHub状态。新增禁用这两个入口的RED→GREEN测试。
- 自动验证仅扩展local:excel_app/word_app/powerpoint_app三个精确目标。同意绑定所属状态根；开启请求/启动批次使用既有串行任务，普通GET与POST probes仅发现。有效成功且清理confirmed才复用；每个目标/条件指纹一次，启动前持久化attempt，失败/取消/冷启动不重放。关闭取消本协调器登记任务，不启动后续目标；已有任务在同批次等待并复核，同意写盘失败不留下开启内存授权。
- 定义本轮“每轮”为一次明确开启/条件指纹周期：成功证据过期后不会单凭GET重做Office；需要明确动作或条件变化。Office默认24h、Wind最多5min不变。页面证据到期/重新可见只发状态GET。
- web-design-engineer采用Redesign Preserve：中性现有色板/系统字体/细边框、低动效，高密度；variance2/motion1/density8/assets2/fidelity10。分类实际过滤保留全部；九类统计换行；默认名称/单状态/短原因/下一步，四事实/时间/阶段/错误码/清理收详情。Excel桥作为组件详情，未交付/不适用折叠；Tabbit配置仅全部/浏览器分类默认折叠。
- UI同目标PUT串行、最新关闭意图优先；旧轮询在关闭/导航/刷新后失效。读取失败清除旧绿色但保留历史说明与撤销入口，不把授权未知显示成已关闭。Wind真实操作仍单独确认。

### 实机与证据来源

- 独立18088/instance状态根；真实local/integration API，DSH与其他目录为离线shell fixture。实际SPA加载候选/static，未请求真实模型/Keychain/厂商；未认证研究Runtime或其他平台。
- 启用前verification_runs=0；Office启用后三款各一次：Excel 03:46:50.348485Z→03:46:58.656865Z，Word 03:46:58.666100Z→03:47:02.437444Z，PowerPoint 03:47:02.445917Z→03:47:06.211754Z（本地11:46–11:47），均available且cleanup confirmed，串行无重叠。
- GET重复、冷启动后账本仍3；实际SPA分类过滤与关闭亲手执行，三目标consent均false、记录仍3。厂商/Wind/iFinD/模型实际调用0。后续候选调度/投影修正只复用这三份证据，不冒称又做了新Office实跑。
- **产物更正**：既有执行器成功路径会删除登记的测试文件和run目录（verifiers.py的finally/_remove_run_directory）。保留的是JSON账本、其中的阶段诊断与日志；没有保留三个Office文件。先前“合成产物保留”的措辞不准确，UI/文档已改为“验证记录/诊断记录”。不追加真实调用补证据。
- 验证器未修改，与base字节一致：verifiers.py SHA256 `ed6ef836686c1fdd27e027f6ed3f93ad1d6fd4c40e82e79c27ccddfb87eee54e`；workbook.py SHA256 `2e5a068592f43b5fd21e5bbedfacc1967e62fb0a80da787e1b2154d769f4fc45`。旧生产4a5到7d9执行器差异1631新增/63删除，旧生产实机记录未直接复用。
- 内置Browser连接因classic-level签名失败；未修签名/安装，改用CUA。重新开启的确认步骤CDP超时，后续读取/关闭测试标签同样超时，停止重复操作。CUA安全策略拒绝读取Codex原生窗口；未绕过，待用户手动处理。UI重新开启/弹窗/响应式未标PASS。
- 独立18088服务已精确停止；生产未改。没有killall Office、reset TCC、关闭沙箱、扩大目录权限、扫描用户文档或读个人工具配置。
- 证据根 `/Users/leon/.codex/visualizations/2026/10/09/01a11ea6-4b8a-7e71-9faa-bd15d81e8a51/local-integration-clarity/`；baseline.png为旧生产只读快照重渲染，candidate-spa-office.png为候选实际SPA分类后的截图。截图早于“保留记录”措辞更正。instance账本、after-ui-close.json、真实Office日志、失败日志、candidate.patch与完整changed-set计划均在该根。没有新增第二份任务报告。

### 全部授权后的继续执行

- 用户明确“全部授权放行”：允许本任务独立静态工具安装、现有执行器最小归档修复与新源码实机验收、候选发布及macOS/通用CI；不修改原只读复用环境、不接受系统权限弹窗、不扩大他平台产品任务。
- 已核对仓库PUBLIC、远端master=f8adae050900e2209bf3f10025b901dea692cdee；最近5次macos-14成功job实际耗时602/386/588/412/728秒，标准runner。
- 独立quality-tools安装ruff0.16.10/black26.10.0/isort9.0.2/mypy2.4.0；Ruff/Black/isort检查通过；同版本mypy候选与新master均59错误/21文件，无新增类型错误，既有债务不伪报全绿。
- 受管交付task integration-clarity-ship-20261009已start，fresh feature工作树位于原任务目录的ResearchWorkbench-worktrees/integration-clarity-ship-20261009，base=f8adae05；待本地候选commit后cherry-pick整合，避免覆盖主树。
- 归档RED测试已真实失败；最小修复后本机集成105通过/1既有Windows跳过。Office确认改成页内确认/取消，62个指定UI测试通过。新独立instance-retention根开启前真实记录0，已从实际SPA确认启动串行验收；各应用新源码每款只一次，结果待收据。

### 本次授权续接

- 复用原Harness会话，runtime verify无漂移、resumed=true。6文件补丁先git apply --check退出0，再实际应用。测试/证据复用：本次未改执行源码、不重跑Office、不延长证据TTL。
- 完整29个changed paths重验：Project Constraints退出0/0违规（0.210s）；文档治理退出0/0违规；Python索引check退出0；check_doc_sync.py --base 7d9d5a5c退出0，内含架构/文档治理/索引子门。git diff --check退出0。本次没有改执行源码、没有Office/厂商/模型调用；其余阻塞仍保留。

### 实际验收命令与结果

| 命令 | 退出码/结果 |
| --- | --- |
| 指定Python -m pytest --confcutdir=tests/research_web tests/research_web/test_integration_coordinator.py -q | RED 2失败/26通过；修复过程失败日志保留；最新隐私与版本投影修复后34通过（1.07s） |
| 指定Python -m pytest --confcutdir=tests/research_web tests/research_web/test_local_integrations.py -q | 最新104通过/1既有Windows-only跳过（20.53s） |
| 指定Python -m pytest --confcutdir=tests/research_web tests/research_web/test_integration_coordinator.py tests/research_web/test_local_integrations.py tests/research_web/test_service_manager.py tests/research_web/test_protocol.py -q | 隐私修复前503通过/1既有跳过/5警告（33.28s）；其后变更模块已分别重验，不将其合并冒称新整套结果 |
| node --test tests/javascript/research_web_local_integrations_ui.test.mjs tests/javascript/research_web_connections_ui.test.mjs tests/javascript/research_web_settings_ui.test.mjs tests/javascript/research_web_appearance.test.mjs | UI新增RED失败记录保留；最后当前可调用投影修复后61通过（94.27ms） |
| node --test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs | 修复后71通过（13.62s） |
| node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs | 176/181失败回执保留；最新181通过（13.54s） |
| node scripts/check_documentation_governance.mjs --project . | 0，585文件/88当前文档/0违规 |
| 指定Python scripts/generate_py_file_index.py --check | 首次1/stale；用户授权仅更新索引，生成后0 |
| changed Python AST / node --check changed .mjs / git diff --check | 0，通过；不冒称替代格式/类型检查 |
| 指定Python -m ruff/black/isort/mypy --version | 均1/No module named，未安装，静态检查NOT_RUN |
| node scripts/plan_verification.mjs --project . --changed-file（完整集合）--signal validation_failure | 0；L4/full-delivery，包含Mac bootstrap/通用CI/Windows交接，未裁门 |
| node .agents/project-constraints.mjs --project . --changed-file（完整集合） | 此前1（文档范围阻塞，0.216s）；获授权补齐6文档后最新0/0违规（0.210s） |

- 保留原测试；新增证明有效证据复用/串行/去重/失败停止/关闭/重启/归属/已有任务接续/晚到开启/清理未知/失败读取/到期刷新。成功fixture显式提供confirmed清理诊断；没有宽泛ignore、新增skip或降级policy/Hook。
- 用户已授权更新docs/generated/py_file_index.md。额外6文档的具体pending-doc-sync.patch已准备并打开；用户随后回复“授权”，本次仅按该具体请求应用6份文档同步，不扩展生产/依赖/发布/Office重跑权限。

## BLOCKED

1. **已解除文档授权阻塞**：用户已授权并应用 `01-system.md`、`02-research-runtime.md`、`04-api.md`、`08-research-frameworks.md`、`docs/research-web-tabbit.md`、既有readme-review.json同步；仅补齐此前具体补丁，Project Constraints、文档治理、索引和文档同步均退出0；文档授权阻塞已解除。
2. **静态工具安装阻塞已解除**：工具安装到本任务独立quality-tools；mypy同版本基线债务单独保留，未修改他任务环境。
3. **CI待执行**：用户已授权候选发布与macOS/通用CI；尚未取得最终候选新CI证据。hostAcceptance=BLOCKED，aggregateAcceptance=NOT_READY，mergeReady=false，releaseReady=false。Windows/Linux产品、Docker与桌面不由本任务补跑。
4. **environment**：候选浏览器确认步骤阻塞，Codex原生窗口访问被工具安全策略拒绝，待用户手动处理。UI确认重启旅程及响应式未通过。
5. **requirements**：Office测试文件未保留，现有安全执行器成功后删除；本轮白名单不含执行器，且每应用最多一次。不改执行器/重跑凑证据，该验收条件未满足。

恢复只读本报告PROGRESS/BLOCKED；依据实际授权/环境变化处理对应项。保留已通过的Office实机记录，先比对执行器源码和TTL，不重做真实调用来凑基线。Harness原blocked/permission失败历史保留；本次文档门PASS，任务因未授权CI等剩余项继续记录blocked/external；Goal未标complete。最终源与测试改动已保存，待授权/环境变化继续，不重复真实Office调用。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在既有协调器、同意存储、批次与受管Office验证器中收紧状态和权限；页面采用原生分类与折叠详情，没有新增研究引擎、宿主脚本接口、守护服务或部署节点。","diagrams":[]} -->

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"在既有协调器、同意存储、批次与受管Office验证器中收紧状态和权限；页面采用原生分类与折叠详情，没有新增研究引擎、宿主脚本接口、守护服务或部署节点。","diagrams":[]} -->

<!-- architecture-review {"group":"integration-coordinator","structure":"unchanged","reason":"在既有协调器、同意存储、批次与受管Office验证器中收紧状态和权限；页面采用原生分类与折叠详情，没有新增研究引擎、宿主脚本接口、守护服务或部署节点。","diagrams":[]} -->

<!-- architecture-review {"group":"local-integrations","structure":"unchanged","reason":"在既有协调器、同意存储、批次与受管Office验证器中收紧状态和权限；页面采用原生分类与折叠详情，没有新增研究引擎、宿主脚本接口、守护服务或部署节点。","diagrams":[]} -->

<!-- architecture-review {"group":"research-api-contract","structure":"unchanged","reason":"在既有协调器、同意存储、批次与受管Office验证器中收紧状态和权限；页面采用原生分类与折叠详情，没有新增研究引擎、宿主脚本接口、守护服务或部署节点。","diagrams":[]} -->

## PROGRESS（全部授权收口更新）

- 候选新增最小归档：登记沙箱文件通过source fd/目录fd/目标fd身份、UID、单链接、30MiB上限核验，归档到既有私有run目录后删除沙箱副本；目录替换反例保留源文件，未扩大清理范围。成功run沿原16/512MiB/24h策略保留，不重建执行器。
- 新源码实机三款各一次，从实际SPA页内“确认开启”启动，均available+cleanup confirmed；保留xlsx 8313 bytes、docx 13351 bytes、pptx 35316 bytes，ZIP有效，SHA与当前归档实现复核副本相等，权限0600。后续目录fd硬化没有新增Office动作，仅用这三份实际输出复核当前归档边界；不冒称硬化后又实跑。
- 实际SPA启用前零调用、确认后3项串行、关闭后记录仍3/同意均false；页内确认、取消与作用域匹配替代阻塞的JS原生confirm，确认焦点/取消焦点复原已修正。桌面图retention-desktop.png、390×844图retention-mobile.png；mobile scrollWidth=clientWidth=390，无水平溢出，viewport已reset。
- 最终本地当前源：Python506 passed/1既有Windows-only skipped/5 warnings（37.39s）；JS243/243（16.70s）；Ruff、Black、isort、Project Constraints PASS。mypy候选与fresh master同版本均59 errors/21 files，无新增债务，仍不是全绿。
- 源执行器已变更，旧源码实机只作历史。新根instance-retention独立，原instance记录保留不迁移。厂商/Wind/iFinD/模型真实请求均0；产品服务未切换。
- 当前按受管交付start→feature commit/cherry-pick最新f8adae05→prepare→整合结果验证→PR/CI推进；Windows/Linux/Docker产品交接不由Mac dispatch。
