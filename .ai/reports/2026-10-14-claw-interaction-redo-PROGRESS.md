# Claw 交互布局重做与真实验收

宿主 Mac mini/macOS，功能开发。独立 worktree codex/claw-interaction-redo-20261013，从最新远端基线 c1bcd0992（PR101）开始，保留 FinGPT 与 Docker 凭据修复。

参考证据：已登录 Chrome 的「创建定时任务：每日收盘点评」对话，scheduled_task_list/AskUserQuestion/create/update 与两次请求试跑、Agent 日程真实表格；不复用 AlphaEngine 报告或成功数。目标参考 MON-FRI 与“仅周一、周五”摘要不一致，本产品明确按星期集合，不称交易日历。

实现直接 research_task、同 ID 预期版本更新、多星期日、不可变运行快照、创建启用失败可重试及删除重放保护。聊天原生工具经现有私有控制入口，研究执行独立 DSH 会话，逐工具与资料范围核对；没有第二研究引擎或调度层。修正导航容器契约、可见展开焦点与独立 Agent 日程。

已授权任务测试依赖与候选公开安装/Keychain 复用。候选数据根 acceptance/claw-redo-20261013，18190/13190。公开安装已通过固定 web.lock/DSH 构建。原 start --json CLI 参数错误未执行启动，改正式参数后健康；立即重启曾端口释放未结束而拒绝，未知监听未接管，确认消失后重试。

真实模型已提出原生缺参问题并根据回答准备日程卡；发现回答成功后旧问题未清除，已修复并补回归。真实创建、同任务版本修改及 v1/v2 两次成功试跑已取得原生完成、非空回复和真实文件证据，历史失败记录保留。金融数据源状态与收盘点评覆盖仍受限，合成测试不能代替。

本地 Automation 74 PASS，UI JS 405 PASS/1 既有跳过；根集成首轮94 PASS/2 skip/1 Word失败，定位测试解释器沙箱包路径，使用公开安装产品解释器后聚焦8 PASS。最终完整 Router/质量/文档/真实浏览器验收与绑定提交 macOS CI 仍待执行，未宣称完成。发布、合并、部署保持独立授权；Windows/Linux NOT_RUN 交接。

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "复用既有 Web 私有控制、DSH 原生工具与 Automation 执行；增加同模块契约和投影，无新执行引擎、节点或跨宿主授权。", "diagrams": []} -->
<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "复用既有 Web 私有控制、DSH 原生工具与 Automation 执行；增加同模块契约和投影，无新执行引擎、节点或跨宿主授权。", "diagrams": []} -->
<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "复用既有 Web 私有控制、DSH 原生工具与 Automation 执行；增加同模块契约和投影，无新执行引擎、节点或跨宿主授权。", "diagrams": []} -->
<!-- architecture-review {"group": "capabilities", "structure": "unchanged", "reason": "复用既有 Web 私有控制、DSH 原生工具与 Automation 执行；增加同模块契约和投影，无新执行引擎、节点或跨宿主授权。", "diagrams": []} -->
<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "复用既有 Web 私有控制、DSH 原生工具与 Automation 执行；增加同模块契约和投影，无新执行引擎、节点或跨宿主授权。", "diagrams": []} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"现有 public-data 私有通道复用日程控制；资料来源与工具限制仍由同一 DataHub Broker 和准入核对，无新 Provider 或调用路由。","diagrams":[]} -->

全目录扩展回归首次 3400 PASS/11 FAIL/10 SKIP（2235.72秒），失败已定位并逐项修复测试夹具/断言，不跳过、不放宽生产边界。工具目录现36项、Skill30项和显式data_requirements字段；旧沙箱测试必须声明所选资源read_paths。Framework解释仍正常，但未声明DataHub合同的内置验证能力保持409/待配置，测试不再把创建preset当作可执行证明；本轮未静默修改内置能力或迁移专业数据授权。Docker加密算法单元在模块内隔离模拟平台，Mac实际CLI后端拒绝另有证明，Linux原生仍NOT_RUN；安装fixture使用真实空闲端口，不探测8088/3081。

真实证据v1：run automation-run-26f89ff629f6491f8aa71fe832d6dabe，DSH session 9afbf684-3bf3-480c-92a6-da7b1349c78e，原生turn/end completed、非空回复、12980字节Markdown，SHA256 dcb97c4b4724091f2aa3db6957a9773cbdaad5e9dd94dd08c4d87cf72b693d9d。同任务已更新v2，时间/时区/模型/权限及next_run_at逐项保持；v2第一次未生成文件，记录session_incomplete，不能冒充通过，继续修正文件生成指引并显式试跑。

独立评审复现两个HIGH：并发v1更新产生两个v2；历史目录失败被展示容错后仍允许执行。已用共享定义RLock/CAS及严格send原生校验修复，并禁止受限会话完成认证。83 Automation测试通过，真实布局网格现352px/928px，侧栏x0、主画布height656；新级联测试覆盖旧高特异性规则。

真实证据 v2：run automation-run-254722ddc3d840f2b9a98cf389686981，DSH session 40820bb3-86b3-4d72-828f-89b83554abfc，定义版本 2，原生 turn/end completed、非空回复、真实 Markdown 12859 字节，SHA256 f0e9019ae4f20e5be0568478ad1c3020dbfb05aed9940fe586696027b734212e。副本字节数与摘要已独立核对，证据为 acceptance/claw-redo-20261013/evidence/trial-v2-native-proof.json 与 A股收盘点评_2026-10-14.md。研究执行与文件交付通过不代表金融内容覆盖通过：指数数据缺失、未识别资产不得冒充指数、T-1 日期表述错误仍记录为受限；本轮不宣称完整金融 PASS。

本地完整性收口（2026-10-14）：当前完整 changed set 58 路径，Router 使用 `node scripts/plan_verification.mjs --project . --base HEAD --signal validation_failure`，保持 L4；受管 runtime manifest 所有文件 SHA256 匹配。13 条 fallback unknown_path 保留 unknown_impact_boundary，未修改政策或减少门禁。此工作区尚未形成新候选提交，plan schema-v3 是本地 Git 绑定检查，不认证未执行 CI；提交后须重新生成宿主 task plan/receipt。

实际通过：`node .agents/project-constraints.mjs --project . --changed-file <完整58路径>`、`node scripts/check_research_architecture.mjs --project . --changed-file <完整58路径>` 均 0 violations；`node scripts/check_documentation_governance.mjs --project .` 为 607 文件/89 current/0 violations；`python scripts/generate_py_file_index.py --check` 通过。Router L4 JavaScript 闭包四文件实际 110 PASS/0 FAIL；主代理 Router JS 总日志核对为 445 PASS/1 既有 skip。独立 fixture 三文件回归 206 PASS/2 既有显式授权 native skip；未新增 skip，Mac 上实际 Docker 凭据拒绝另有测试，Linux 原生仍 NOT_RUN。

上述日志统一保存在 `/Users/leon/.research-workbench/acceptance/claw-redo-20261013/evidence/`：router-plan-local-final.json、project-constraints-final.log、architecture-final.log、documentation-governance-final.log、python-file-index-final.log、router-verification-full-final.log。最新完整 Python Router 见下方继续收口记录；精确提交 macOS Bootstrap 与通用 CI 仍 NOT_RUN、无本轮推送授权，mergeReady/releaseReady 不得标为 true。Windows/Linux 验收由对应设备交接，金融覆盖另保持受限状态。

继续收口：owned launcher 原 4096 输出上限导致原生 max-tokens、空内容及无文件；固定有界 16384 后 v2 原生完成与真实文件交付。输出 overlay 回归先 RED 后 GREEN，完整 launch 测试134 PASS。旧截断运行保留失败，不修改任务定义/next_run_at，不自动重试。独立授权复审发现名称子串、跨任务及中文版本邻接漏洞，改规范问题的精确名称/ID/版本全匹配；独立4例通过，完整72例通过，补充“需要”正向/否定矩阵及最新完整 Router 仍执行中。

浏览器真实验收：1440桌面折叠后可见展开按钮且 Enter 恢复焦点；1050抽屉及 Escape、390移动侧栏和遮罩返回均无水平溢出。日程表显示同一任务v2、周一至周五15:30 Asia/Shanghai、已启用，手动v1/v2成功与旧失败真实分列。创建「每日收盘点评验收」项目、移入原对话及两个执行会话，聚合两个真实文件；明确选择原对话后引用v2文件，刷新仍保留附件。独立「归档交互验收」项目归档后可恢复。首页示例只填草稿，跨设置路由仍保留；浅/深色布局保存截图，Claw能力页仅选择并跳转能力中心管理连接。截图claw-home-desktop.jpg、claw-home-dark.jpg、claw-schedules-two-success.jpg及移动图存于候选evidence。

首次输出预算 Router 已结束892 PASS/1 FAIL/1既有SKIP，唯一失败是当时旧版本匹配漏洞，现已修复；修复后完整 `/tmp/claw-router-python-canonical-final.log` 为942 PASS/1既有SKIP/0FAIL（812.09秒），不以聚焦通过代替最终门。远端只读确认 PUBLIC、master 已前进到0cf38ff23（PR102历史模式修复），提交后须保留其改动并验证集成。

引用附件显示原source_name及来源会话/文件提示，真实副本ID不变。实际刷新发现原持久化仅保留id/name，补白名单保存有界source_name/source_session_id/source_file_id；不保存URL/path/未知字段，不改变attachment_ids。真实controller保存→重建→渲染→发送及无效字段回归通过，完整ResearchWeb JS421 PASS/1既有SKIP。旧副本没有来源展示元数据，不自动补造，需显式重新引用。当前只查询最新结果的原生对话已确认v2文件与七段内容、指出T-1缺陷，没有额外试跑或修改。

提交前最终本地：完整59路径的项目约束、架构、文档治理、Python索引全部通过；Router JS完整450项中449 PASS/1既有SKIP，日志/tmp/claw-router-js-storage-final.log。Python942 PASS/1既有SKIP；Ruff/Black/isort相关22文件、mypy10源码通过。Python与JS独立评审均Approve。原生Chrome参考并排截图因Mac锁定待用户解锁；候选IAB验收继续，未把参考截图标为完成。
