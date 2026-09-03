# Research UI 真实模型验收（持续更新）

本记录按时间保留实际执行、发现的问题及修复；早期「待验收」是当时状态。整轮收口见 `2026-09-03-research-ui-final.md`，不把失败试验改写成通过。

## 专用会话

- 会话：`82f9904a-4c4c-4d35-a1cd-93985437f488`，标题「UI 验收 · 多轮与 HTML 文件」。
- 模型：现有 `deepseek-v4-flash`；原实例 3080、配置、权限与执行上限未变。
- 本轮测试没有联网取数、读取用户其他文件或新增依赖。

## 已观察的结果

1. Web 新建 FinGPT，从输入框提交固定样本 10、20、30；真实回答平均值 20。
2. 第二轮生成 `outputs/ui-acceptance.html`，929 字节；真实 `af_run_script` 活动出现在活动面板。
3. 在隔离预览中读到中文标题、样本表和平均值 20.0。下载接口实际 GET 200，attachment、no-store、nosniff；HTML 含三根 SVG 柱。
4. 模型第二轮聊天结尾却写平均值 30.0。此为真实模型内容错误，不能因文件结构检查成功而宣称回答正确。第三轮要求实际读文件，模型通过脚本读取后纠正为 20.0；未改文件。
5. 通过 Web 重命名后，以不同验收查询串重新加载同一会话，标题和六条消息恢复；无自动重复提交。
6. 第四轮在输入框显式选择 HTML，新建 `ui-delivery-checked.html`（722 字节），Python 断言平均值等于 20 后读回。Web 实际显示「文件交付已检查」，服务详情为 `delivery.status=completed`、要求 `[html]`、缺失 `[]`，只计入本轮新文件，不误计旧 HTML。
7. 第四轮文件 ID `97000c47047feb45a14f6436`，SHA-256 `c699a5a67f6d45405baa5c64886a519d28285db8989686011f82544d3db89d8b`；执行状态 completed、can_cancel=false。交付格式有效仍不代表全部内容质量已被自动证明。
8. `tests/e2e/research_web_live_readback.mjs` 实际通过：隔离浏览器加载/刷新八条消息、交付通过标签、空 sandbox 的 HTML 预览、浏览器 download 事件与保存文件哈希一致。未发新模型请求；主控制器已查看 `live-readback/html-preview.png`，没有把自动截图生成视为人工验收。
9. 06:46 UTC 核对原生 23 个会话 `running=false` 后，仅重启已确认所属的 Web 8088 和 DSH 3081 进程；原 3080 PID 77454 未改。新原生目录包含四个 Skill、两个 Workflow。使用旧会话 `session.models` 冷恢复、`skill.list` 实际发现六项，Web 恢复八条消息与已检查文件。
10. 随后从旧会话 Web 输入框发送第五轮无工具追问，真实模型回复「初始样本为 10、20、30，平均值为 20」。历史现为十条，文件仍两份；本轮 `delivery.status=not_required`、files=[]，不误把上轮产物算作新交付。后续 readback 必须按最新十条和无文件要求验证，不能继续断言上轮 delivery 状态。
11. 更新后的只读 readback 实际通过十条历史刷新、本轮无需文件、旧 HTML 隔离预览及下载哈希复核。第四轮原成功回执单独保留为 `round4-receipt.json`，不将历史验收与最新会话状态混淆；已人工查看 `cold-recovery.png`。

文件下载路径：`/api/research/sessions/82f9904a-4c4c-4d35-a1cd-93985437f488/files/914ce65db2a4e561eb3a6c89/download`。

## 布局回归的已知未完成项

`tests/e2e/research_web_layout.mjs` 使用隔离无头浏览器，只允许 GET/HEAD，阻断写请求。首轮 1440/1600/1920/820 的 12 个页面组合通过；390 手机侧栏没有可见关闭按钮而失败。另观察到 slash Escape 未关闭、桌面导航缺少可见文字、首页右侧空面板及手机搜索缺口，交 Task 3 修复。截图与失败回执位于 `outputs/research-web-ui-acceptance/`，不能当作最终通过证据。

Task 3 初检更新：目录已接新 API；控制器按新 listbox/移动关闭按钮语义更新测试，十五个页面/视口组合实际通过（代码仍未最终审查，不作为交付定稿）。只读历史浏览器三会话通过：PDF 保留及页码文本、四份资料/两名真实子 Agent、最终 XLSX 下载哈希、已取消会话没有待审批按钮。未新取数或重跑这些旧研究。

## 真实能力创建（进行中）

- 专用会话 `793dc010-bb08-429d-957a-c858c6654d39` 从 Web 能力中心「对话创建」进入。初始确实 `idle`、无消息、请求在输入草稿，明确点发送后才调用模型。
- 首轮模型真实生成 SKILL.md / capability.json / 多余 workflow.json。输入类型 list[number]/string、额外字段和 stdlib 文本依赖不合约，导入草稿 `69485961c003479cab1d77e52990f919` 明确 invalid，未发布、未加入原生目录。模型过程中有工具错误和自纠正，不宣称一次生成即兼容。
- 通过原会话再次要求模型修正两份文件，明确唯一元数据结构与 type=text、dependencies=[]、默认 html；多余 workflow.json 被重命名为 workflow-draft-reference.json 保留参考。控制器读取实际 SKILL.md，未手工代替模型改写产物。
- 此时真实发现后端缺陷：from-artifact 仍遍历历史文件账本中的已改名 workflow.json，导致 `[invalid_resource] 文件访问被拒绝`；实际文件列表已无该路径。必须修复选择实际当前产物的逻辑并补回归，不能把 ZIP 路径可用当作此问题已解决。
- 同时发现 UI 缓存运行状态导致完成后禁发布；已交 Task 3 通过实际详情同步和后端最终冲突判断修正，待最终实测。
- 第三轮要求模型将已修正的实际两文件打包为 verified-skill.zip，便于继续验证独立 ZIP 产物路径；尚未宣称发布调用闭环完成。

### 对话创建闭环与真实下载

- 第三轮实际 ZIP `7bfeb10ff04085cba5f42633`（2308 字节）经 Web 审查导入，静态检查通过。人工阅读实际指令后，明确点击发布为 `1ba298cc4b754aee9496b7d1c5c78bf7` v1；原生名称 `af-1ba298cc4b754aee9496b7d1c5c78bf7-v1`，编译 SHA256 `d8d991bbcb96089c48b9a1ce1d8fb059942bf26c54800817e3331241e6c55f3a`。原无效草稿未发布，仍保留。
- 从 FinGPT 新入口选择此能力发送新研究，真实会话 `7ee7b736-673a-4aff-8006-73de6c10b600`，标题「能力验收 · 自建 Skill 统计报告」。输入 [12,18,30,40]，DSH 原生指令进入消息，三次真实 `af_run_script` 完成计算、写文件、读回校验；n=4、sum=100、mean=25。
- 实际文件 `outputs/sample-statistics.html`，ID `3320abdf473d5e3d84d3df8f`，1285 字节，SHA256 `ff0b305c0b1815120654c944f00635094e930f98474ca7517d46d520e91878e0`。本任务要求 HTML，独立 delivery=completed、缺失=[]、格式检查通过。能力 ID、版本、只读资源路径与编译哈希实际保存在研究记录。
- `research_web_custom_skill_readback.mjs` 实际通过刷新版本记录、文件交付状态、无权限 iframe 预览、浏览器下载事件及字节哈希、样本值检查。控制器已人工查看 `custom-skill/preview.png`。此脚本只 GET/HEAD、没有重新发模型请求。
- 读回脚本首两次因为错误假设桌面面板默认关闭、两张表使用非唯一选择器而失败；修正为真实 aria-expanded 和「统计结果」表后通过。没有因此修改产品行为或削弱文件检查。
- 后端旧 ledger 问题已有独立修复提交 `d997759`，233 个 Python 测试通过；实际 Web 重启后根 SKILL.md 路径复验仍待执行，ZIP 成功不是其替代证据。

### 手动导入与版本生命周期

- 将真实模型生成的 SKILL.md 下载后由浏览器文件控件导入，不扫描全局目录。候选 `528c5a3dd15849b0a7f29fbdf5441b01` 初始缺产品元数据、检查 invalid；未静默补齐并发布。
- 在产品编辑表单填入名称「验收·手动导入样本」、slug `ui-import-sample-20260903`、text 输入、HTML 输出、af_run_script 需求及空依赖，明确修改 frontmatter 同名。保存后单独「检查草稿」通过，再明确发布 v1。
- 表单修改说明与指令、检查并发布 v2，GET 不可变版本确认两版指令不同；停用后使用按钮不可用；明确回滚 v1，刷新后当前版本仍 v1、enabled=true，v2 保留且可查看。浏览器实际导出 v1 ZIP，非空 PK 容器，回执记录 SHA256。
- `research_web_manual_skill_lifecycle.mjs` 完成以上 UI 动作，限制写请求仅能力管理路径，零模型调用。初次脚本误断言 import=200（实际201）、保存即检查（实际须显式检查）、发布响应包含compiled_sha256（实际在版本响应）；分别修正脚本并对同一专用候选断点继续，没有重复导入或覆盖其他能力。这些是验收脚本契约假设错误，不记录为产品缺陷。
- 控制器人工查看 `manual-skill/rollback-version.png`，目录/详情/两个历史版本可读。截图时运行时状态尚在初始加载，不能据该静态图宣称 DSH 离线；另已实时 GET runtime connected=true。
- 07:38 UTC 核对原生26会话均 running=false 后仅重启所属Web8088，加载 d997759 修复。两份DSH实例均未重启。

## Workflow 真研究、双 Agent 与文件

会话 `43170801-cfeb-4c89-914a-a6973dbb8c9a`，标题「Workflow 验收 · 基金资料共享与受限评价」，使用 fund-research-workflow v1、document-reading/fund-evaluation v1。由已授权资料准备会话升级，四份快照复制到本会话只读inputs，未重新联网；净值78bc1a79…243条13页、资料4e30e040…16行、分红7d10b4b6…25行、持仓ef0f29eb…220行。请求2025全年，取数时间2026-09-02，并非当日实时数据。

DSH原生子Agent `3c6101ae-fb53-469f-ab8a-fac757453306` 核验净值与分红（19804 tokens/80.142s），`e5ec4b45-5510-4506-bb5d-b30f9227fd9e` 核验基本资料与持仓（20859 tokens/61.648s）均结束。实际工具、错误与耗时保留；步骤模板无执行证据不勾完成。

初版实际生成DOCX/HTML/XLSX/PNG，但Excel「统计与口径」第10行是未完成f-string文本。控制器独立复算发现后明确要求模型保留原件、生成v2，不追加取数或子Agent。v2实际交付3格式、missing=[]：

| 文件 | 文件ID | 字节 / SHA256 |
|---|---|---|
| workflow-fund-report-v2.docx | b7633244999e079045942b68 | 41280 / 9ea0118a1d76b2383aaad4c63fd8ae2d81450ef5ff2ab1928ed40e7ee03531de |
| workflow-fund-report-v2.html | 1ccf91d946c2a7da1bcf9aa7 | 9727 / f8de5970ffe15cf45d882bb67d70f12a09ecadb0d5b69c7ce30283bffe4512f0 |
| workflow-fund-workbook-v2.xlsx | 849f14dbac3a9be567fbaf93 | 31508 / 24351ad0a27405ecb956d2acd49b698674b99b3fbc932f309889e90a048633ea |

使用已有Office库实际重新打开：DOCX47段3表；XLSX7工作表，原始净值244行含表头，分红26、持仓221、资料17。第10格为21.695831%真实数值，无残留代码。独立按243净值/242收益、250交易日重新计算：原始单位净值变动34.8692403487%，最大回撤−12.4780316344%，样本日波动1.3721648616%×√250。报告注明基准、完整分红总回报与披露范围缺失，不能当完整基金评价。

`research_web_workflow_readback.mjs` 最终PASS：两真实Agent、四资料、模板版本、独立交付状态、预览和三格式浏览器下载哈希。主控制器已人工看最终版本步骤/Agent卡片截图；产物在 `outputs/research-web-ui-acceptance/workflow/`，原版与v2都保留。

## 新上传 PDF 与运行中刷新

- 新真实会话 `63d128e4-e39d-4cd0-a1ec-2e5fa5d5e7c8`，标题「UI 验收 · PDF 上传与页码引用」。上传国金DSH报告，附件ID `a928b9cc44bdbe2640728740`，实际安全文件名 `d5c567bd66a8-dsh-report.pdf`。
- 从Web选择 document-reading v1，明确发送一次，记录idempotency key；执行中刷新后无第二次POST。真实af_run_script读取物理14/15页（索引13/14），PDF18页。回答分别引用arXiv/海外大师股票研究及基金评价案例，锚点可核对；无联网或安装。
- 验收脚本初次误认上传文件无前缀，保留了另一空会话0ad0d27e…的附件而没有发模型请求。第二次真实研究已完成，脚本末段误用activity.name而实际为title，改成真实契约后只读重验同一63d…会话PASS、零新增模型请求。未把脚本第一次运行说成完整通过。
- 最终回执 `pdf-live/receipt.json` 为readback模式；回答和PDF下载保留，已人工查看回答截图。截图初始runtime尚未加载显示未连接，不表示研究失败，任务实际completed。

## 原生审批拒绝

新专用会话 `839ec20a-b2ce-461c-9602-eb4798bde1c1`，标题「UI 验收 · 原生审批拒绝」。真实请求af_public_data，fund_nav000001/2025-01-01至01-10；控制器点击拒绝而非允许。工具活动failed、detail=`Error: Public data approval rejected; HTTP not sent`；最终会话completed，无审批、文件、数据或子Agent。模型明确未取数且不重试。未修改其他会话审批。

根SKILL.md伴随文件选择修复也已在当前Web真实复验：不再invalid_resource，返回正确name_conflict（相同ZIP能力已发布），未覆盖已发布能力。

## 真实手动停止与额外发现

- 会话610ba6cb-8dcd-40d4-96e8-e238a24e2249首次脚本60秒超时，模型误说手动停止完成；控制器明确纠正且不计通过。第二次在超时边缘点击停止，原生出现 `turn/end carries non-JSON-serializable data`，界面failed/can_cancel=false但delivery pending。保留该原生日志与会话，继续诊断，不覆盖状态成成功。
- 新专用会话 `c825aae3-db16-41d6-9657-d77e2780832c` 由 `research_web_stop_live.mjs` 从真实Web提交一次研究，检测af_run_script实际running后1.5秒点击停止，取消HTTP200。结果status=cancelled、can_cancel=false、delivery=not_required。
- 实际脚本在1808ms停止，`cancel-proof.txt` 仅4行/8字节。三次下载间隔2秒，哈希均 `16fbd7d1f18d2fedb247d73edc3bc6aa040f5ab99bd3b48c35b79e543d22179b`，未继续写入。独立回执和截图在stop-live目录。这是实际取消证据，不以先前超时作为替代。
- Claw首页68e8775已独立复审Approved；最终布局脚本15/15通过，四Skill可在两个模式进入草稿、两个Workflow首页展示及真实分类、目录搜索/空态/详情、slash键盘与移动抽屉均验证，无模型调用。控制器已人工查看最终15张截图，未见水平越界和按钮遮挡；长内容正常纵向滚动。

## 停止异常最终收口（09:01 UTC）

- 新增明确停止意图、完整原生历史/父子空闲证据与事件revision保护。首次28项中的原始26项暴露正常aborted测试夹具误写cancelled，已按实际协议改正；独立复审发现新事件竞态，新增turn/start与turn/end两项先RED再修复。最终28项通过，复审Approved。
- 在原异常会话610ba6cb…点击真实「重新核对停止」：当前任务11b33a2a1d77001c532e7c80成为verification_failed，failure_code=cancel_terminal_event_missing，files=[]，未伪造原生turn/end。页面明确原因并恢复发送；不是把原始停止试验算成功。
- 同一会话从Web发起新一轮、明确不调用工具/不读写/不联网。真实模型回答可继续并承认上一轮未确认；新任务51dda8785a3d330d68d6653f为completed/not_required，历史8条。安全索引只读核对：旧任务仍verification_failed、cancel_accepted=true，新任务单独收据；没有覆盖旧结果。
- 09:00 UTC最后加载已复审代码，仅重启所属Web8088（PID19511）；DSH3081与原3080未重启。33个原生会话空闲后操作，未处理其他任务。
- 最终全量287项Python/123项JavaScript通过，无skip；静态检查、图文一致性、文档同步、项目约束和任务完整性通过。八图最终showcase9/9零错误警告、四视口通过；图07因本修复重新生成并人工看1440深色/2048浅色，绑定新哈希。
- 最后再次运行15组布局、架构入口与交互、Workflow/自建Skill/旧历史/多轮/PDF只读浏览器脚本均通过，没有重新执行已完成研究。15图前一轮已全部人工查看；最后一轮另看FinGPT1440、Claw1920、能力中心390，布局和内容层级保持一致。
