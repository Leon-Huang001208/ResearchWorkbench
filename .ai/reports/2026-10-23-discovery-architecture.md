# 今日发现架构与文档核对（2026-10-23）

宿主范围为macOS功能开发，Windows/Linux原生、真实模型、生产跟踪与常驻部署均不由本报告认证。

<!-- architecture-review {"group": "ui", "structure": "changed", "reason": "新增今日发现真实来源页面、冻结确认和独立跟踪交互，原情报栏目保留；03序列说明用户只读/准备/执行边界。", "diagrams": ["03-research-sequence"]} -->
<!-- architecture-review {"group": "research-api", "structure": "changed", "reason": "Host新增严格发现接口及同一DSH创建/单次提交分支，未知只查询，原质量门覆盖FinGPT和Claw；03保留真实顺序。", "diagrams": ["03-research-sequence"]} -->
<!-- architecture-review {"group": "datahub", "structure": "changed", "reason": "新增golddata_intel规范JSON归档与显式跨会话复制，复用原原子快照但有独立资料入口，04新增真实冻结分支。", "diagrams": ["04-data-file-flow"]} -->
<!-- architecture-review {"group": "automations", "structure": "changed", "reason": "原Automation新增独立同意的窄跟踪适配和任务委派/恢复选择，02在原Host和调度节点内标出此路径；不新增第二调度器。", "diagrams": ["02-module-dependencies"]} -->
<!-- architecture-review {"group": "files", "structure": "changed", "reason": "Store新增懒交接/跟踪元数据与预分配会话创建阶段，DataHub保留规范JSON与上下文哈希，04显示新文件流。", "diagrams": ["04-data-file-flow"]} -->
<!-- architecture-review {"group": "private-multiuser", "structure": "changed", "reason": "网关从启用账号的持久同意中经原Pool容量门恢复owner后端；窄跟踪与泛用Automation关闭区分，01新增恢复准入边。", "diagrams": ["01-deployment"]} -->
<!-- architecture-review {"group": "discovery", "structure": "changed", "reason": "新增Host内来源投影、严格选择、JSON冻结、预留身份、单次执行与独立跟踪模块；03/04记录新顺序和归档边。", "diagrams": ["03-research-sequence", "04-data-file-flow"]} -->
<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "仅在原Checks同一Python步骤追加三份离线模块、原Mac安装同一步追加两份静态资源；job/runner/timeout/平台dispatch/质量门及08验证治理拓扑保持。", "diagrams": []} -->

## 源码身份与证据

审阅基线 `3a62ca1a3bff0927db681322a1ff028f08cf03cd`。工作区源码文件哈希清单保存在 `logs/discovery-architecture-source-identity.json`；它只绑定此时源码快照，不冒充最终SHA、已提交源码或CI checkout。图源/HTML由各自deliver receipt逐字节绑定，该阶段源码reading pin暂沿旧真实提交；真实源码checkpoint绑定在本报告后续记录，未用旧pin伪指新模块。

## 已执行与限制

四图均经现有Archify展示规格deliver 9/9、零错误零警告；四视口containment已实跑，另有1440浅/深及2048浅/深截图。Agent实际查看每图1440浅色与2048深色，不冒充用户人工批准；自动visualReview保留pending。03保留完整12参与者/48消息，全览文字密集需路径/缩放；04保留原右侧留白。初版01多一张说明卡、03增加高度使1440溢出，已合并卡片及压缩消息间距（至少28px、不缩字体）修复；初版路由碰撞依诊断修复，未删除旧流程。

新事件源的raw-0001.bin是已解析detail与选择包经json_bytes规范化的JSON，不是HTTP压缩/空白等传输原字节，也不是Host抓取网页全文；来源仍是golddata_intel第三方归档。

CI只修改既有两处名单，无新增workflow/job/runner/timeout/依赖或平台dispatch；requirements/web.in/web.lock/setup_web.py已核对并保持。只读GitHub PUBLIC快照与历史run预算保存在日志；未发起CI或模型/服务动作。原16项手动合同及110项旧闭包为阶段证据，最终完整Router、独评、同候选CI和部署由主任务单独留证。

新模块权威说明为docs/research-web-discovery.md，所有受影响group的必需模块文档、架构inventory、11条发现API及1条当前账号恢复状态API、公开安装静态名单及生成索引同步。根README已阅读并更新入口，其复核回执记录本轮updated。

## 文档门结果

2026-10-23本机执行check_research_architecture（基线3a62）通过；check_doc_sync通过，包含架构、documentation-governance与py_file_index。日志分别为logs/discovery-architecture-check.log和logs/discovery-doc-sync.log。这是文档工作区快照检查，不代替最终提交Router/CI。后续源修复已同步显示字段绑定、完整详情跟踪基线/批准事件、同UUID配置恢复及Host真实质量关联；root最终候选若继续改源码仍需重验索引/身份。

## 选择详情预览补齐

新增GET /api/research/discovery/selection已按真实routes.py登记；只从owned预览的event_ids读取完整详情，独立scope feed不污染首页，GET不写Store/创建会话/调用模型。新研究/跟踪抽屉先核对，再freeze/save；未知与已prepared沿原身份。原03序列的准备步骤补充此只读详情核对，不新增运行节点或第二模型边。此阶段尚待root真实checkpoint，后续绑定记录如下，不将早期阅读pin冒充新模块源码。

## 真实源码阅读绑定

源码checkpoint为`e4d33c76ce9453d73c7286f796ac44c1b753c208`，已从Git对象逐一读取13份发现模块/UI/测试文件并与当前文件逐字节相等核对，包含真实GET /selection。architecture reading.repository.revision现固定该已提交完整源码，API Atlas/index重新生成；绑定证明保存logs/discovery-reading-source-pin.json。图源/HTML未因阅读链接改变，无需重新伪造图交付或截图回执。此绑定不认证远端CI、部署、生产计划或真实模型质量；最终交付提交仍由root独立回执认证。
