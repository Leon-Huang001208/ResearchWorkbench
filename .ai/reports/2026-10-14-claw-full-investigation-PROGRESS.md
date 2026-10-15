# Claw 全页面调查与复刻

日期：2026-10-14。宿主：macOS；任务：Web 功能开发；本平台验收：macOS Native、适用通用门。Windows/Linux 产品原生验收不在本宿主执行。

基线：`de0fc4e30b47545d33081662be4994bc5cd5a870`，现有隔离 worktree `claw-interaction-redo`。原 PR 与候选保留；本轮未授权合并、部署、清理。状态：进行中，不能据本报告宣称全量调查或真实验收通过。

## 证据边界

- **实际观察**：登录 Chrome 的原日程对话、创建/修改参数、两次试跑报告、日程表；本轮技能页与 IM/连接器设置弹窗。
- **源码确认**：本产品全部 Claw 前端处理链路、Automation Run 定义快照、DSH 准入和数据桥接。
- **未知**：AlphaEngine 服务端实现，尚未获取的请求结构和事件、隐藏及错误状态。
- Chrome 只有原生窗口通道，未出现在标签页连接目录。辅助功能可读，但截图一度全灰，滚动/坐标输入返回无可用窗口。用户恢复窗口后技能页和设置可读；后续输入再次失联。未修改浏览器配置、安装扩展、开放端口或读取 Cookie/凭据。
- 参考证据在 `.codex/acceptance/claw-full-20261014/alpha-*`，既有完整对话证据沿用上一候选 evidence；只读源码调查不证明运行。

## 元素调查账本

### 2026-10-14 接续调查与连接诊断

- 本轮原生 Chrome 实际观察到两个标签：首页 FinGPT 和 `#/alpha-claw/index`；进入 Claw 并打开原创建对话，未提交新问题、创建或修改参考日程。
- 创建工具展开参数：`name`、`prompt`、`cron_expression: "0 30 15 ? * MON-FRI"`、`im_channels.feishu/weixin: false`。结果记录原任务 ID `76c0d31f-0b4c-4b36-b702-11478e02e915`、启用、云端工作区、未分组。该证据是工具卡内容，不是 HTTP 请求合同或服务端实现证据。
- 历史主线实际显示：名称后 AskUserQuestion，创建不立即执行；首次试跑工具摘要 9 成功；“增加”再提问并更新同一任务；“需要”承接二次试跑摘要 6 成功。报告、表格、引用标记、复制和 PDF 入口直接在对话展示；计数只是参考产品显示，不认证其数据或本产品验收。
- 原生窗口通道依赖前台，用户明确要求不与并行 FinGPT 对话争抢窗口后已停止原生切换/输入。Chrome 重启后扩展标签枚举仍 15–20 秒超时。官方扩展启用与 native-host 清单检查通过，通信子进程存在。应用日志另有旧 `computer-use` 相对路径启动错误；不将其认证为 Chrome 超时根因，也未擅改系统配置。等待用户在另一对话保存后重启 ChatGPT 桌面应用，未宣称修复。
- 实际候选 MD 文件链接渲染缺陷使用 `bugfix-evidence` 修复：两个新增回归先失败，再通过；同会话、交付校验成功且精确登记的相对链接转正式下载 URL。未知/外会话/重复/穿越/代码中的链接保持原文。84 项 focused JS 通过，独立只读评审 UI 文件 41 项通过，无阻断发现；真实浏览器点击待验证。
- 该增量 Router L0/L1 闭包实际通过：架构 82 项、UI/能力 77 项、文档治理和 Python 索引；增量 receipt validator `valid: true` 只证明本次 5 文件工作树增量，不证明整个 Claw 任务、候选提交 CI 或发布就绪。候选真实详情重新读取、渲染后正式下载返回 200，2469 字节且 SHA-256 与交付快照一致，见 `markdown-real-file-proof.json`；无新增模型调用，浏览器点击仍 NOT_RUN。总体调查状态仍未完成，等待桌面应用重建 Chrome 标签连接。
- 后续用户已完成 ChatGPT 桌面重启和官方扩展重装，侧栏正常；会话命名、标签绑定、全局枚举仍失败，后续错误转为 `nodeRepl.fetch request failed`。用户明确要求重新打开后，已用原生 Chrome 新标签打开 AlphaEngine，由用户自行登录；只读取用户当前打开的 Claw，不恢复抢夺 FinGPT 前台。
- 用户手动打开 Agent 日程后，AX 与截图均确认独立任务表：名称、模型、最近执行时间/结果、执行频次、下次、启用开关、更多操作；顶部为搜索任务名称、权限模式“智能授权”、新建任务和提醒说明。云端运行的“每日收盘点评”显示 DeepSeek V4.1 Flash、10/14 15:30、成功、启用、17 小时后。
- 频次摘要实际显示“下午 15:30，仅周一、周五”，与历史创建工具的 `MON-FRI` 不一致；保留为文案/定义差异待核实，不能据此推断实际调度，也不能照搬为本产品频次算法。用户手动展开后实际读到菜单四项：编辑、立即运行、执行记录、删除。原生“编辑”点击未生效，等待用户只打开编辑表单；未运行、删除或改变任务开关。
- 用户只打开既有编辑表单后，截图与完整 AX 值双重确认：频率“每周”、15:30，周一至周五 `Value: 1`，周六/日 `Value: 0`；模型 DeepSeek V4.1 Flash；任务内容为修改后五项要求（指数/板块/热点/资金、T-1 北向和两融、技术面、次日关注、外围市场），245/10000 字符。可见任务名 6/50、会话归档“不分组”、飞书和微信推送均 off；可见表单没有时区字段，不推断隐藏值。列表摘要没有完整反映编辑器星期选择，实际调度仍未从接口/运行行为独立核实。
- 编辑弹框提供“让AlphaClaw帮您编辑任务，更快捷”、关闭、取消、保存入口；不触发编辑助手、不输入、不保存。调查没有创建额外任务或主动改变参考任务定义。
- 用户取消后打开执行记录，AX 与截图显示仅一条 `2026/10/14 15:30:12 成功`，已显示 1/1 条、已加载全部记录；没有显示原对话的两次试跑，也没有可见报告/会话链接，用户点击记录行后无变化。不得把“未观察到链接”升级为服务端不存在关联；对话试跑与定时运行是否共用后端执行链仍未知。
- 此时任务表的频次文案变为“下午 15:30，仅工作日”，保留此前“仅周一、周五”的前后观察；无法仅凭本次只读调查确定是页面重算、缓存还是其他变更，不能认证服务端定义没有变化。
- 日程权限下拉经用户只展开后，由 AX 与截图确认两档：“手动批准”（需要权限时，始终会请求您批准）、“智能授权”（仅高风险操作会请求您批准，当前选中）。它与聊天编辑器“免确认”是不同可见入口；未确认底层权限实现是否共享，不切换模式，也不扩展本产品已批准实现范围。
- 用户点击日程“新建任务”后，实际返回 Claw 首页并在中央输入区预填 `帮我创建定时任务:`，不是新建配置弹框。发送按钮可用但未提交，未创建任务；已有“编辑”才打开结构化表单。本产品对应 `claw-workspace.mjs:renderClawSchedules` 的 `data-claw-case="schedule"`，也只预填澄清草稿，不直接创建或运行。
- 技能·专家页再次确认搜索、对话创建 Skill、添加 Skill、用户分享/官方/我的技能；分类包括综合投研、公司研究、投资策略、宏观周期、行业赛道、固定收益、量化研究、选股策略、技术分析、效率工具、基金甄选、期货期权及更多分类。隐藏已安装未勾选，综合排序，共享发布入口与推荐区。卡片包含名称/简介/分类/作者或机构/日期/热度/添加；这些是目录声明，不认证能力可调用或卡片所宣称工具数。等待用户只打开详情，不安装或发布。
- 用户只打开 `technical-analysis` 详情后，实际读到名称、作者、分类、更新时间、热度、简介、“Skill 使用案例”、查看案例详情和文件、添加到我的 Skill；未见独立版本、资源清单、权限说明，不推断其不存在。示例展示历史问题、9 次调用（8 成功/1 失败）、表格和报告，正文明确说明澄清超时后自行采用周期/偏好假设；此行为只记录，不复制为本产品的隐式授权。
- “查看案例详情和文件”实际打开独立的“technical-analysis 使用案例生成会话”视图，保留问题/时间/工具汇总/完整报告/复制/PDF 导出；本次全页 AX 与当前截图未见可用文件入口，也未触发下载。未添加 Skill，未运行案例；工具展开与失败恢复链路待进一步观察。报告金融数值不属于本产品数据验收或投资结论。
- 案例“展开全部”后实际显示九个卡：Skill 67ms、AskUserQuestion 5m 0s、task 1m55s、read 81ms、bash 215/547/393/448/449ms；截图红点对应 AskUserQuestion，其余卡绿点。说明/工具按回合穿插，正文说明超时后采用标注假设，随后发现均线单位异常、读取原始行情自行复算、再补算 ATR/突破位/TD。这里只认证回放展示，不认证金融计算正确或真实并发时序；单卡输入/输出待展开核对。
- 展开的历史 AskUserQuestion 输入包含两项各三选：操作周期（中线推荐/短线/长线）与单次回撤（稳健推荐/保守/积极），有描述与推荐标记；错误区仅显示“任务执行失败”和复制错误，无可见错误码。“用户未响应”来自后续说明，不能冒称已取得机器超时码；推荐项或该案例自行采用的假设不等于用户已批准。
- 用户再展开 Skill/task/read/首个 bash：Skill 输入是能力名；read 输入为内部临时 MD 路径；bash 输入是目录检查命令，均未见输出正文（不能推广到其他调用或当前完整接口）。task 展示“16 已完成（1分55秒）”可收起的子调用列表：加载金融查询 Skill、研究洞察、读取文件、基础数据库的个股及指数行情/区间/技术指标/日行情查询、再次研究洞察、文件筛选；各项有状态与耗时。主调用 9 与子调用 16 是不同层级，不合并成同一成功分母。只读历史，不执行复制来的命令，不把临时 MD 认证为交付文件。
- 新增界面差距：本产品目前活动卡可显示 Agent 归属，但主/子活动的分层与计数、子任务折叠摘要仍需对照原生事件实现；不得以隐藏失败或只改计数掩盖此前真实工具权限/参数失败。此项先登记，整页调查与事件合同未完成前不臆造子调用或结果。
- “我的技能”实际载入 14 项既有能力（含快速研究、查询金融数据、超级研究、AlphaEngine CLI 等），并非空态；筛选为全部/来自市场/来自分享/我添加的。每卡有更多、立即使用、停用开关以及分类/官方标识；本次 AX 未提供开关 Value，不能从“停用”动作名称反推实际状态，不切换开关。目录登记与可调用仍分开；仅查看既有能力，不安装。
- 快速研究卡的“更多”实际打开能力详情弹框，显示名称、来自市场、2026.09.11 更新、说明、关闭、停用、立即使用；并非通用 CRUD 菜单。本次这项未见编辑/删除/分享，不推断其他来源或自建能力也没有这些操作。等待只点击立即使用核对会话准备，不提交研究。
- “立即使用”实际回到 Claw 首页，在输入区放置独立 `/ae:quick-research` 标记和移除按钮，正文输入框为空；没有直接执行研究。原生日程新建也是准备草稿，两条链均不可误做立即运行。自动写入一次性研究草稿未生效，已核对输入仍空；请用户发送已批准的普通研究测试（pandas/Polars 官方 CSV 文档对照、表格、可点击来源、访问日期、Markdown 文件），明确不创建/修改日程。发送及实时过程待观察，不提前记运行成功。
- 用户已手动发送上述一次性测试，出现新会话“Pandas与Polars读取CSV对比及生成Markdown文件”，页面时间今天 23:07，模型 DeepSeek V4.1 Flash · 预置模型。第一回合说明先加载能力，Skill 卡 `ae:quick-research` 25ms；页面显示思考中、耗时/token 指标，正文/附件/工具/免确认控件禁用，保留停止生成按钮。属于本次实时参考产品观察，不是本产品真实模型验收；检索、完成和文件仍待观察。
- 后续同一原生 App 句柄连续 AX/截图停在旧思考状态；用户确认已完成后重新 `cua.getApp` 才读到完成视图，确认观察通道存在旧快照风险。不能把这段未变化认证为服务端卡死，也不能宣称已取得完整逐时流式证据。
- 新窗口快照显示 16 个工具调用、16 成功；原对话为完成说明+延伸思考+MD 文件卡，右侧 Canvas 自动打开报告全文，包含对照表、官方来源链接/访问日期/页面版本与无法核实章节。文件按钮展示内部 tmp 路径，文件卡有 PDF 导出和下载，Canvas 另有下载文件；这里只确认界面呈现，下载字节与真实请求尚未核对。普通研究与无文件案例存在不同结果布局，不能一概当作单一气泡全文。
- 用户下载后 Chrome 明示 `csv-reading-comparison.md 6.9 KB · 完成`。本机指定文件实际为 7102 字节、UTF-8、5 个标题和18行表格；来源域名仅 `pandas.pydata.org` 与 `docs.pola.rs`，含无法核实章节。已保存 `.codex/acceptance/claw-full-20261014/alpha-ordinary-original.md` 与 proof JSON，SHA-256 `7bcfe0f0c04b4d4e71bfd10fa5ed83354002404acbd24dbbe73229460731a6ac`。证明真实下载与文件结构，不认证技术结论逐条正确，也不是本产品交付验收。
- 展开后主链为 Skill→临时目录检查→两路 task 检索→两次 read→发现第三方证据不足→五次 webfetch 官方页面→write 官方证据→task 报告→两次 write→canvas。叙述明确第一次报告只含第一部分，随后合并重写；属于工具表面成功后的内容质量修正，不应混同工具失败。主卡保留实际说明、参数摘要和耗时，最终报告与 Canvas 均可查看。HTTP 方法、请求参数与流式协议仍未取得。
- 已准备同会话续答：增加最小 CSV 与两库代码（仅展示，不安装/执行）、保留原内容和来源/限制、另存 v2 文件并说明变化，不创建/修改日程。用户发送及第二次文件交付待观察。
- 用户已在同一 CSV 会话发送修改要求；当前窗口快照确认原问题和续答同时保留在回合导航中，原文件/Canvas 仍显示第一版，第二回合出现独立思考状态、禁用输入与停止按钮。此时尚未确认 v2 交付，不能把上一回合“16 成功”当作本回合成功。
- 第二回合完成后，实际回放为 read 原报告 131ms→write v2 202ms→canvas 677ms；同会话给出修改点及两个文件入口，Canvas 改为 v2。用户下载的 v2 为9934字节，SHA-256 `a33f9abbf122f95855b7e6acb3b882e5b6443d5e6bf090bb1d34d72410ac3682`；原正文完整保留为 v2 前缀，原下载哈希未改变，新增 CSV 代码块及两段 Python 代码，原来源/限制章节仍在。已保存 `alpha-ordinary-v2.md`、proof JSON 与11项结构化观察账本；示例未执行、技术结论未独立验真，普通研究两轮 UI/下载链路闭合不等于全页面/HTTP/本产品验收完成。
- 侧栏收起后，AX 明确提供“展开侧边栏”按钮，截图确认其在工作区左上角可见，全局模块轨保留，当前对话与右侧 v2 Canvas 共存；表格在 Canvas 内水平滚动，未遮挡展开入口。等待用户展开后核对恢复及键盘方式。该截图同时确认本轮 write 卡会显示真实输出摘要（创建路径、9934字节、107行），read 与 canvas 显示输入路径；此前部分历史卡仅见输入不能推广为所有工具均无输出。
- 用户明确反馈已用键盘展开；随后 AX 确认会话/工作区/收起侧边栏/日程/技能/IM/连接器/模型导航恢复，当前 CSV 会话和 v2 文件/Canvas 仍保留。认证范围为用户操作反馈+恢复后状态；未采集按键瞬间，不冒充自动化键盘驱动成功，参考窄屏/移动与焦点序列仍待调查。
- 工作区切换实际替换左侧栏为“云端工作区”文件树：搜索、更多操作、`/.alphaclaw` 根目录，已用空间1.57M/2.00G；中央 CSV 会话仍保留。不是中央项目管理页，根目录内容待只读展开。本产品仍按已批准本地项目聚合与显式跨会话引用边界实现，不因参考云端根目录而增加云执行或共享正文。
- 用户展开根目录后可见 `skills`、`tmp` 两个子目录；只列目录，未读技能配置或其他文件内容。虚拟树根 `/.alphaclaw` 与工具显示的 `/alphaclaw/.alphaclaw/tmp` 前缀不同，只记录表象，不由路径推断容器、操作系统、存储或服务端目录映射实现。
- tmp 展开后同时列本次 v1/v2、官方证据/两路检索底稿及原收盘点评的多个中间 MD、finance_data 子目录；只观察文件名，未打开其他研究内容。文件树未见来源会话字段，不能因此取消本产品的项目/来源/显式引用约束。工作区更多菜单实际为排序方式、刷新、上传、新建文件夹，均未执行；单文件菜单待用户只读展开。
- v2 文件菜单实际为对话中使用、拷贝、粘贴（禁用，提示先拷贝）、创建副本、重命名、移动到、下载、导出、删除；未执行文件变更。用户只点“对话中使用”后，在当前输入框插入文字 `@.alphaclaw/tmp/csv-reading-comparison-v2.md`，发送按钮可用，没有自动发送或另建会话。本次只认证路径引用的前端行为，不认证后端挂载、复制、读取或跨会话权限。本产品继续使用已登记文件 ID/哈希/来源会话的显式引用合同，不接受任意本机路径。
- 连接器从会话侧栏底部打开共用设置弹框，导航包括积分/连接器/IM/我的模型/记忆；当前 iFind、IMA 可配置，已安装0。用户仅打开未配置 iFind 表单：MCP JSON 文本区（示例 mcpServers）、自动提取配置、必填 Authorization Token、按端点分别配置、默认实例级认证继承说明、取消/保存。只采集标签和说明，字段值过滤；未填写/测试/保存，端点配置待展开，UI 字段不等于已核实 HTTP 请求键。
- 展开 iFind 端点配置后显示股票/基金/宏观/新闻四类，每类可继承实例认证；说明写明公共 Authorization 自动提升到实例级，不一致端点保留覆盖。只观察未保存表单，不切换实际认证，不填写 Token，不据此认证实际 API 地址/请求键/认证有效或可取数。
- IMA 未配置表单只见必填 Client ID、API Key，官方获取入口 `ima.qq.com/agent-interface`、“让AlphaClaw协助安装”、取消/保存。仅记录字段与入口，未采集字段值、打开官方认证页、触发协助安装或提交配置；该入口不能当作已安装或可调用证据。
- 我的模型实际显示“添加自定义模型”表单：Kimi/MiniMax/智谱/DeepSeek/Qwen/火山方舟供应商，Coding Plan 与 API 按量入口、Key 获取说明、Key 输入、可添加模型单选、取消/添加（未填时禁用）；当前默认表单列 Kimi 的 kimi-k3/kimi-k2.7-code/kimi-k2.6。字段值过滤，不填写/添加/切换实际会话模型，不认证套餐价格/额度文案或模型可调用。其他供应商分支与真实认证未展开/验证。
- IM 渠道页确认微信/飞书、已接入0，微信 ClawBot 扫码绑定、飞书配置引导/扫码入口。未生成绑定码、执行引导、接入或发消息；不增加本产品远程 IM 实现，绑定接口和异常状态未验证。
- 记忆页只采集管理控件，见“启用记忆”开关；不采集正文、编辑字段名称或值，不切换、不编辑/清空/保存。记忆文件/检索机制仍未知。为补前端映射，已请求用户关闭设置后仅保存公开 CSV 测试会话的“网页，全部”，只提取脚本资源，不导出或读取 Cookie/HAR/认证值/记忆内容；资源是否完整及静态分析尚待确认。
- 用户保存 `Downloads/AlphaClaw.html` 及资源目录后，只解析 script 引用并复制选定的4份静态宿主 JS（2851345字节），没有把 HTML 正文、表单、记忆、图片或浏览器存储复制进证据。此前403的宿主 index/common 已取得；不执行下载脚本，也不发布第三方原始资源。
- 宿主 `AlphaClaw.4d68c3f0.js` 明确由 QiankunMicroAppHost 加载 `window.location.origin + /alphaclaw/index.html`，传入 `apiBase: /alphaclaw`、`socketPath: /alphaclaw/socket.io` 以及用户/配置/认证字段引用；没有读取这些字段的运行时值。属于前端代码推导，不是实时请求或服务端实现证据。真正微前端 JS 不在此宿主集合，已请用户只保存源码声明的入口，不重新登录。
- REA 宿主静态分析 Evidence `ev_0c4e900aadb1ad596008045953646dbfb432ed60509ff8561adcbea7a43e1679`，parent `ev_07665983aee4524bec0f4932dcbb65585d31f05601bc25b730c607c16a617945`；4份JS解析成功、0 parse failures，图覆盖 partial，common展开超出结果预算、语义预算耗尽、模块统计0，不能称完整应用重建。完整摘要另存 `alpha-host-rea-summary.json`；未重复生产同一大结果或把截断预览当完整证据。
- 独立入口实际跳至 `/alphaclaw/chat`，渲染“云主机初始化：请求失败 404”“模型加载失败”、重试/刷新入口，输入/附件/工具/发送禁用。只观察错误，不重试、不登录、不启动云机；错误请求 URL/方法未知，不把 UI 的404当作已捕获 HTTP 记录。微前端依赖宿主 props 是待核实的原因假设，不认证为404根因。已请用户直接保存此错误页资源，以取得已加载业务脚本。
- 错误页已保存为 `Downloads/AlphaClawMicro.html`，资源目录仅图片，未含业务 JS；只解析 script 元数据与无认证标记的短启动脚本引用，未输出 HTML 正文或表单内容。从动态 import 精确取得 `/alphaclaw/assets/index-CywjV4PZ.js`，已请用户通过正常 Chrome 打开并仅保存文本，不猜资源名、不运行脚本。
- 已取得实际业务包 `Downloads/AlphaClawApp.js`，8968980字节，SHA-256 `885a4098a21d41852c471008eea6a85b6c1304edd0a6abe943715e1d16529a14`，不是 HTML 错误响应；仅复制至忽略证据目录 `alpha-micro-static/index-CywjV4PZ.js`，未执行。末尾明确声明 source map 名 `index-CywjV4PZ.js.map`，已请用户只尝试该声明地址，不猜替代地址。请求/事件静态范围与界面静态范围分工只读调查，结论与实际 UI/HTTP 分开。

以下为最初调查矩阵，保留当时缺口；source map取得后的当前覆盖、修复和未验证项统一见[前端源码调查与差距](2026-10-15-claw-source-survey.md)，不能将下表旧缺口当作当前实现结论。

| 元素族 | 初始参考状态 | 本产品链路/接口 | 初始差距与后续证据 |
| --- | --- | --- | --- |
| 全局模块轨、侧栏展开/收起 | 外观已观察；本轮状态部分调查 | shell / 本地 sidebar 状态、焦点恢复 | 需实测参考展开、键盘、窄屏 |
| 会话/工作区、搜索、新建 | 入口已观察；内部部分调查 | app/core / POST sessions、GET session、项目 GET | 参考搜索与工作区弹窗待调查 |
| 分组、会话更多操作 | 入口已观察 | app / 项目 POST/PATCH、会话 PATCH/DELETE/restore、归属 PUT | 参考菜单和归档状态待调查；不得为取证删除原记录 |
| 首页分类、案例与回放 | 既有首页截图 | claw-workspace / 本地案例填草稿 | 参考回放内部待调查；不伪造本产品回放 |
| 技能·专家 | 本轮目录实际观察 | capability workspace、composer / capabilities | 参考用户分享/官方/我的技能、分类/隐藏已安装/排序；详情与添加确认待调查，不安装 |
| IM | 本轮弹窗实际观察 | 不增加远程 IM | 微信/飞书、扫码绑定、配置引导、已接入 0；不生成或保存绑定 |
| 连接器 | 本轮空态实际观察 | 能力中心 connections/MCP | iFind、IMA 配置入口、已安装 0；配置表单与接口待调查，不保存凭据 |
| 模型、记忆、积分 | 共用设置入口实际观察；内部未知 | settings / 现有模型配置 | 页面切换受原生输入失联影响，不扩展秘密权限 |
| 输入、附件、能力、工具 | 参考入口已观察 | composer / uploads、message、Tabbit scope | 弹出菜单、拖放、禁用状态须补实测 |
| 提问、回答、工具执行卡 | 原日程完整历史实际观察 | views + projection / questions、原生 tool/call/result | 本产品缺主对话工具卡；调用参数被结果覆盖 |
| 创建/修改日程 | 完整原对话实际观察 | drafts / prepare、confirm、dismiss | 保留显式点击批准，与参考自动创建差异明确 |
| Agent 日程 | 既有真实表格证据 | automation / list、run、enable、disable、delete | 周一至周五不照搬参考仅周一/周五摘要；手动运行不可显示未执行 |
| 试跑报告、活动、来源、文件 | 参考 9/6 工具摘要、报告、引用实际观察 | run snapshot + execution detail/files | 本产品报告原为纯文本；活动只在侧栏；执行格式误显示无需文件 |
| 复制、导出 PDF | 参考按钮已观察 | 新增本地回复复制；真实导出机制待确认 | 不能以按钮存在证明 PDF 文件成功 |
| 停止、断线、错误、重试 | 参考未知 | cancel、SSE、错误提示、幂等受理 | 独立测试，不触发参考故障或扩大权限 |

## 接口与实现映射

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"显式格式使用现有文件助手与交付校验，默认调用仍兼容，内联预览沿已有会话文件端点和沙箱，不引入文件复制或另一个生成引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"模式记录初始共享祖先验证与既有后置身份契约对齐，私有父目录和文件验证不变；没有新增生命周期进程、端口或权限。","diagrams":[]} -->

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"复用现有消息、Markdown和活动渲染，在同一详情投影内穿插原生证据与不可变运行快照；没有新页面服务或渲染引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"现有会话详情增加安全证据与执行快照字段，续答沿同一DSH受理；没有新增请求执行循环或进程边界。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"在原生guard已有pre-step边界使用固定DSH会话级工具目录限制，保留执行veto与原私有认证通道，无新runtime或全局授权。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"只读取现有Run不可变定义快照并约束执行续答，Automation仍负责所有调度和Run，不新增定义持久模型。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"原生桥补manifest身份和受限错误码，Provider和Broker校验路径不变，不增加数据源或调用权限。","diagrams":[]} -->

本产品统一前缀 `/api/research`。下列是源码确认，非 AlphaEngine 同名接口：

- 会话：`POST /sessions`；`GET/PATCH/DELETE /sessions/{sid}`；恢复与永久删除独立入口。发送 `POST /sessions/{sid}/messages` 携幂等键，停止 `POST .../cancel`，`GET .../events` 使用真实 snapshot/runtime_error SSE，断线不重发请求。
- 项目：`GET/POST /claw/projects`、`GET/PATCH /claw/projects/{id}`；`PUT /sessions/{sid}/project`；文件引用 `POST /sessions/{receiver}/file-references` 校验来源会话、文件身份和期望哈希，复制后仅加入草稿。
- 对话确认：原生 questions/approvals 各自 POST；日程 drafts confirm/dismiss，确认创建并启用不试跑，启用失败重试不重复建任务。
- 日程：`GET /automations`、`GET /automation-runs`；任务 run/enable/disable 独立 POST，删除独立 DELETE。Run 保存定义快照、版本、trigger 和 execution session，修改后旧 Run 不变。
- 文件与数据：上传 multipart；files/preview/download 受当前会话路由约束；datasets 保存实际查询、来源、日期、字段、缺口和哈希。
- 工具桥：原生目录→guard→会话级准入→DataHub 内部 business-query/cancel。受控 loopback 认证值不记录；公开数据错误需返回稳定安全原因，不透传原始秘密或整个响应。
- AlphaEngine 已观察的是原生工具名 `scheduled_task_list/create/update`、`AskUserQuestion` 及其历史参数/结果；HTTP 方法/路径、流式事件、重试协议尚未捕获，不推断为上述本产品接口。

## 已修复与实现映射

| 源码 | 改动与约束 | 对应测试 |
| --- | --- | --- |
| runtime/guard.mjs、research.cordis.yml、service.py | 固定 DSH 会话级 tools.restrict 收窄目录，保留执行 veto；运行续答绑定不可变快照；原生提问绑定当前任务与版本 | guard、API、automation_research_task |
| runtime/public-data.mjs | quote/quotes、日期契约、安全错误码及 query/provider_query/coverage；注册不等于可调用 | public_data |
| projection.py | 真实序号、参数/结果/错误/耗时分开投影；递归脱敏并按 UTF-8 字节限制 | protocol |
| ui/app、core、views、claw-workspace、composer、styles | 原生回合穿插、真实 Run ID 定位、Markdown 沙箱报告、复制、不可变执行格式、确认回执、草稿受理清除 | claw_redo、UI、capabilities_ui |
| resources/research_helpers.py | write_deliverables 显式 formats，只选 MD 不生成其他格式；默认四格式仍兼容 | artifacts |
| runtime/research-tools.mjs | research_task 输入一致性预检；仅真实 PermissionError 增加已知相对路径恢复提示，不改权限或 stderr | automation_draft_tool、method_tool |
| automation/drafts.py、automation/service.py | 历史确认快照；启用重试在同一定义锁内 CAS，旧确认不得启用新版本；缺回执 409 | automation_research_task、drafts、service、routes |
| runtime_mode.py | 共享祖先身份校验容忍合法兄弟目录变化；私有父目录、文件、FD、链接与归属检查保留 | runtime_mode、docker_runtime |
| test_delivery.py、test_docker_runtime.py | 夹具使用正式 DSH 会话契约；健康轮询计时隔离，避免全局 time.sleep 捕获无关等待 | delivery、docker_runtime |

## 真实候选验收

候选 Web/DSH 为 18190/13190，固定 DSH 为 48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0。正式服务未改动。证据根为本 worktree 的 `.codex/acceptance/claw-full-20261014/`。

- 普通研究会话 `dfd59944-ce1e-4065-ab6d-fe911823d2fe`：实际原生澄清、公开文档比较表与来源、修改续答；原生完成序号 67/82。修改文件 pandas-polars-review-v2.md 为 22779 字节，SHA-256 b5ef519ebd8493a2a7e2dbbe02b226c3c689c8b95904a2bc310c751af89fdcfd。首次助手默认生成额外格式及 Path 序列化失败保留，不能称首次流畅通过。
- MD-only 会话 `f353ce8c-6278-4567-9c68-a6243bbb2485`：真实 turn/end 序号 41、reason completed；delivery completed、required_formats=[md]、只有一个 MD 文件，2469 字节，SHA-256 209f500ec85c0ad1b27c0970e066fe2e39dca049cb5091efe311068a333a3e32。验收提示错误使用不存在的 build_report_package，造成一次失败；模型查询后改用真实 write_deliverables 成功，错误未掩盖。
- 新验收任务 `automation-cf9a3168709567b328eedaac76e0105956b4917026f91c8683d05bd7ae256ba9`：名称“每日收盘点评·全页面验收”，创建并启用后运行数为 0；修改保持同 ID，从 v1 到 v2，名称、模型、时间、权限、格式与下次时间均不变。原有“每日收盘点评”任务未修改。
- v1 手动 Run `automation-run-51f1cbba165645e9b3a0030690a00ff1`，执行会话 `255e6980-86be-487d-a213-82cd73386fd3`：真实完成事件序号 51；5 项活动，其中 1 项目录探测失败、后续恢复；MD 12555 字节，SHA-256 a8629afccf43c10a12f626129f5c8990aa291c26e9fa601346b0299e271aa200。
- v2 手动 Run `automation-run-fecf1e903b45438f9059653b9bb56517`，执行会话 `e74f7bca-0aec-460b-b9b2-20da9172a9d4`：真实完成事件序号 70；8 项活动，其中 3 项重复目录探测失败、最终恢复；MD 18000 字节，SHA-256 a1edfb30c697f318d97808b74d08a91ad225e3d3534ae3d4906ddbfbb707c3c2。
- 两次运行均未调用未批准 Skill、子 Agent 或 datahub。两张 Run 卡刷新后保留 v1/v2，按实际工具结果定位；完整 MD 预览为独立执行会话来源、空 sandbox iframe；执行会话明确显示 MD 和批准范围。
- “增加”首次仍为普通文字澄清，后续原生提问通过；“需要”第二次试跑前仍需要额外人工提示才形成原生问题。已补提示并保留实际引导；不能宣称自然简短续答无引导全程通过。
- 研究内容 **LIMITED**：搜索只取得标题/摘要，未逐页核验；T-1 报告把 2026-10-10（周六）写成前一交易日，日期口径验收不通过。指数点位、全市场资金及专业行情缺口独立保留，运行与文件完成不等于收盘研究合格。
- 桌面侧栏收起后 Enter 展开；1050px drawer Escape 关闭；390px 移动关闭后焦点返回，documentWidth=viewport=390，无横向溢出。深色执行定义/工具状态实测并恢复原主题。响应截图与 responsive-proof.json 已保存。首页草稿跳过存储的缺陷已修复，真实即时刷新恢复“草稿保留验收：尚未发送”；授权、能力等不随草稿恢复。
- 两次试跑后仅停用本轮新增验收任务，避免后续定时模型调用；记录、定义与文件保留，原有任务仍启用且未改动。

## 全量调查缺口

参考已捕获 99 个技能/设置控件，保存角色、标签、来源行与状态，**不是全页面调查完成**。本产品候选 OpenAPI 目录包含 80 路径、95 方法及请求/响应 schema 引用，仅证明本产品接口，不能冒充 AlphaEngine 接口。

初始脚本403与原生输入失联的阻塞记录保留，但不再代表当前覆盖：用户已完成普通研究及修改、两版下载、日程/技能/工作区/设置的只读导航，并保存实际业务包及声明source map。已提取404模块、索引567项模板声明和155个HTTP调用点；30个Pipeline handler已静态审阅。详见[前端源码调查与差距](2026-10-15-claw-source-survey.md)。当前调查为 **PARTIAL**；实时HTTP trace、服务端实现、参考移动布局及全部动态状态仍未验证。内置浏览器不共享Chrome登录态，继续保留单处登录，不复制Cookie、不调整调试端口、不争抢FinGPT窗口。

## 验证状态与交付边界

最终 Router 为 L4，全变更集规划。485 项 JS 全部通过，无跳过；文档治理 89 份当前文档/610 文件、Python 索引与完整性检查通过。Python API/协议/日程/产物/交付/模式/生命周期/本机集成共 836 PASS、1 Windows 原生专属 SKIP，耗时 762.29 秒；冻结后版本原子保护与模式/平台增量 203 PASS，耗时 3.16 秒。旧全 Python 3361 PASS/10 SKIP/2 FAIL，两个失败分别由 delivery 夹具和共享目录身份校验闭合，保留原记录。最新 Docker 375 PASS/1 FAIL 为全局计时器捕获 Native/SQLite 等待；隔离后完整 Docker 模块 358 PASS，耗时 210.66 秒，不删除原失败记录。

实际最终命令（证据文件保留完整输出，后续新增修复以聚焦增量闭合，不将旧全套重新标为无失败）：

```sh
DSH_SOURCE_ROOT=/Users/leon/.research-workbench/acceptance/claw-redo-20261013/runtime/dsh/48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0 node --test tests/javascript/research_web*.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs tests/javascript/docker_runtime_contract.test.mjs
PYTHONPATH=/tmp/rwb-claw-redo-tests-20261013/lib/python3.12/site-packages .venv/bin/python -m pytest tests/research_web/test_api.py tests/research_web/test_protocol.py tests/research_web/test_automation_research_task.py tests/research_web/test_artifacts.py tests/research_web/test_delivery.py tests/research_web/test_runtime_mode.py tests/research_web/test_service_manager.py tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q
PYTHONPATH=/tmp/rwb-claw-redo-tests-20261013/lib/python3.12/site-packages .venv/bin/python -m pytest tests/research_web/test_runtime_mode.py tests/research_web/test_platform_capabilities.py tests/research_web/test_automation_research_task.py tests/research_web/test_automation_drafts.py tests/research_web/test_automation_service.py tests/research_web/test_automation_routes.py --confcutdir=tests/research_web -q
```

Ruff、Black、isort 核对全部变更 Python 文件；mypy 核对 5 个研究源码文件及 runtime_mode。后者使用证据目录内配置，仅关闭 stdlib stub 的 follow_imports_for_stubs，保持标准库类型分析与原产品配置不变，避免已有 dataclass stub 错报；不能称全仓库 mypy 通过。

启用版本漏洞由独立评审真实复现，3 RED→GREEN，4 个相关模块 83 PASS；线程竞争、旧版本及缺回执拒绝、正常重试、停用后重放与删除后重放保留。其余独立 Python、JS、安全边界评审无重要缺陷。

本轮尚未发布新候选、执行新 SHA CI、合并、正式部署或清理。旧 PR103 与旧 SHA CI 保留，不能用于证明本轮新源通过。后续发布遵守本任务明确授权及不合并/部署/清理边界；Windows/Linux 产品 dispatch 仍交对应设备。整体调查状态为PARTIAL，局部修复与文件验收逐项记录，不登记“全部完成”。
