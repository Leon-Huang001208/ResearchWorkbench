# Research Workbench 研究界面、能力中心与实时架构实施

## Spec

依据用户 2026-09-03 已批准的《Research Workbench Web：研究界面、能力中心与实时架构文档》。用户提供三张 AlphaEngine 截图作为布局参考。本文拆解实现与验收，不替换已批准范围。

## Global Constraints

- 工作树 `.worktrees/dsh-web-v1`，分支 `codex/dsh-web-v1`，起点 `304930d`；不覆盖主工作区。
- 保留原生 HTML/CSS/JavaScript、FastAPI 和 DSH。DSH 是唯一研究执行引擎。
- 不新增依赖、外部 MCP、在线技能市场、拖拽工作流、调度器、桌面适配或旧业务模块。
- 不变更模型、执行上限、沙箱、原 3080 实例及秘密配置。会话和生成文件不得伪造。
- Workflow 是步骤式研究模板；Skill 来源为产品内置、对话创建、手动导入；Tool 只展示现有目录。
- 产品管理能力包及版本，DSH 原生发现调用。不得虚构安装 RPC，不扫描宿主默认 Skill 目录。
- 新逻辑有错误处理、项目日志和回归；采用测试先行，记录 RED/GREEN。每批更新说明与实际验证，不能将待验收写成通过。
- 仅在此工作树内提交自己的文件，不合并、不推送。其他协作者可能编辑独立文件，不覆盖其改动，不递归委派。

## Task 1: 研究产品壳与布局

**所有权**：`app/research_web/ui/` 产品壳、输入框与研究详情相关 JS/CSS/HTML，`tests/javascript/research_web_ui*.test.mjs`，`docs/research-web-ui.md`，本任务 `.ai/reports/`。不编辑后端、架构主入口、全局 CHANGELOG。

阅读 AGENTS、docs/ARCHITECTURE.md、DEVELOPMENT_MAP.md、frontend 文档及当前 UI 模块。截图路径：`/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/codex-clipboard-5b3df224-3ab4-41d0-9ec6-eb097ce64cfc.png`（FinGPT）、`codex-clipboard-51362d6b-c11a-47c0-83cd-07961374b5e5.png`（Claw）、`codex-clipboard-98cdeaa9-1dad-4614-94a6-38405c481cfa.png`（能力卡片，同一目录）。

深蓝顶栏、窄主导航、浅二级侧栏、白研究画布；保留 Research Workbench 品牌。主导航 FinGPT/Claw/能力中心/历史，底部设置。顶栏搜索实际会话标题和能力名称/简介。可折叠侧栏显示实际最近会话/运行任务。FinGPT 和 Claw 独立首页：中央输入、四个真实研究 Skill 快捷入口和分类卡片，Claw 强调目标和交付。卡片只打开详情或放入草稿，不发起模型。第一批仍使用现有 Skill API，第二批用同一目录替换；不得用演示能力填充。

拆出 shell.mjs 与 composer.mjs 等有职责边界模块，不重写 SSE 控制器。输入保留现有附件、Skill、模型、格式，加入 slash 搜索、拖放/粘贴现有支持文件。右侧 Activity/资料/文件标签和抽屉；日志参数默认折叠，错误仍可见。Claw 会话/工作区切换只显示当前会话资料/文件。

保留现有路由、API、data selector 契约，SSE/幂等/草稿/停止/审批/子 Agent/刷新恢复/交付状态。新增交互可新增 selector，不移除已有测试依赖。禁止积分/会员/云端/免确认/7×24/日程。桌面 1440/1600/1920，平板/手机可操作；窄屏侧栏和面板改抽屉。编写交互/渲染测试与状态矩阵（默认/hover/loading/disabled/error/running/empty/keyboard），主控制器最后执行浏览器验收，不能把单元测试称为视觉验收。

命令：`node --test tests/javascript/research_web_ui.test.mjs` 及新增 UI 测试，`node --check` 改动 JS，`git diff --check`。完整 JS 回归一次：`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`。提交后写报告。

## Task 2: 能力包与版本后端

**所有权**：新 `app/research_web/capabilities/`、后端 `main.py/service.py/store.py/launch_runtime.py/runtime/` 必要接线、`tests/research_web/test_capabilities*.py` 与原生测试、`docs/research-web-capabilities.md`、本任务报告。不编辑 UI/架构主入口/CI。

建立独立能力目录、元数据、包安全、版本与发布服务。四个内置 Skill + 两个内置 Workflow；目录不依赖会话或 DSH 在线。Tool 目录取自原生注册/guard 白名单与 DataHub 声明，区分 Agent 内部控制工具和可选研究工具；显示参数、来源、审批、条件，不开放任何新权限。

API 集中 `/api/research/`：能力目录、详情、创建/复制/编辑草稿、导入（SKILL.md/ZIP）、检查、发布、停用、启用、版本、回滚、导出，以及只读 tools/workflows。中文元数据包含名称、简介、分类、输入、场景、格式。内置只复制不覆盖。版本不可变、资源只读，状态 draft/invalid/blocked_dependencies/enabled/disabled；名称冲突明确 409。

ZIP 压缩限制 10 MiB、展开 30 MiB、最多 128 文件，单文件 10 MiB；拒绝路径穿越/绝对路径/链接/嵌套压缩/安装钩子/二进制可执行文件；仅允许文档、图像、研究 Python 脚本与模板，导入不执行。保留文件和检查问题，不静默修复后宣称兼容。工具要求必须命中真实白名单；依赖不自动安装。恶意文件不可落到目标目录之外。

Workflow 包含名称说明、输入字段、有序步骤、关联 Skill/Tool、格式，编译为 DSH 原生 Skill 指令包；不建第二执行器。种子：基金资料准备与受限评价、公司资料研究与报告交付。描述为模板，不能假定真实步骤完成。

动态产品专属 native Skill 目录，默认 roots 关闭。发布/停用/回滚与提交使用同一互斥边界：任何活动回合（含子 Agent/恢复未确定）拒绝变更但保存草稿。不可变版本选择与会话只读资源一致。原有 DSH skills 会话内容不被新版本覆盖。使用经实际源码确认的 native discovery 机制，不新增不存在 RPC；如需重启专属 runtime，交给主控制器在空闲检查后做，自己不重启运行实例。

消息可选 capability_id/version，校验启用、版本、依赖，记录所用版本/资源。显式 expected_formats 优先，否则能力默认；保留 skill_id 兼容。对话创建：专用创建会话产出候选包，通过会话实际产物导入草稿后用户检查发布，绝不自动发布或执行包。

安全/协议测试覆盖 zip 风险、元数据、冲突、依赖/工具、历史版本、跨会话、并发发布/运行、离线目录、原生发现、Workflow 编译、格式优先。Python `python`；DSH `/Users/leon/Developer/deepseek-harness`。执行聚焦 RED/GREEN，再完整 research_web pytest（`--confcutdir=tests/research_web`）及 ruff/black/isort/mypy 相关检查。不安装包。

## Task 3: 能力中心前端闭环

**所有权**：UI capability catalog/detail/editor 模块、app/core 必要接线、JS 测试、前端能力说明/报告。消费 Task 2 实际 API，不再硬编码平行目录。

Skill/Tool/Workflow tabs；内置/我的、分类/搜索、卡片中文 metadata、状态、详情、技术 ID、输入和文件/工具要求。所有 landing/composer/cards 共用后端目录；离线可浏览已保存目录，不允许假运行。Tool 只读选择放入草稿，原生审批不变。

对话创建入口走专用创建会话，完成后可审查实际草稿文件并发布；表单编辑、内置复制、SKILL.md/ZIP 上传导入及报告，发布/停用/回滚/版本查看/导出均真实调用。Workflow 同套管理、有序步骤编辑（非拖拽）、关联能力和输出；运行展示预设步骤与真实活动分区，无执行证据不标记完成。

测试搜索分类/空结果/错误/禁用/运行中、危险 HTML、草稿与幂等版本引用、格式优先、导入检查失败/依赖不足/活动回合冲突、刷新持久；不伪造成功交互。主控制器做真实创建/导入/Workflow/文件浏览器旅程。

## Task 4: 文档一致性门禁与安全入口

**所有权**：`scripts/check_doc_sync.py`、新可移植 Node 架构检查、`.agents/project-constraints*`、`.github/workflows/project-constraints.yml`、检查测试、后端仅架构文档静态路由/设置入口必要接线及说明。不改其他 CI/桌面配置。

覆盖 research_web Python/JS/CSS/HTML/Skills/config，读取主控制器建立的 architecture-map.json。检查 changed source 要求对应 Markdown+review-record；结构未变允许显式理由。检查代码/API 引用存在、内部文档链接、图 JSON+HTML+哈希回执字节一致、视觉证据存在（不伪造人工通过）。CI 无需全局 Archify。命令支持离线仓库、临时 fixture；测试仅代码改动无文档、仅图源未重建、失效 API 必须失败。与现有本地交付及 project constraints CI 接同一检查。

只读架构 HTML 路由仅允许 `outputs/research-web-architecture/` 生成文件，路径穿越/链接拒绝，不暴露 Markdown 源仓库或运行时目录。设置提供入口。保留现有资料和 HTML 产物隔离。

## Task 5: 主控制器架构、集成与验收

**所有权**：`docs/architecture/research-web/`、`outputs/research-web-architecture/`、根 ARCHITECTURE/DEVELOPMENT_MAP 入口、旧 merged-platform 历史标记、CHANGELOG/最终报告。与代码实现者不重叠。

Markdown 覆盖部署/模块/API/DSH/能力/数据文件/安全/状态/验证；建立 source→docs→graph→API→tests 对应清单。使用 archify 生成八张图（部署、模块、研究序列、DataHub、能力生命周期、运行状态、交付状态、文档迭代）；每张 source JSON/HTML/hash receipt/showcase 9 checks 零错误警告、四视口和人工截图。图中每个节点关系落到实际实现，未知/计划单列。

执行真实浏览器视口与所有用户验收（四内置、对话创建发布调用下载、导入编辑停用回滚、Workflow、已有双 Agent/DataHub/审批/停止/交付回归）。单元/静态/完整性/Harness 门禁；保留当前本地 URL、新会话与文件及未通过项。全部必需验收通过才称完成，不重跑旧数据付费/授权请求、不自动批准未授权网络请求。
