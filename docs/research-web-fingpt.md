# FinGPT 三模式问答接入

FinGPT 使用 `app/research_web/fingpt/`，Claw 保留 DSH 任务和能力执行。此项按用户明确选择更新原“全部研究由 DSH 执行”的边界。前端为原生页面，复用项目导航、Markdown、安全文件 API 和主题变量；不依赖 AlphaDesk 服务或 iframe。

## 配置与诊断

受管 Node 已是现有 Web/DSH 安装合同的依赖，无新增 Python 或 npm 产品依赖。Host 依次使用 RESEARCH_NODE_BINARY、受管进程 PATH 的 node。公开安装器、锁文件和 Bootstrap 工作流保持原入口；干净安装兼容必须由 macOS CI 验证，不能以本机已有环境替代。

模型 ID 和 key 仅在 checkout 根 `.env.local`，gitignore 且 chmod 600；禁止 VITE_ 前缀，禁止进入前端、供应商错误日志或测试产物。Lite 使用 MIMO_API_KEY / MIMO_MODEL；Ultra 使用 MINIMAX_API_KEY / MINIMAX_MODEL；Frontier 使用 DASHSCOPE_API_KEY / QWEN_MODEL；可选 Kimi 使用 KIMI_API_KEY / KIMI_MODEL。各服务的兼容 URL 使用同文件配置，不在浏览器公开真实模型 ID。用户本次明确要求该文件存储，Claw 的既有 Keychain 合同保持独立。

`GET /api/research/fingpt/tiers` 仅返回档位标签及 configured；缺 Node / 配置读取失败返回稳定错误。`rwb web doctor --json` 增加 fingpt 配置诊断，仅返回四档 configured 标志和 generation_verified=false；宿主未就绪显示 host_not_ready，接口不可用显示 unavailable。configured 不等于厂商调用成功。不要把 DSH 的模型已配置视为 FinGPT 已配置。部署到另一 checkout 或 Docker 时必须在该目标私有挂载配置文件并验证；不复制凭据到镜像或 Git。

## API 与耐久性

- `POST /api/research/fingpt/sessions`：在本模式有效项目内创建；旧会话继续研究时校验项目、来源会话与显式附件引用，最多继承六条消息。
- `POST /api/research/fingpt/sessions/{sid}/ask`：quick / deep / agent；Lite / Ultra / Frontier / Kimi；Idempotency-Key 防重，冲突拒绝。
- `GET /api/research/fingpt/sessions/{sid}/rounds/{rid}/events?after=N`：只订阅既有回答；断线、刷新与切换页面不重发模型调用。
- 常规创建与发送 API 对普通新版 FinGPT 会话使用同一引擎；能力创建和自动化的显式 purpose 保留 DSH。指定 Skill / Workflow / 工具的任务请求引导至 Claw，避免静默忽略。

保留 setup、start_of_agent、step_start、tool_call/tool_call_result、_cot、_qa、answer_source，以及 update 的 intro/progress/file_op/work_note/summary/_final。Host 只接受白名单事件；SSE 帧有序号，round_end 表示宿主终态。单回答上限900秒、并发上限4、单行上限1MiB。停止与退出只终止自己创建的子进程；网页关闭不自动停止研究。

事件原子写入会话目录 fingpt.json（0600）；工作笔记与最终 Markdown 报告写入本会话 outputs。普通会话列表、项目归属、重命名、软删除和文件下载复用既有索引。永久删除使用本引擎的删除标记，不伪称删除 DSH 日志。

## 研究与资料边界

Agent 开场复述，拆分3–7项任务，逐项取数和写笔记，再反思复核，最后生成“一、二……”章节报告，按核心结论、数据分析、风险和来源组织，使用 [S#] 引用。优先 iFinD MCP / QuantAPI，其次腾讯与东财，再用公开源。0/100 分位及市值冲突必须交叉核验，不能确认就标口径存疑。

get_research_context 读取用户显式提供的附件、项目引用和已验证 DataHub 快照。文件属于本会话或显式旧会话；不扫描宿主。PDF前10页、Office有限工作表/段落、文字与快照最多12000字符；未解析内容不能宣称读过。资料中的指令不可信。既有 source_scope 继续限制上传、DataHub和联网工具。

快速与 Agent 使用同一个可折叠思考面板：运行中自动展开并显示旋转指示，逐块追加灰色推理流与「正在检索/完成检索」步骤行，思考完成后按钮变为已完成思考，面板可再次展开回看；单条回答只保留一个开关，不会重复渲染。Agent 另有子任务清单、任务运行中进度条、正在撰写报告状态、最终报告卡片，以及右侧 Agent 工作空间的文件与工作笔记两个标签。子任务推理在检索期间实时追加，子任务完成后收进该任务的「子任务思考过程」折叠块，完整保留而不是随笔记生成消失。任务预设在 Claw，点击只准备草稿，不隐式提交。

推理与正文都按小块实时出栈：出站过滤只保留足以拦住被拆开凭据的尾部长度，并在空白或中文断句处切分，因此思考过程在模型生成过程中持续显示，而不是等整段结束一次性出现。正文流同样逐块追加，并在生成时显示光标。

## 验证边界

真实 Lite quick / agent 先前各执行一次；迁移验证复用其已脱敏 SSE 回放，避免重复付费。新增 Host 集成测试使用真实有界 Node 子进程，验证 HTTP、SSE、归属、幂等、停止和文件交付，不能作为供应商实时可用性证据。macOS 干净安装 CI、目标常驻服务切换和 Windows/Linux 验收须分别记录真实状态。
