# 个股、资讯与问答场景交接

macOS Web 功能实现，复用现有 Host、DataHub、唯一 DSH 和报告质量链。八个合同取自
`app/research_web/scenarios/`，不修改冻结目录，不引入模型调用、数据源、秘密或依赖。

## 用户流程

FinGPT／Claw 输入区和个股页标题提供“研究场景”。原个股“交给 FinGPT／Claw”按钮进入同一实际
表单。搜索和选择仅读取当前目录；输入规范证券／行业分类／独立主题、明确研究截止日、问题，
勾选已经取得的快照；历史复盘另需起点。技术面使用目录声明的 `chanlun`，其禁用、比较证据及
原生发现门保持，不换成公司研究，也不声称等同华创专有模型。

确认冻结后显示方法、版本、原件身份、截止日、输出要求及缺口；再进入独立研究会话草稿。
原问答文字、附件与档案交接仍在原草稿，新会话不继承另一档案的授权。新增交接默认来源为
`datahub`；只有明确选择已有研究资料并勾选必要范围，才能加入文件或网页，不自动扩权。明确发送后由原 `ResearchService.send` 重新检查能力、
模型工具、来源、快照和截止日，写入原幂等消息及质量合同。继续追问保留这份冻结合同。
已有来源、文件、结果与档案链接继续使用原会话功能；不会自动修改档案观点。

资讯的来源、关键词、分类、日期、来源重要性和自选关联只筛选当前已返回的有界资料集。
未知发布日期不进入日期筛选；按 Asia/Shanghai 自然日比较。重要性仅来自源字段，没有热度
字段时不制造热门排行；未提供资产关联的资料不会被推断为自选关联。
研究抽屉可选择新闻查询、新闻传导、调研前置，冻结完整选定资料包的身份和内容哈希。
当前采用整份资料选择，不支持任意客户端正文／URL或自报证据资格；原始归档不冒充链接网页全文。
既有 `selection → prepare → review → execute` 及未知不重发流程保持。

## API 与信任边界

- `GET /api/research/scenarios`：八场景及当前发布版本；package `available` 与
  `execution_admitted/status/missing` 分开，目录可准备不等于本次发送已获准。
- `POST /api/research/handoffs`：保留旧请求，新增 `scenario_id`、`scenario_inputs`、
  `observation_id`。输入严格采用 T1 的 subject/as_of/question/material_ids/window_start。
  没有来源会话仅允许无观察、无材料的新研究；有材料必须属于当前账号及指定观察。
- `GET /api/research/handoff-requests/{key}`：只查原回执，不创建或发送。请求全部字段绑定
  哈希，同键改参数 409。旧无完整请求哈希的回执拒绝猜测性重放。
- Discovery `Prepare` 新增可选场景字段；缺省字段排除 null，旧七字段请求哈希及旧
  v1/v2 context 字节不迁移。只有新场景上下文写 v3。

Host从实际 Store、观察、快照及当前目录构造资格。缺少数据种类、会计口径或历史 PIT
证明可以形成明确 `incomplete` 草稿；证券不符、已知晚于截止、外部账号、撤权、版本变化
和原件损坏属于硬拒绝。冻结上下文含身份、哈希、方法及有来源的观点／关系声明；完整原件沿原DataHub或已批准文件链冻结。
复用档案原件解析器检查原始字节和动态来源授权；发送以及新场景的数据行／下载／文件预览
再次校验原证据，撤权后不能借新复制快照下载。

场景交接在普通 `service.create` 之前保存 `creation_outcome_unknown` 意图；若创建回执
丢失，原生身份无法证明时保持未知，绝不再调用 create。浏览器按账号保存未确认的原请求，
刷新后只查询同键；暂时404也不旋转键。这里不宣称已实现未知原生会话的自动恢复。
Discovery继续复用它已有的同ID原生会话恢复机制。

## 验证与边界

后端测试使用真实 Store／Snapshots／Router／能力和质量合同，仅替换原生／模型／来源传输。
`test_scenario_handoffs.py` 覆盖八种方法要求、当前能力门、实际send与重放、Discovery执行、
来源撤权下载、跨会话观察、原件冻结和未知创建；原Discovery恢复／tracking用例保持。
Node测试执行控制器事件、来源筛选、草稿及不相容档案隔离、晚到响应、转义和刷新恢复。
浏览器脚本 `tests/e2e/research_web_scenarios_real_backend.mjs` 复用现有临时Host夹具，在
1440/390视口用真实表单、HTTP和草稿导航验证，不连接生产或外部网络。

这些测试不认证供应商可用性、真实模型质量、生产常驻部署或跨平台支持。完整变更集的
Router、独立评审、原通用CI和同候选macOS干净安装由控制任务统一执行；新增
`ui/scenarios.mjs`／`ui/scenarios.css` 必须进入其静态资源检查。


## 独立评审修复（2026-10-27）

场景及其legacy派生交接均保存祖先引用链，逐层重验权限、原件与副本；环、过深及未知祖先拒绝。
引用登记和永久清理使用原retention fence；源软删除仍可核验，仍被引用时在任何DSH删除前拒绝永久清理。
search_news使用原行的明确published_at核对截止，正文／发布时间资格分别判断；market_snapshot以
正式assets参数核对身份。明确比较角色另行冻结，不能把其他证券或支持资料当成主体。

仅场景的新研究质量合同使用schema2，execution_context严格绑定场景上下文hash与全部必需能力
id/version/compiled hash/native_name/resource_path。旧schema1构造和字节不变。
全部必需能力分别通过当前readiness、原生发现、实际资源快照；运行准入纳入
scenario_required_capabilities。scenario_discovered_capabilities记录发送前发现证明；
native_capabilities仍仅由真实loaded回调写入。质量核验重读Host冻结及实际资源，不信自报或重新计算的
JSON哈希；缺实际加载保持incomplete，资源／版本／合同变化为invalid。

原基金及其他非资产交接保留原数据属性和API路径；证券切换窗口不携带旧观察，搜索Enter不创建研究。
筛选无匹配、来源空与没有可核验资产关联分别展示；自选只用源实际返回的规范asset_codes。
资产研究工作区及严格资料格式见[资产研究资料](research-web-asset-research.md)。
