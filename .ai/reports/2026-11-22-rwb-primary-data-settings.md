# 主账号设置中的数据源入口

宿主：Mac mini／macOS；任务：主账号 UI 修复、原操作员通用完整候选入口及相关文档检查范围更正。已验证相关 JavaScript、隔离 Chrome 与局部操作员回归；Windows/Linux 原生、生产登录和实际部署分别待对应验收。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"本次仅将既有服务器可信主账号布尔值投影到页面，并缩小原样式隐藏规则的适用范围。沿用原设置路由与账号接口，不新增后端、权限、数据流、依赖或运行节点。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"既有Mac Bootstrap只补四个确切文件的PR/push触发和原步骤内的两个wheel资源字节检查，不新增job、runner、服务、权限、依赖、超时或其他平台执行。原安装、固定DSH、健康检查及Doctor流程保持。","diagrams":[]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"修正apply-ui候选交付目录，并在原version4双端事务中以显式前后版本表达通用已审升级，复用原资格、身份、账号业务保全、切换与恢复。未新增服务、账户库或部署框架，Host与Gateway职责和进程拓扑保持，对应网关模块说明已同步。","diagrams":[]} -->

根因：网关向登录页面加载的 `ui/server/profile.css` 无条件隐藏 `#/settings/data`，主账号展开设置侧栏后仍没有数据源。静态导航目录包含该链接不能证明登录页面实际可见。

界面只改两处：`session.mjs` 在加载该样式前，将现有严格布尔 `identityData.primary === true` 写入 `document.documentElement.dataset.rwbPrimary`；`profile.css` 只对非主账号隐藏数据源。其他隐藏规则与后端权限不变。两个相邻 VM 测试夹具仅补真实浏览器的 `documentElement.dataset` 形状，并增加四种身份的标记及加载顺序回归。

实际验证：

- RED：原实现执行 `node --test tests/javascript/research_web_multiuser_session.test.mjs`，既有用例 1 PASS，新增四身份用例均因标记为 `undefined` 失败。
- GREEN：Node 24.19.0 执行该文件及 `research_web_mcp_login`、`research_web_account_menu`、`research_web_account_workspace`、`research_web_module_navigation` 五个 `.test.mjs`，43/43 PASS、0 SKIP。
- Chrome 157.0.8103.79／现有 PlaywrightCore：真实 session、CSS 和 `renderModuleSidebar`，仅 `/api/server/me` 使用合成身份。原 HEAD 主账号不可见；候选主账号可见并点击进入 `#/settings/data`；普通用户、非主 admin、字符串 `"true"` 均隐藏。local/hot/operations/旧 plans/provider option 仍隐藏，模型设置仍可见。0 浏览器错误、外部请求及业务写入，浏览器与临时 loopback 服务已关闭。
- 独立 JavaScript 只读评审 APPROVE，0 P1/P2；其 10/10 相邻测试包含在上述 43 项内，不重复累计。`git diff --check` 通过。
- Bootstrap 局部静态检查：YAML 解析、PR/push 各四路径覆盖及其余工作流结构不变断言、5 段 Bash 语法、4 段内嵌 Python AST 均通过，独立只读复核未发现 P1/P2。检查脚本首次因系统 Ruby 2.6 不支持 `filter_map` 停止，改为兼容写法后通过；未执行安装或 CI。

本地浏览器证据在本任务 Scratch 的 `primary-settings-fix/result.json`、`primary-admin-settings.png` 与复现脚本。该夹具只证明页面可见性，不代表生产账号或后端权限验收。

安装契约已核对：`requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py` 和安装文档无需因本次无依赖、无安装步骤变化而修改。实际先验发现 Bootstrap 原 PR/push 清单各缺本次四个确切路径，覆盖断言 RED exit 1；现分别补齐，并在原静态资源冒烟 Python 块逐字节核对已安装 wheel 中 `ui/server/session.mjs`、`ui/server/profile.css` 与 checkout，复用原 `asset-static-smoke.json`，明确记录 `installed-wheel`。未新增服务、job、runner、权限、依赖、timeout 或他平台 dispatch；现有单用户 Host 不承担多用户 `/server-static/` 入口验收，生产 gateway 仍须另验。

正式 Router 对原四路径选 L4/full-delivery，两个测试留有 unknown-path 风险；新增文档及 workflow 后须按最终完整候选重规划。CI 触发已补不代表本轮 CI 已实际运行，Mac 干净安装、固定 DSH、3081/8088、Doctor 及 wheel 资源比较均仍待最终候选 CI。

原过宽模块映射曾要求同时改多份无关主题说明；现按已修正的既有结构评审规则撤回这些机械说明，只保留对应 UI、网关、文档合同与工作流说明和 README 复核。最终 changed set 以同任务当前受管候选为准。

显式网关准入另发现：`apply-ui` 误用 resident 的旧 `source_common` 查询候选 delivery，无法找到已审 `--source` 仓库中的回执。`research_workbench_entrypoint/resident/gateway_upgrade.py` 现只在静态 UI 模式用传入 source 的绝对 Git common 查询候选证据，普通 apply 和后续现役网关对原 `resident.source_common` 的身份比较保持；原日志、命令失败与资格错误传播继续复用。未修改运行配置、controller.pyz 或真实交付记录。

相邻新增参数化测试共两例，只在私有测试目录放置合成候选回执、模拟外部资格边界：旧实现两例均因误查旧 common 报 `resident_delivery_missing`；修复后正常候选通过交付和现役身份检查进入原 `verify_primary`，替换现役 common 仍在 journal／恢复安装／signal 前拒绝。正常例在该边界主动结束，不冒称整部署已通过；首次越出此范围触及旧夹具的 `.venv` 解释器假定后，已将测试限定回本次准入段，未修改解释器保护。

最终两条展开的 pytest nodeid 在原留存入口 `run --mode wip` 实际 2/2 PASS、0 SKIP，成功根已正常退休并回收 28672 字节。前一次 2 PASS 因只登记参数化基名一条而被留存计数核对拒绝，已用两条确切 nodeid 更正，不改旧回执；Ruff、Black、isort 两文件检查及 diff 检查通过。Python 独立评审已 APPROVE、0 P1/P2；最终候选 CI 由主任务接续，不把本地合成准入回归计作真实 GitHub 交付或生产部署证明。

源码提交、最终候选 CI、Mac 干净安装、受管部署及生产三身份复验仍由主任务接续；未在本报告中标为通过。未新增依赖、模型调用或全链路验收。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"本次仅按既有结构评审决定区分模块文档的适用范围，不新增评审字段、映射结构、服务、API或图形证据机制。已有有效unchanged说明且更新对应模块文档时不再要求机械修改全部映射文档；结构变化继续使用原全部文档与受影响图检查。","diagrams":[]} -->

局部操作员修复还暴露结构检查器把所有映射文档无条件列为必改项。现复用原 `architecture-review`：有效 `unchanged` 决定加至少一份该模块文档即可满足文档更新要求；缺说明、缺任何模块文档、`changed` 结构的完整文档及图要求保持。三项新回归在旧实现精确 RED 为 1 FAIL／2 PASS；修后与五项直接相邻回归合计 8/8 PASS（约0.49秒），未重跑已有381／188项结果。初次夹具增加文档映射后未重建目录输出，补齐夹具自身的原生成步骤后再取得上述精确 RED；未修改生成物检查或其他门。

## 已审完整版本的原事务入口

后续真实部署评估确认：旧 primary 的完整壳不能只靠 gateway 更新，最新主线又包含非 UI 产品变更，原固定 PREVIOUS/PAYLOAD 模式不提供任意已审完整版本的入口。沿用户在主维护聊天的完整部署授权，本次只扩原 `model_provider_upgrade.py`：增加 `apply-reviewed --expected-previous --expected-target`，使用单个通用模式及原 version 4 事务，不新增控制器、服务、恢复框架或每提交固定 profile。

显式前版绑定现场 accepted、manifest、baseline、两端实际版本；目标绑定干净 source HEAD、当前 master 和原 GitHubEvidence 完整树资格。前后树及 source 仓库身份冻结于原 journal，Operations 的切换、启动、校验及恢复均取本次动态值；旧历史模式和其枚举保持。候选回执取候选 common，两个 release 各自 common／inode／origin 保持核验。原 wheel、账号、模型、业务索引、恢复包及锁内前版复核继续使用，MCP／AlphaDesk／私网路由不借升级改配；依赖锁与固定 runtime 声明不同则拒绝，不安装依赖或切 DSH。

TDD 首批 10 项在旧实现因缺命令／参数失败；最终同批 16/16 PASS、0 SKIP（1.41秒），覆盖真实 Git 完整树与依赖变化拒绝、参数缺失／放错命令、前版／目标／资格拒绝、原 operate 与 recover 读取动态值、真实独立 release clone 的 journal 身份及 accepted／manifest／baseline 篡改拒绝、原 Operations 的双端前进／失败回滚、当前 MCP／AlphaDesk 及已存在私网服务路由保留、旧固定模式兼容。GitHub、模型和 OS 启停使用隔离替身，不把测试输出的 `deployed` 当生产已部署；成功根经原 `run --mode wip` 正常退休，回收1368064字节。早期绿色验证中的夹具健康元数据／BirthFence transaction 及历史枚举兼容问题已更正，旧失败不计为成功。

实际生产 accepted／两端状态、最终 source 的 GitHub 合并与同候选 CI、空闲、恢复包及生产页面仍由唯一生产 writer 复核执行。本工作树未执行部署、重启、金融／模型调用、依赖安装或真实交付账本修改，未 stage、commit 或 push；Python 独立评审已 APPROVE、0 P1/P2，最终候选交付由主任务接续。
