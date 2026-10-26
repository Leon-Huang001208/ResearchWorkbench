# 业务模块与导航重新划分

宿主：macOS；任务：Web 功能开发；交付任务：`business-navigation-20261021`。
按用户确认的方案撤掉“研究台”主导航，保留 FinGPT、Claw 与唯一 DSH 执行链。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"本轮重分组浏览器路由和页面投影，原Host/DataHub查询、不可变快照、显式交接、DSH会话、框架与ETF工程模拟请求链不变；没有新增服务、执行循环、HTTP接口或持久格式。02/03图继续描述这些模块及查询到交接的请求链，旧研究台称谓仅表示workbench.py技术模块，并非现有主导航。","diagrams":[]} -->

## 实现

- 一级顺序为 FinGPT、Claw、资产观察、研究情报、AI 资讯、研究框架、策略模拟、能力中心、运行与用量。
- 资产观察的行情与基本面使用原七区块；基金数据独立复用 `fund_data` 的基本资料、净值、分红、披露持仓，不声称股票区块已具备基金能力。
- 新闻、研报和公告查询移至研究情报的主题检索；行业查询不声称具备上下游关系图。ETF 模拟独立入口，原 BLOCKED、工程输入、账本、历史运行与缺口保留。
- 规范路由为 `#/assets`、`#/assets/funds`、`#/intel/search?kind=news|research|announcements`、`#/simulation/etf`。旧 workbench 路径及 section 查询参数映射到新入口，热点继续保留事件及视图参数。
- HTTP API、历史 section 和数据格式不变；撤掉跨会话文件网格，不增加资产与成果关联。材料、快照和产物继续从原会话查看。
- 页面加载、查询轮询、交接及ETF异步结果绑定发起导航的代际。离页不撤销已受理的服务器任务、不重发研究；迟到返回不改写当前结果、错误、上下文或草稿。查询交接从已选 manifest 恢复原始来源、参数、截止时间，资产交接保留观察上下文。
- 基金浏览器回归发现 `name="dataset"` 遮蔽 `form.dataset` 导致能力字段缺失，改为读取 `data-capability` 属性；先复现失败，再修复并补测试。

## 已执行验证

- `node --test --test-reporter=dot tests/javascript/research_web*.test.mjs`：最终代码 744 项通过；新增表单遮蔽回归前的首次完整运行为 743 项通过，两次日志均保留。
- `node --test --test-reporter=dot tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs`：112 项通过。
- 本机产品 Python 加当前 worktree 的 `PYTHONPATH`，只读复用已有开发工具，运行 `python -m pytest tests/research_web/test_workbench_operations.py tests/research_web/test_asset_workspace.py tests/research_web/test_etf_decision_routes.py tests/research_web/test_etf_decisions.py --confcutdir=tests/research_web -q`：25 passed，56.22 秒，1 项现有 Starlette 弃用警告。最初两个解释器缺少 pytest 的尝试保留为失败，未安装依赖。
- `node tests/e2e/research_web_business_navigation.mjs`：10 组通过，208 次本地夹具 API 请求，16 张明暗/宽窄截图；覆盖新旧路由、基金四类、主题三类、来源与manifest交接、迟到GET/POST/失败、切页返回、ETF迟到结果、会话资料/文件及键盘焦点。测试server首轮补齐JSON MIME与隐藏控件选择，随后完整运行通过。
- 浏览器仅使用临时localhost静态服务器、真实UI及确定性fake API；没有真实行情请求、模型调用或常驻服务操作。
- 文档治理、架构对应检查、完整 changed set 的 Project Constraints、Python文件索引检查均通过。架构检查发现的新文档标题锚点已修复后复验，无遗漏门项。
- 独立 JavaScript 评审未发现阻断问题，并另跑 workbench/intel 的29项回归通过；评审绑定五个产品Git blob，发布前复查候选内容。JS-only不运行TypeScript，工程无ESLint配置/二进制，不把它记为通过。

本机日志及浏览器回执归档于 Git common directory 的 `leon-engineering/local-evidence/business-navigation-20261021/`。后续完整Router、独立评审、集成候选及远端CI的实际状态由同task-id的受管交付回执与验证回执记录，不预报通过。

## 验收边界

公开安装器、依赖锁、固定DSH及启动配置未改；按用户要求取得同候选macOS Bootstrap，另保留Project Constraints与Research Web Checks通用仓库门。Windows/Linux产品原生验收为NOT_RUN，不作为Mac任务前置条件。常驻服务部署未授权，本任务不部署；不以浏览器夹具、安装健康或CI替代真实研究质量。
