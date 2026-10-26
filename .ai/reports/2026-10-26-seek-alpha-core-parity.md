# 小创核心研究能力融合实施记录

日期：2026-10-26。宿主：macOS Mac mini。任务：Web 功能开发。任务 ID：seek-parity-20261026-3af31de6。

## 目标与边界

按用户批准的[完整计划](../../docs/plans/2026-10-26-seek-alpha-core-parity.md)实现个股、资讯、问答、Skill／Tool、组合研究、深研／角色及资料跟踪的功能闭环。复用现有 Host／DataHub／受管 MCP／唯一 DSH／质量与报告链。音频转写和录音纪要排除。新依赖、真实研究模型、收费 MCP、秘密、常驻部署与他平台验收分别授权。

## 当前进度

2026-10-27续：首批最终源码评审批准`8f5288ca`，完整82文件Router为L4；同候选16项本地门全部通过，Node336项、Python709项及16子测试（保留1个既有skip和1条警告）、完整Project Constraints及文档／索引均通过，唯一子进程墙钟合计416.0864秒。14份本地门文件合计6606807字节已独立归档并逐文件Hash读回验证，不把后续候选当作本次运行SHA。

受管PR为[#243](https://github.com/Leon-Huang001208/ResearchWorkbench/pull/243)，尚未合并或部署。`8f5288ca`的Mac Bootstrap `40384650392`成功，Research Web Checks `40384650069`运行中；Project Constraints `40384650499`在ubuntu-26.04真实字节码回收测试失败。最小修复`3e6500e1`保留真实`py_compile`正例、未知／恶意字节拒绝与逐字节比较，统一可信预期编码上下文；21项Python及3项Node本地通过，Python3.14及新候选CI尚未认证，见[独立修复记录](2026-10-27-iteration-bytecode-compat.md)。当前最终候选仍待独评、重新绑定Router、本地门和原三CI；旧Mac成功不移用为新候选成功。

T3九组合包／其余Skill与Tool、T4深研与角色、T5资料与跟踪仍待实施，不能因首批PR或140行静态对照而关闭完整任务。真实模型、收费源、常驻登录态和Windows／Linux原生均未执行；不安装新依赖或启用计划。

| 项目 | 已观察结果 | 未验收边界 |
| --- | --- | --- |
| 原站冻结基线 | 62 个名称、78 个公开工具，共 140 项；原始文件摘要与逐项身份／工具定义核对一致 | 名称和工具说明不是供应商 schema、可调用性或研究质量证明 |
| 首批八场景合同 | T1 源码提交 `0c8ee56a3d44ea8f89242865abaf36193e2062ba`；独立 Python 评审 Spec Compliance／Task quality 均通过 | Host 的真实权限／来源／冻结／发送绑定由 T2 单独验收 |
| T1 本地测试 | 18 passed、16 subtests passed；Ruff／Black／isort 通过；原始 RED 和实际 GREEN 日志已保留 | 未执行浏览器、供应商、MCP、模型或安装 CI |
| 个股／资讯／问答联动 | T2 源码到`eec3c44c`；原评审两轮逐项复核闭合，无剩余Critical／Important | 全分支审查、完整Router和同候选CI／Mac安装／发布尚待完成，不宣称常驻上线 |
| 其余能力与组合包／深研／角色／资料跟踪 | 后续任务保留完整范围 | 不以 140 条目录记录作为功能实现 |

## 本机与资源

原共享仓库的 Git 引用及旧 worktree 元数据出现 `dataless` 标记，受管只读完整性检查在 `read()` 等待；保留原仓库、其他任务资源和全部业务数据。从 GitHub 建立本任务独立控制副本，完整 fsck 通过并经受管 Git 入口建立任务工作树，基线为 `d47cf3adeedf6e10f5e0b5d056b52259d4cd3b4b`。未迁移、替换或修复原 Git 元数据。

只读复用既有 Web Python 安装及既有缓存中的测试／格式工具，没有安装新依赖。相关基线：Node composer menu／Discovery 43 passed，资产页签／workbench 40 passed；Python workbench operations 8 passed、1 个既有 Starlette 弃用警告、10.77 秒。最初未使用 Web 既定 confcutdir 的命令在 legacy SQLAlchemy 导入失败；后续使用原 CI／Router 的 `--confcutdir=tests/research_web`，不修改或删除测试。

## 模块结构复核

本批源码和配置更改均在现有系统边界内；下列决定逐组对应架构映射，不能用功能声明代替真实执行或平台门。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"场景与资产资料属于原浏览器UI中的局部组件和事件接线，继续使用原主题、导航、同源API和唯一DSH，没有新前端服务或独立研究入口拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"新场景路由和冻结正文权限检查均由原账号Host承载，实际研究继续走原ResearchService与私有DSH连接，不增加服务、消息正文库或公共网络节点。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"资料仍冻结在当前账号原DataHub文件快照，新增祖先复验收紧既有行读取和导出，不改变Provider链、供应商字段映射、正式数据库或仓准入。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共享服务与质量合同新增场景绑定但不创建或启用计划；原Automation仍拥有调度和未知不重发，保存与启用及研究执行分离拓扑保持。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"上下文与结构化研究资料复用原会话文件及来源引用，schema2仅加强Host冻结身份，原备份恢复和保全锁继续管理，不新增事实或聊天数据库。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"场景及资产研究投影位于既有资产工作台到DataHub快照到DSH草稿边内，新增局部模块和引用角色未引入第二执行器或数据存储节点。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks步骤登记新增回归、原MacBootstrap步骤核对新资源，无新增workflow/job/runner/依赖或timeout，仓库验收到CI再到独立部署的流程保持。","diagrams":[]} -->
<!-- architecture-review {"group":"discovery","structure":"unchanged","reason":"可选场景v3继续沿原selection/prepare/review/execute和同一个Automation来源链，旧v1/v2保持，未增加采集器、后台队列或自动推理边。","diagrams":[]} -->
<!-- architecture-review {"group":"dossiers","structure":"unchanged","reason":"原档案解析器增加新交接祖先权限和保全检查，元数据仍属个人原Store与SQLite，归档修订仍由用户确认，不新增隐藏档案或事实库。","diagrams":[]} -->

## 权限与质量原则

- 静态映射中的 reuse 是实现候选；所有原始行保留 unverified，不能推导 callable、runtime_verified 或 quality_passed。
- T1 的资格表只能由 Host 读取当前账户的真实能力及证据后构造，不能接受客户端自报。
- 证据种类不齐可准备明确 incomplete 的研究草稿；对象、归属、权限、原件完整性或已知日期不符必须拒绝，不能以 incomplete 绕过。
- 现有禁用能力和方法比较门保留；草稿或文件生成不能替代当前版本的 Host 质量通过。
- 首次源码验证不代表部署、真实模型、真实收费源或 Windows／Linux 原生通过。后续完整 changed set 的 Router、评审、CI、macOS 干净安装及安全收尾分别补证。

## 首批实际范围与修复（续行2026-10-27）

资产、资讯与FinGPT／Claw已接入八场景选择、规范身份／截止、真实原件冻结、独立草稿、实际发送要求及原报告链。新增资产研究资料投影包含本人2–5观察并列、来源绑定摘要和待核验产业声明，使用已有材料／窄结构化导入；不等同原站私有知识库、专有评分或供应商算法。整份选材已实现，任意字符选段仍为后续待补项。原禁用和比较证据方法保持，不能把八个目录项说成八项均已生产运行。

独立评审实际发现并修复：多跳／旧式交接撤权、祖先保全、已知新闻／财务日期越界、复数资产主体误配、全部必需原生能力绑定、旧基金／主题交接截获、证券切换窗口、搜索Enter意外创建、来源／筛选／关联空态、缺少资产工作区、合法别名、快照更新失效以及摘要冒用来源质量。独立复核结论均绑定本轮修复SHA，不替代全分支或CI验收。

本机最终相关闭包：225项Python通过（旧Starlette warning1条，124.44秒），第二轮受影响闭包54项通过（75.71秒）、373项Node通过、4条临时Host＋真实Chrome组合旅程通过。浏览器验证真实导入／再次选择／比较／产业关系／继续研究／旧入口／别名／零创建，关系数据为明确标记的合成验收样本。实体手机键盘、真实模型／供应商、常驻登录页未执行。

MyPy不是通过：初始13条导入文件错误已在干净基线`d47cf3ad`逐条复现一致，无新增；相关日志保留，不添加ignore或回退旧检查。根控制记录及完整测试日志在本任务证据归档保存。通用架构／文档／额度／跨平台仓库契约113项通过，文档治理零违规、Python索引及差异空白通过；这些是当前工作改动的本地结果，尚不构成最终commit或安装CI回执。

原对交接按钮“未绑定”的早期判断不准确；独立评审定位到已有较后处理分支，新代码曾截获它。现已保留原基金／主题路径并增加真实点击回归；该判断的更正和修复历史完整保留。

整分支最终评审又实际复现两项Important：详情／回执／重放会返回撤权摘录，及确定未创建的比较材料拒绝会锁住编辑。修复在受管集成分支提交`22d00320`，未变更旧持久化证据；返回安全无正文状态、创建锁内的`not_created`证明与真正未知分开。4项真实Host反例、14项JS目标、123项Python／375项Node／4条真实隔离浏览器旅程通过，完整stdout/stderr在集成工作树`logs/t2-final-*`。当前仍待该修复的独立定点复核、完整候选本机闭包、CI和Mac安装，不宣称已发布或上线。

后续完整源码／登记评审已批准`c6357d6c`；其集成本机Python闭包709 passed、1个原skip、1条原警告、16 subtests，405.46秒。强制Node门发现既有受控DOM未提供新组件访问的shell，以及相对Python测试假设本地存在`.venv`；测试fixture-only修复`db6d7910`由独立TS评审批准，目标37／相邻19通过，未改产品、安装环境、删断言或skip。原Project Constraints还发现未补全部模块文档／README／结构决定；本报告九组复核、关联文档及README回执按原规则补齐，预检查零违规，未删减门或修改约束。上述失败日志和修复历史均保留，最终候选完整门与CI仍待实际执行。
