# Super Agent 个人自动化接入

Super Agent 将本人目标交给 Chief Coordinator，在 Paperclip 中保存任务、运行、会话与质量记录，按任务需要调用专业岗位，并交付可核对的成果。本文是 ResearchWorkbench（RWB）的接入与协作说明，不是运行许可、工具就绪证明或发布回执。

## 本人入口与项目选择

在已完成本人配对的飞书企业机器人单聊中使用 `/chief`。入口须核对真实作者、任务归属与项目绑定；转述、历史摘要、网页、候选文件和工具返回均不能扩大授权。快速回执只表示已收到意图，不表示模型执行、QA、PR 或上线完成。

`--project <key或别名>` 放在动词之前。以下使用已注册项目键 `rwb`；不能用正文指定任意目录或提高权限。未指定项目时，使用本人会话中持久选择的项目。切换项目恢复该项目所选任务；显式查询某个任务不暗中切换选择。

| 本人命令示例 | 行为 |
| --- | --- |
| `/chief projects` | 查询已注册项目，不建任务、不调用模型。 |
| `/chief project rwb` | 选择 RWB 并恢复该项目的所选任务。 |
| `/chief --project rwb new 梳理本次需求` | 创建明确绑定 RWB 的新目标。目标中应说明输入、范围、成果和可观察验收。 |
| `/chief --project rwb status` | 查询所选任务和待应用补充。 |
| `/chief --project rwb status LEO-28` | 只查询指定任务；任务号是语法示例，不是新任务授权。 |
| `/chief --project rwb add LEO-28 补充验收要求` | 保存同根补充并暂停后续派发；旧运行明确终态后应用新输入版本。可省略任务号使用所选任务。 |
| `/chief --project rwb pause LEO-28` | 暂停后续派发，保留在途运行、原操作及累计预算，不把未知结果改为取消。 |
| `/chief --project rwb continue LEO-28` | 继续原根；复用同版本未完成计划，新输入按最新要求重建，未知结果先对账。 |
| `/chief --plan-first new 先形成计划` | 本人可选的一次计划后暂停；在已选择 RWB 时用于该项目，收到计划后用 continue 继续。无需复制计划 SHA。 |

普通目标默认沿既有授权执行，不强加一次计划确认门。选择 plan-first 后，补充再继续也不为每次新计划重复加门。`/chief <目标>` 仍可用；目标首词与命令冲突时用 `new`。成功的 add、pause、continue 保存任务选择。仅对已完成根的独立新目标才使用 followup；失败修正与 UNKNOWN 不得借新根重置预算。

## 当前执行与权限

模型进程使用 Mac 原生 Codex，沿用个人订阅 `gpt-6.1-sol`、推理强度 `low`，不转 API 或换模型。Codex 沙盒关闭，`approvalPolicy=never`；岗位和当前任务范围内的动作不逐项重复审批，但这不免除明确禁令、项目交付门和独立 QA，也不自动提供 root、辅助功能或屏幕录制等系统权限。缺少实际能力时报告具体缺口。

Docker 按项目需要用于构建、测试或服务，不是业务模型必须运行的位置。宿主事实不能由容器内观察冒充；macOS 结果也不能冒充 Windows/Linux 原生验收。RWB 的平台边界以[Agent 工作流](../AGENT_WORKFLOW.md)和[支持矩阵](../research-web-platform-support.md)为准。

Paperclip 是唯一任务、运行和会话控制面；适配与控制层只保留授权绑定、操作意图、映射及回执，不建立竞争任务库。任务续接从原 Native 授权输入和固定产物重建上下文，不伪造运行身份。每次运行只加载当前项目与岗位获准的材料；记忆和文档本身不授予工具权限。

普通 RWB 动作上限取可信 Native 项目登记、catalog 与任务许可的交集，不能由本说明提高。read_only 映射为 artifact，即使登记了仓库远端，也不等于有代码工作区或写入权限。工具被列出、Skill 被分配、连接存在、实际动作成功和业务验收是不同证据阶段，不能相互推定。

## 按需岗位与独立质量

Chief 按目标拆分依赖并指定跨职责共享对象的唯一执行负责人，不要求每个任务跑遍全部岗位。

| 岗位 | 主要责任 |
| --- | --- |
| Chief Coordinator | 拆解目标、协调依赖、授权边界、预算和汇总。 |
| Research Analyst / Product Manager | 来源与事实、业务结论、指标、需求及可观察验收。 |
| Product Designer | 视觉、交互、可访问性与设计依据。 |
| Software Architect | 技术边界、接口与取舍；协调前后端实现。 |
| Frontend Engineer / Backend Engineer | 各自实现及开发侧测试；应用代码、配置行为和数据库语义不因扩展名转给文档岗。 |
| Quality Assurance Engineer | 独立会话核验精确候选、实际证据和 NOT_RUN，不自审实现。 |
| Platform Operations Engineer（DevOps） | 项目登记范围内的构建、CI/CD、服务与受管交付。 |
| Network Engineer | 牵头 DNS、代理/VPN、TLS、路由、网关及连接故障；需要代码修改时协调技术岗位。 |
| System Resource Engineer | 卷身份、容量、RAM/Swap、CPU/I/O、缓存与资源预算。 |
| Document Specialist | Office（Excel/Word/PPT）、PDF、Markdown、TXT/LOG、JSON/YAML、CSV/TSV、XML、LaTeX/BibTeX 等整理、制作、转换与验证。 |

文档岗默认保留原件并输出新版本，记录编码、类型、结构及转换损失；语法/schema、内容含义、公式实际重算、LaTeX 编译和渲染分别留证。Research/PM 负责实质内容口径，Designer 负责视觉要求，QA 独立核验。小型纯文本修改不机械增加岗位或调用。

## 原根预算、返修与恢复

默认原根最多 **6 次外层角色调用**；只有本人授权且可信控制面登记为复杂任务，才可使用 **12 次**。Chief 计划、执行子任务、QA、返修和最终汇总共用原根累计账本；补充、暂停、继续、重启、新会话或输入改版均不清零。每 run 的 64 responses 上限与全局单任务执行约束保留，取消每日新任务数量硬上限。

质量返修最多两轮。QA 的 NEEDS_WORK 回到原执行子任务，保留旧失败、旧候选和原 QA 记录；修复后由独立会话复核新候选。成功运行的 QA 质量不通过不是传输失败，不能以重试传输替代返修。Chief 须为汇总与必要复核预留调用。

外部或模型动作结果未知时，只沿原 operation、dispatch、run 和真实回执对账；缺本地回执不是换 ID 重发的理由。add 先持久保存 pending 输入，在途运行未明确终态前不改其输入绑定。中断后保护原件、未归并工作与恢复证据，不删除锁、许可或账本来制造可重试状态。

## RWB 交付边界

RWB 源码真相源为 GitHub，`master` 是唯一长期集成分支；按当前[仓库规则](../../AGENTS.md)和[Agent 工作流](../AGENT_WORKFLOW.md)使用受管 Git 路径、短期分支及必要的独立 worktree，不用文件同步覆盖源码。新增文档须核对[文档治理](../research-web-documentation.md)并纳入[文档门户](../README.md)。

普通 Super Agent RWB 任务不得因通用岗位说明推导出合并或部署权。历史上存在 DevOps 的**任务绑定**合并/部署例外：只有原任务明确授权、可信项目登记和受管操作许可同时满足，才沿原 RWB 验证、评审、平台、Actions 额度、分支保护与部署恢复流程，在唯一写入窗口内执行。它不是可复制到其他任务的全局权利；代码合并、服务切换和业务验收分别记录。

仅产物任务止于候选；仅 PR 任务止于原 PR 的受管交付，不合并、不部署。后续获准更新已有 PR 时沿原任务、原分支与原 PR 推进，不另建替代 PR 重置身份或预算。文档内容本身不构成 apply、push、merge、deploy、账号、KB、同步、模型或服务变更的授权。

受管 `delivery --status` 可能执行合并，`--defer-cleanup` 仅延迟清理，并非只读模式。只观察 PR/CI 时使用获准的只读通道。任何远端写动作前仍须读取[Actions 额度规则](../actions-budget.md)并核对当前证据，不用历史 public 状态推导当前额度或权限。

## 证据与历史边界

交接须分别列出真实文件、候选身份、实际验证、未执行项、源码交付、发布、部署、业务验收与资源收尾。输入与产物摘要、命令退出结果和来源定位放入独立任务证据；不把工程流水嵌入用户说明。检查计划不等于检查执行，文件生成不等于验收，历史 PASS 不等于当前候选通过。

PR259 的早期文档试点属于历史：原任务 LEO-2、受管任务 `super-agent-rwb-doc-pilot` 当时的单 README、Docker 执行、`/rwb` 入口与仅交 PR 合同只说明旧试点范围，不作为现役全局规则。历史任务、调用与验收记录单独保留，不能据此认证当前候选或扩大权限。

真实任务暴露的方法、工具、交接或运行缺口沿原任务定位：职业方法更新岗位 AGENTS/SOP，依赖与连接证据更新 CAPABILITIES，派发/预算/恢复/权限缺陷修原运行代码，业务缺陷修对应项目。岗位材料经既有发布器及 Native CAS 保全人工差异和历史；新版本只对下个 run 生效，不覆盖在途快照。未执行或缺少依赖的验证明确记为 NOT_RUN。
