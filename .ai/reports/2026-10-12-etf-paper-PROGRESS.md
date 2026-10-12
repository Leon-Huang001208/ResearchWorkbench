# ETF 首期工程模拟 PROGRESS

宿主：macOS / 24GB Mac mini。任务：功能开发。基线：`8a2d4ba75`（origin/master）。
隔离分支：`codex/etf-paper-loop`。仅本任务本机证据；其他平台NOT_RUN。
状态：独立工程实现进行中；真实闭环、完整门禁、浏览器、Docker与macOS安装CI未完成。
最新状态见文末本轮收口：浏览器与本地门已补验，真实准入和外部安装/CI仍未完成。
主工作区未提交报告与日常实例保留；未发布、合并、升级实例、安装依赖或执行真实交易。

## 能力/缺口矩阵

| 必要能力 | 已实现 | 当前可调用证据 | 缺证据/实现 |
| --- | --- | --- | --- |
| Research Web/DSH | 现役Host、唯一DSH、既有Automation | 本任务未运行真实DSH | 安装/浏览器/平台CI待验 |
| DataHub行情/基金 | catalog及Provider存在 | 本任务未调用必要真实数据 | ETF原价/总回报/公司行动/PIT等价闭包缺失；NAV不替代成交价 |
| 历史证券资格/交易规则 | 工程输入有显式合同 | 无生产认证 | 已准入逐日适配缺失 |
| receipt-gated计算 | 既有18项门继续保留 | 本任务未认证当前实例版本 | 真实Wind/Excel比较回执缺失；不启用、不复制绕门 |
| ETF信号/约束/模拟账本 | 新独立确定性领域实现 | 工程数据聚焦测试通过 | 真实准入BLOCKED；API仅接受engineering_only |
| 回放/恢复/复盘/UI | 同一step及checkpoint、事务保存、结果页 | Python/JS聚焦证据 | 实际页面、全门禁、真实固定样本/样本外研究待完成 |

## 源码与证据

| 源变更 | 测试 | 权威文档 | 实际结果 |
| --- | --- | --- | --- |
| portfolio_decisions models/engine/store | test_etf_decisions.py | 03-data-files.md | unittest 7项通过，0.451秒首次GREEN |
| portfolio_decisions routes/main接线 | test_etf_decision_routes.py | 04-api.md、05-security-validation.md | 本地真实HTTP/SQLite边界1项通过，0.063秒 |
| etf-paper/UI接线 | research_web_etf_paper.test.mjs、research_web_workbench.test.mjs | research-web-ui.md | 新2项及现有10项通过 |
| 架构API/源码清单、生成索引 | 项目强制门待核对 | ARCHITECTURE/DEVELOPMENT_MAP及现役模块文档 | 生成索引已生成，未认证全门禁 |

实际命令：

```text
git fetch origin master
python -m pytest tests/research_web/test_etf_decisions.py --confcutdir=tests/research_web -q
  FAIL/环境：现有.venv没有pytest；这不是行为RED，不伪造TDD证据。
python -m unittest tests.research_web.test_etf_decisions -v
  PASS 7项
python -m unittest tests.research_web.test_etf_decision_routes -v
  PASS 1项
python -m unittest tests.research_web.test_etf_decisions tests.research_web.test_etf_decision_routes -q
  PASS 8项（存储权限/摘要及人工事件校验调整后复验），0.483秒
node --test tests/javascript/research_web_workbench.test.mjs
  PASS 10项
node --test tests/javascript/research_web_etf_paper.test.mjs
  PASS 2项
python scripts/generate_py_file_index.py
  generated
```

Python聚焦使用既有主checkout `.venv/bin/python`（macOS Python3.12），没有安装包。
stdlib unittest与pytest兼容；不把它替代planner选中的pytest/API完整门。
Docker独立开发池被g2a占满3GiB，未停止或借用该任务；安装已声明开发工具需用户同意。
源码前尚无行为RED；首次pytest收集因环境失败，报告保留这一缺口。

## A-I 验收状态

| 项目 | 工程证据 | 状态/限制 |
| --- | --- | --- |
| A时间因果 | 未来价格/延迟known_at的信号对照 | 聚焦PASS；真实PIT、公告/形态不是本策略输入 |
| B最终约束 | 两只各15%保留70%现金 | 聚焦PASS |
| C资金持仓守恒 | 参与率部分成交、费用及批次守恒 | 聚焦PASS；公司行动等扩展待补 |
| D T+1 | 旧10份可卖，新10份不卖 | 聚焦PASS |
| E不可成交 | 停牌、无价、限价触及 | 聚焦PASS |
| F数据/准入 | 错口径单位/延迟数据、伪verified_real拒绝 | 聚焦PASS；没有伪造真实认证 |
| G回放/模拟 | 同一冻结片段step结果相等 | 聚焦PASS；生产前向数据adapter未交付 |
| H幂等 | 重复键/相同输入/数据库重开/checkpoint | 聚焦PASS；故障注入覆盖待扩充 |
| I真实闭环 | 未执行必要数据/计算真实调用 | BLOCKED |

## 研究和交付限制

示例输入与结果保存在任务证据目录，明确synthetic-fixture/engineering_only。
它们只证明工程路径可重算，不替代真实能力或市场收益；尚无真实固定样本、样本外或参数增量研究。
实际数据单位、逐日规则版本、来源授权、当前准入/receipt需独立补齐才能开放真实执行。
本任务不扩大framework Bot权限、不新增调度器/数据注册中心/凭据中心，也不接真实券商。
完整本机门、浏览器、Docker、macOS安装CI、其他平台及实际实例升级保留NOT_RUN/BLOCKED。

<!-- architecture-review {"group":"ui","structure":"unchanged","diagrams":[],"reason":"研究台增加ETF工程结果渲染与显式提交表单，仍在既有原生UI和同源Host边界内，没有新部署节点或执行循环。"} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","diagrams":[],"reason":"现有Host挂载有界确定性模拟路由，DSH与运行时拓扑不变，API清单已新增四项声明；真实链路阻断不提升研究工具权限。"} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","diagrams":[],"reason":"策略与事务账本作为Host内部领域计算使用现有产品数据根，未产生第二执行器、服务或全局数据库，现有系统级图的Host和产品数据边界保留。"} -->

## 本轮本地收口（后续结果替代前述待验状态）

用户明确授权本任务独立临时环境安装已声明开发工具。
临时目录 `/tmp/rwb-etf-validation-41b0c01d`，未写产品锁或现有.venv。
实装版本：pytest9.1.1、pytest-asyncio1.4.0、pytest-cov7.1.0、Ruff0.17.0、Black26.10.1、
isort9.0.2、mypy2.4.0。格式检查限定changed Python set；未宣称全仓历史债务消失。

只读review发现并以实际RED→GREEN修复4项：开盘引用未来close、扣费后其他持仓超限、恢复跳日、
公司行动晚到仍认证完整账本。前3项3 failed →13 passed；第4项1 failed →14 passed。
存量UI门还发现new change分支假设matches总存在，1 failed →71 passed；未改测试豁免。
各原始回执：`logs/etf-paper-loop/review-red.log`、`review-green.log`、`corporate-red.log`、
`corporate-green.log`、`ui-regression.log`、`ui-regression-green.log`。

最终聚焦pytest14项通过（0.80秒），已有API回归53项通过（193.28秒），
UI回归71项、ETF/研究台12项、L4相关JS合同110项通过；没有skip/todo。
API初次52 pass/1 fail是临时解释器未携带产品文档依赖：原sandbox -I/-S不继承PYTHONPATH，
已用现有产品Python加载临时pytest工具复核单项1pass及全套53pass，未改Office代码或放宽sandbox。
Ruff、Black、isort及新模块mypy通过；mypy实际参数`--follow-imports=silent`，不是全仓mypy。
记录的Starlette弃用warning和mypy unused overrides提示保留，不作为产品故障隐藏。

浏览器：隔离127.0.0.1:18743实例，真实main/UI/API/SQLite，DSH用NativeFixture、凭据用隔离
内存fixture，不读取系统用户密钥。首次首选浏览器因classic-level ABI137连接失败，备选CUA完成
上传engineering-input.json →执行→保存→刷新→选择运行恢复；真实BLOCKED仍显示。
示例净值9997.02、现金7017.02、费用2.98、两标的各1490份/目标15%、各剩10份过期。
截图为`logs/etf-paper-loop/ui-screenshot.png`。既有framework启动collector在测试根采集公开
宏观资料，不是ETF必要数据/能力证据；不得以它认证I项。未验证真实DSH、供应商、手机视口或平台CI。

剩余：I真实数据/计算认证BLOCKED；Docker独立池仍未使用；macOS干净安装CI及通用远端CI NOT_RUN。
新模块不需要增加产品依赖；无变化安装合同的CI兼容证据仍缺失。
目标仍未认证为全部完成，未提交/推送/PR/合并/实例升级；需独立发布授权及数据准入补齐。

最终机械回执：`verification-plan.json`覆盖完整changed set并保留validation_failure升级记录；
`verification-receipt.json`由正式validator确认`valid=true/result=BLOCKED/mergeReady=false`。
所选6个本地门全部PASS、2个远端门NOT_RUN；不是本平台总验收PASS。
独立审查最后限定复核无新增发现，并单独用既有Python运行13项领域unittest通过。
输入、checkpoint与运行结果新增源码实现摘要；仅用于重现/跨实现隔离，不授予能力认证。
报告中源与回执都是本worktree未提交字节；GitHub macOS安装CI没有认证它们。
GitHub当前visibility已只读核对为PUBLIC，未执行任何远端写操作。
临时浏览器服务器已按唯一listener与任务script身份核验后停止，预览截图保留。
