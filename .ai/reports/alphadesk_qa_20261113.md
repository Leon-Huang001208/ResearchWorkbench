# AlphaDesk AI 问答迁移

2026-11-13，Mac mini，Research Web 功能开发。来源为 AlphaDesk `1c946b9a0930d3070da7263ffcffe5e8831077c3`。用户确认可将问答源码提交公开 RWB。开发在受管任务 `alphadesk-qa-20261113` 工作树进行。

## 验证记录

| 检查 | 实际结果 |
| --- | --- |
| `node scripts/git_safety.mjs check --project /Users/leon/Desktop/Projects/ResearchWorkbench` | Git fsck PASS，未见锁 |
| `node --test` 问答、现有 Web UI、Docker 合同、架构、文档与交付路由相关套件 | 324 PASS |
| `python -m pytest tests/research_web/test_alphadesk_qa.py tests/research_web/test_fingpt_dsh_fusion.py tests/research_web/test_discovery_tracking.py tests/research_web/test_report_delivery_links.py` | 53 PASS。初轮有一例流式夹具短于追问标识缓冲，调整夹具后通过 |
| `python -m pytest tests/research_web/test_alphadesk_qa.py` | 增加费用预留和原生 Markdown 交付后 6 PASS |
| Node 24 锁定安装、TypeScript、Vite、实际 wheel 与 ASGI 静态资源核对 | PASS，公开资源与已构建文件逐字节相同 |
| `node tests/e2e/research_web_qa_browser.mjs` | 隔离 Chrome PASS，合成 API |
| 独立源码评审 | 发现流式桥、作用域和质量回执阻断并逐项处理，最终候选仍需复核 |
| Mac Docker Desktop 受管构建 | 第一次发现已登记控制镜像缺失，`./rwb-docker bootstrap` 恢复控制镜像。第二次在 DSH 依赖安装阶段因宿主空间降至约 600 MiB 主动中止，退出 130 |
| 受管 Git prepare | `DELIVERY_FAILED`，记录为 `integration_failed`，Git 退出 128；尚未创建 PR |
| 同候选 GitHub CI、真实模型与数据、常驻切换和回滚 | NOT_RUN |

## 续接验证

- 三档真实 DeepSeek 问答已返回合成资料引用。原账本为 24 次、48.796 元预留，当前缺少可归因的原始用量。新账本逻辑保留旧预留，只有身份一致并完整结束的官方流可按用量计算峰值费用上界。未核价的外部数据请求保持待验。
- 合成冻结快照已通过 Host 质量检查并完成 Markdown 下载，通知监视器使用该报告得到 `meaningful_change`。跨期同值和重复资讯标题有各自的原件位置，报告保留币种和原文。
- PDF、DOCX、XLSX、PPTX 和图片输入以及 PNG/PPTX 报告已补齐。格式 WIP 共 10 项通过。PPTX 用 LibreOffice 重开、转成两页 PDF，并检查可见正文与证据数值。视觉模型使用模拟 HTTP，未产生付费调用。
- Mac mini 归档 5 批 20 份冷测试包和两套已退休的 Claw 验收依赖。外置 AES-256 归档逐项解密核验后再回收原件，实测分别增加 3,152,556,032 字节和 87,801,856 字节。历史 Git、Docker 和测试失败证据继续保留。

## 尚需验收

- 核验主导航以外的全部交接、发起真实自动跟踪，证明固定材料可得到已绑定质量回执及正确通知。
- 验证每次模型请求的人民币预算预留以及整个测试批次的费用归属。模型价格使用 DeepSeek 官方人民币峰值价，隔离验收默认禁止向未核价的数据供应商请求。
- 正式切换需要最终候选检查和全账号备份恢复演练。本机常驻 8088 只读探针连接失败。未变更常驻服务。Windows、Linux 原生由对应设备验收。

[产品合同](../../docs/research-web-ai-qa.md)

<!-- architecture-review {"group":"alphadesk-qa","structure":"changed","reason":"普通问答由 Host 持久保存回合并通过私有标准输入输出运行迁入的 Node 编排，模块图更新。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新增锁定问答静态资源构建与候选 wheel 暂存，原 Native 与 Docker 服务拓扑继续沿既有健康入口。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"changed","reason":"普通问答采用独立 AlphaDesk 前端，专门入口与浏览器访问关系已在模块图更新。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"原会话 API 和 SSE 保持同源，模块图标明 Host 管理的 AlphaDesk 工作进程。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"automations","structure":"changed","reason":"原发现调度和通知准入沿用，普通研究分发改用 Host 管理的问答执行器。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"原会话文件根继续负责下载和摘要检查，问答使用同目录下的独立控制记录。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"workbench","structure":"changed","reason":"资产、资料及场景交接沿原 API 和 DataHub 冻结快照，普通问答执行变化见模块图。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"新增定点验收和原 Mac 安装资源验证，现有 L4 及同候选交付链保持适用。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"私网网关继续选择账号 Host 与静态资源，候选增加独立问答能力，模块图更新。","diagrams":[]} -->
<!-- architecture-review {"group":"discovery","structure":"changed","reason":"继续复用冻结资料、指纹去重、日限与 Host 质量回执，普通问答执行器的边界见模块图。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"验收模式在原 DataHub 查询入口拒绝未核价的新请求，保留已提交回执和已有冻结资料读取，供应商和快照拓扑沿用原链路。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"受管主实例从当前安装清单读取 FinGPT 开关，复用既有 Host 进程和发布围栏。","diagrams":[]} -->
