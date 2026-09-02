# Research Web 真实验收 · 2026-09-02

## 可直接使用

- [Web 入口](http://127.0.0.1:8088/)
- [基金受限评价及文件包](http://127.0.0.1:8088/#/fingpt?session=5ef2fb20-59f9-4203-8484-c2afefc1c922)
- [双 Agent 行业研究及文件包](http://127.0.0.1:8088/#/claw?session=dfee9d43-e59d-461b-a7c6-49b12b291519)
- [基金 Word](http://127.0.0.1:8088/api/research/sessions/5ef2fb20-59f9-4203-8484-c2afefc1c922/files/e011a8581158426f3eff178e/download)、[HTML](http://127.0.0.1:8088/api/research/sessions/5ef2fb20-59f9-4203-8484-c2afefc1c922/files/82f44933e82508fd7e8cf020/download)、[Excel 底稿](http://127.0.0.1:8088/api/research/sessions/5ef2fb20-59f9-4203-8484-c2afefc1c922/files/0937dfece6ffffe1f7a3fd96/download)、[净值图](http://127.0.0.1:8088/api/research/sessions/5ef2fb20-59f9-4203-8484-c2afefc1c922/files/ce080db7f42a5975e806d0ac/download)
- [行业 Word](http://127.0.0.1:8088/api/research/sessions/dfee9d43-e59d-461b-a7c6-49b12b291519/files/485d2792cbb2780e2fceb969/download)、[行业 Excel](http://127.0.0.1:8088/api/research/sessions/dfee9d43-e59d-461b-a7c6-49b12b291519/files/59f6ea9432b3b2ff09b9b276/download)

这些是本机真实模型的实际产物，不是固定样板答案。链接要求本地两个服务运行。
文件均保存在 `~/.alphafoundry/research-web/sessions/<会话ID>/outputs/`，历史由专属 DSH 保存。

## 运行方式

在 `/Users/leon/Desktop/Projects/AlphaFoundry/.worktrees/dsh-web-v1` 分别启动：

```bash
/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python -m app.research_web.launch_runtime --source /Users/leon/Developer/deepseek-harness --data /Users/leon/.alphafoundry/research-web --source-mode --research-tools
/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python -m uvicorn app.research_web.main:app --host 127.0.0.1 --port 8088 --timeout-graceful-shutdown 5
```

使用已存在的 Python 环境，没有安装新包。Web 8088、专属 DSH 3081；用户原有 3080 未重启、未复制凭据。
默认模型仍为 `deepseek-v4-flash`，原生源码版本和执行上限保持不变。
5 秒 graceful shutdown 避免开发重启一直等待长连接；DSH 任务不随 BFF 关闭而重发或停止。

## 真实旅程证据

| 旅程 | 会话 / 结果 |
| --- | --- |
| 多轮及刷新 | `9792827c-3bd2-437f-96ef-fbbcd7260c4d`：17×23=391，追问+9=400，刷新后继续÷8=50；均由真实模型生成 |
| PDF 解读 | `28d73296-9908-4095-b89b-f46a4758d852`：已上传18页国金证券DSH研报，原生 document-reading Skill 与 af_run_script 读取正文；独立抽取核对第4/6/10/15页，对应 Harness、日志恢复、Skills和基金评价 |
| 原生搜索 | `76cb8df9-36a5-403f-8e4d-fcd4d085b26d`：真实 web_search 返回 DSH 官方仓库等来源，不伪装为已阅读全部网页 |
| 基金公开数据+文件 | `5ef2fb20-59f9-4203-8484-c2afefc1c922`：原生 fund-evaluation、两次人工批准、公开净值、Python计算和PNG、DOCX/HTML/XLSX/MD；独立格式检查通过 |
| 双子 Agent 报告 | `dfee9d43-e59d-461b-a7c6-49b12b291519`：两个真实子会话 `45ed716e-2efd-44aa-99cc-ad36000cbf9c` 和 `baeafee5-9726-4f13-a18a-6b80e05dc9a8`，分别读取PDF能力与评测部分，写 agent_a.md / agent_b.md；主 Agent 汇总文件，XLSX含11项能力/风险与来源页码 |
| 原生审批 | `c9155f74-5887-4ef2-8768-5da903ad1ddb`：原生日志 seq68/493=allowed-once、607=rejected、784=cancelled；拒绝/取消无对应HTTP请求 |
| 父脚本停止 | `b84b9571-2a4a-4406-994f-4aeb61a723ab`：真实脚本已写 pi-long-start.md 后点击停止；超过计划30秒仍无 pi-long-result.md |
| 父已结束、子仍运行时停止 | `21569888-e2ec-47ec-8852-9ae4138e0316`：主Agent回复已启动并结束，子 `2b20cd41-5634-45e8-9748-6648630c2567` 仍运行，Web保持停止入口；点击后子状态cancelled，超过35秒仍只有 child_cancel_started.md，无结束文件 |
| 模型失败后恢复 | `52c9bed5-5d60-4c8f-8a78-c9a608158311`：仅此验收会话临时选无效模型，真实提供方拒绝并显示失败；恢复flash后回答19+23=42。不更改全局默认或其他会话 |
| 重复提交 | 上述恢复问题用相同幂等键提交两次，两个202，原生历史只有一条恢复问题、一条回答；没有自动重放失败问题 |
| 断线、审批恢复 | `a719976a-07eb-42a1-b34b-f855f81e2447`：父任务等待CLS审批时停止BFF；Web显示连接断开，不宣告完成，未发送草稿仍在。重启后恢复同一审批，仅一条用户问题；允许后真实返回3条电报与来源 |
| 文件边界 | 用模型故障验收会话的文件接口访问基金DOCX标识，返回400；opaque Origin=null读取runtime返回403；真实沙箱跨会话读取agent_a.md抛PermissionError |

浏览器实际点击下载了基金 XLSX 和行业 DOCX；基金 HTML 在空 sandbox iframe 内展示正文，禁止脚本、表单与外部导航。
服务重启后仍读取原生日志和同一文件，没有创建替代会话或再次执行旧问题。

## 文件与研究质量复核

- 基金本次请求 limit=60/100，两次单页均返回20条：2026-08-05至2026-09-01。未伪造缺失40条，不推断数据源只能返回20条。
- 独立严格沙箱重开确认基金工作簿三个页签：nav_observations、computed_metrics、sources_meta；按日期识别20条净值记录（工作表另含说明行）。Word有15段，报告引用实际工作簿文件名，移除了未核实的CNY标注和标题错字。
- 行业 Word 有18段；Excel analysis 为11条数据，包含内容要点、来源页码、来源性质和限制口径。它是单份研报基础上的行业工具研究，不声称独立验证所有报告结论。
- 初次模型脚本确有语法/路径错误，界面保留失败活动，后续模型自行修复并实际产出文件；没有隐藏失败或用固定文本补结果。
- 格式完成仅证明当前任务新增/变化文件可打开、有内容。报告准确性不由格式检查保证；缺少复权、分红、基准、持仓、费率和币种时只能交付受限评价。

## 原生能力边界

原生 DSH 委派把子 Agent 的 approval 设置为 `never`。实际测试子 `67fe0486-7e2d-4301-9850-e5140d4e0348` 在1毫秒内自动 rejected，根本未向Web弹审批；不能将其说成人工拒绝。研究流程已明确：需要审批的公开取数由父 Agent 执行，然后交给子 Agent 分析。没有改动原生策略。

现有沙箱仅验证macOS本机；没有做Windows、桌面、Linux部署、多人权限或任意MCP。图片上传已有协议/前端测试，但本轮未做真实视觉模型识别。提供方中途断流的所有类型未逐一人为制造；本轮模型故障使用真实无效模型响应，连接故障使用实际BFF断开。

早期探针 PID38291 仍为内核 `UE` 状态，临时目录 `/private/tmp/af-dsh-sandbox-probe.frLuyJ` 保留；本次只读复查，未自动重启系统。当前研究脚本的真实停止与回归均另有通过证据。

## 回归入口

完整命令与最后结果见 `.ai/reports/2026-09-02-dsh-web-live-acceptance.md`。
`tests/research_web`、`tests/javascript/research_web*.test.mjs` 覆盖协议、历史、幂等、文件边界、交付缺失/损坏/旧文件、解析后变化、审批失败、数据源错误和前端状态。模拟协议回归与上述真实旅程明确分开。
