# AlphaDesk AI 问答迁移

## Fed RSS 实际报告修复

原会话 `9c99e69e-285e-4426-be12-74faacc3f3f5` 的验收脚本漏传已上传附件 ID；修正选择后，真实模型取得来源，但报告计划被未绑定字面量检查拒绝。零模型的真实 macOS sandbox 验证已确认报告 SDK 能落盘。

本轮在原来源上下文交接冻结 RSS 的明确元数据，章节 `source_ids` 由 SDK 呈现绑定标题、日期、链接和真实摘要。原上传字节经真实 Mac sandbox、Delivery 与 Host 质量检查已通过，零模型请求；金额、指标及计算的观测绑定规则继续执行。报告工具的嵌套字段类型、模型可见来源 ID 及本轮范围提示已补齐。原深度会话复验仍未完成，失败回执保留，未据此宣称业务通过。

真实来源分支已接入 DataHub `ext_fed/news`、原 Discovery 冻结及 Automation 调度、历史和通知判断。历史快照仅作已见基线，实际执行重新取得固定来源；同内容定时触发不调用模型。跟踪、来源元数据/索引/报告相关回归、固定 Node 24 的 13 项 worker 消息旅程、195 项 L4 Node 检查及独立 Python/JavaScript 评审通过。

真实在线验收已通过。原 Bot 的手动运行 `automation-run-8c60a9698a8da894bce5918055c394da8839ba1fc6eb560f362e13af2efbd37c` 使用 DeepSeek 官方 Flash 实际调用 3 次，冻结相对原真实基线的 4 条新增公告；Markdown 中四条来源的 URL、日期和原摘要均核对一致，Host 质量 `passed`，通知判断 `meaningful_change`。报告 SHA-256 为 `fffc49e283e0d989cecc957c12facc8e745a2bd4815120d1a20178f46b99f0e5`。同 Bot 于真实时钟 02:25 触发的运行 `automation-run-e2b89b1da9e945e995b9be1e3caf4f69` 为 `skipped_unchanged`，模型账本原字节内容未变，随后停用。最终证据保存在本机 `fed-online-tracking-20261123/final-acceptance.json`、历史和实际 Markdown，原失败运行保持必要短记录。

新阶段账本累计 196 个请求，均有官方 usage；保守费用上界为 1.569584 元，仍在已授权新增 50 元内。旧 48.796 元未知预留未改写。

已合实际部署基线 `0657693b`。完整 `test_api.py` 在本机以共享 Python、固定 Node 24 分 12 批执行，228/228 通过且测试根均退休；实际运行 HEAD 为 `b75e144d`、WIP 仅操作员相关文件，API 和 Service 前后 blob 一致，结果按同 blob 复用，不伪称最终候选全树 exact 运行。`apply-fingpt` 复用已有显式前版/目标资格和 version 4 事务，保留原开关、MCP、私网路由及完成后回滚；39 项核心、表面和旧行为回归通过，独立评审无 P0–P2。最新候选 CI、Mac 双入口回滚及正式切换仍待完成，不由隔离 Host 或本地操作员回归代替。

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

主线 `4c9290db` 增加受管 Git 大差异恢复。FinGPT 候选合入该修复后更新产品封印。

合入 `247db876` 后，FinGPT 的联合发布保留 APFS 身份恢复与网关源码迁移入口，并单独校验问答开关及回滚配置。

合入最新主线 `0ca0f4c0` 后，FinGPT 和 Research Bot 的常驻发布入口分别沿用各自的产品封印与运行时诊断。

本机接受回执、主 Web 的只读运行探针和私网网关配置均指向 `0ca0f4c0`。FinGPT 的操作员据此固定实际前版，Research Bot 的封印保留原定义。

合入 `88bec0ec` 后，Research Bot 保留原 DSH 自动化执行及本机导航准入。FinGPT 仍按原开关切换普通问答，私网账号继续受原权限约束。安装 CI 同时校验两个 Doctor 诊断。

2026-11-15 复查 PR #301。Research Web Checks 的两个失败均由隔离测试初始化无关 MCP 并访问系统 Keyring 引起。使用拒绝访问的合成后端复现两项失败，关闭测试夹具中的 MCP 与调度后，FinGPT 和预算组合 18 项通过。候选继续沿原 PR，重新获取同提交检查及 Mac 验收。

2026-11-16 将已备份的 `ffca41c1` 接到主线 `3be8a17b`。常驻接受回执和主 Web 的运行探针均指向 Radar 版本 `3be8a17b`，因此 FinGPT 固定该版本为切换前版，并使用合并后的产品检查点。Radar 的时效信息和 FinGPT 验收的来源费用守卫同时保留。

同日下午将候选接到 `cfbf73ee`，保留策略验证入口、两套静态就绪检查及受管 Git 恢复能力。常驻接受回执和 8088 探针已指向策略验证版本 `33b3044d`，FinGPT 据此更新切换前版。

11 月 16 日晚复验时，整份统计公报的问答读取触及执行器 24,000 个 UTF-16 代码单元的限制。Host 按实际序列化后的响应大小分页，并在每页保留来源标识和原件 SHA-256。五页重组与原件逐字节一致。真实 DeepSeek 复跑使用原公报及从同一原件提取的冻结 GDP 观测，Host 质量通过，下载的 Markdown 核对数值、单位、年份、日期和链接。

- 核验主导航以外的全部交接、发起真实自动跟踪，证明固定材料可得到已绑定质量回执及正确通知。
- 验证每次模型请求的人民币预算预留以及整个测试批次的费用归属。模型价格使用 DeepSeek 官方人民币峰值价，隔离验收默认禁止向未核价的数据供应商请求。
- 正式切换需要最终候选检查和全账号备份恢复演练。Windows、Linux 原生由对应设备验收。

[产品合同](../../docs/research-web-ai-qa.md)

<!-- architecture-review {"group":"alphadesk-qa","structure":"unchanged","reason":"FinGPT 在账号 Host 到原问答执行器之间分页，复用已冻结原件、权限和现有运行链路。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"只修正真实 Chromium Reader 整数分项与 DOM 总高度的 1px 舍入差异，保留原截图和度量，不改变文档执行拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"FinGPT 在账号 Host 到原问答执行器之间分页，复用已冻结原件、权限和现有运行链路。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"changed","reason":"普通问答采用独立 AlphaDesk 前端，专门入口与浏览器访问关系已在模块图更新。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"FinGPT 在账号 Host 到原问答执行器之间分页，复用已冻结原件、权限和现有运行链路。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"changed","reason":"原发现调度和通知准入沿用，普通研究分发改用 Host 管理的问答执行器。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"FinGPT 在账号 Host 到原问答执行器之间分页，复用已冻结原件、权限和现有运行链路。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"changed","reason":"资产、资料及场景交接沿原 API 和 DataHub 冻结快照，普通问答执行变化见模块图。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"新增定点验收和原 Mac 安装资源验证，现有 L4 及同候选交付链保持适用。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"FinGPT 在账号 Host 到原问答执行器之间分页，复用已冻结原件、权限和现有运行链路。","diagrams":[]} -->
<!-- architecture-review {"group":"discovery","structure":"changed","reason":"继续复用冻结资料、指纹去重、日限与 Host 质量回执，普通问答执行器的边界见模块图。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"验收模式在原 DataHub 查询入口拒绝未核价的新请求，保留已提交回执和已有冻结资料读取，供应商和快照拓扑沿用原链路。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"受管主实例从当前安装清单读取 FinGPT 开关，复用既有 Host 进程和发布围栏。","diagrams":[]} -->
<!-- architecture-review {"group":"dossiers","structure":"unchanged","reason":"FinGPT 在账号 Host 到原问答执行器之间分页，复用已冻结原件、权限和现有运行链路。","diagrams":[]} -->
