# 长期研究档案组合交付

任务为macOS Web功能开发，主任务ID research-dossiers-20261023-e2a3b9d1。Core、UI、MCP及扫描在四个已登记隔离worktree分别实现、验证、独评；最终由主任务统一交付。当前合入主线基线fafc2a60，8处文档冲突保留双方模块和既有部署说明；业务代码自动合并，没有覆盖主线SPDR或固定部署逻辑。

## 阶段与边界

1. 个人长期档案、五区、证据引用与pin、观点版本、成果质量／原件状态、Prompt-only跨会话继续研究、删除保护、备份恢复已实现。
2. 方法说明与确定性手动扫描已实现，仅读已有完整冻结材料；A股财报／公告为待研究，风险和催化观察分别标记。未实现的供应商字段与未知时点明确缺口，不推定方向或机会。
3. 小创18项固定清单、个人Keychain作用域、预算／unknown不重发和原件冻结已有离线合同与独评；真实Registry身份未核验，candidate导入保持unsupported，不能安装启用。54子弹仅估算，真实报价、凭据、收费比较未执行。
4. 复用Automation的冻结材料跟踪已实现且默认关闭；需当前规则、当天合格手动扫描和实际运行中的原调度能力。原私网子profile禁用Automation，当前拒绝开启，未放宽。当前不自动采集新数据，实际源／模型单次业务质量闭环与正式持续跟踪开放另验。

## 已观察验证

PR209 首轮 Checks 的 Python 步骤前300项通过后退出126：新增清单后的空行终止shell续行，后续测试路径被当成命令。删除该空行，保留完整原有清单；原失败run39954302629保留，修复后以新候选重跑，不手工rerun或缩减验收。

主线再前进至PR207／9b21783b后，在原受管integration工作树逐块解决实际冲突，保留Discovery、档案、两套启用边界及全部既有CI清单。Discovery未ready检查先于档案receipt绑定，并增加HTTP回归证明失败不消费、普通会话仍可使用原receipt。JS路由／controller采用并集，116项双方定点通过；新增HTTP回归通过。02／04图重新合成、showcase／四视口通过并实际看图，组合源码阅读绑定5bd320a3。未覆盖主线功能，也未伪造CI或改状态机。

末轮更新：Python候选8c0432767最终Approve，15个关键文件blob与各已审版本核对；JS最终af61a1389 Approve。补齐整个档案目录丢失的根级初始化标记与升级保全后，47项Core／扫描／保全通过。更新组合272 passed（67.47秒）、租户／DataHub／插件121 passed（34.60秒）、Node1081 passed／3原skip（26.58秒）。当前源码重新运行真实HTTP＋Chrome1440浅色／390深色均通过，回执含实际storage等12个文件SHA；积极asyncio网络拒绝回归证明底层连接调用0。仅NativeFixture四次Prompt，无真实模型／供应商访问。源码最终提交、CI和发布身份由正式交付回执绑定。

- 原Router Python：749 passed、1原skip，610.33秒。
- 档案／MCP／Automation组合：266 passed、1依赖弃用warning，41.33秒；后续信号分类26 passed、profile guard10 passed。
- Node Research Web：1075 passed、3原skip，6.54秒；后续UI目标210 passed。L4四组113 passed，9.55秒；新增Router策略组117 passed，4.86秒。
- 升级与渠道扩大回归首次1214 passed／30 failed，156.87秒。失败为测试子进程未继承源码路径及借用.venv-tests不满足旧fixture的.venv身份；未修改产品门。使用既有批准.venv与PYTHONPATH后，gateway完整140 passed，22.19秒；原失败日志保留。
- 真实ResearchService／HTTP／SQLite与Chrome1440浅色、390深色通过：创建、五区、来源与成果预览、缺口与空快照零信号、分类、准备锁、@零绑定、目标刷新后Prompt202绑定、第二会话接续及403缓存清理。只有NativeFixture四次Prompt，真实模型／供应商／外网零调用。fixture登录不认证生产网关。
- Python独评先BLOCK并修复Core3项、MCP2项及扫描3项；30841组合135 passed、Ruff／Black／mypy通过，5285小范围27 passed。JS独评原7项及刷新残留P2均有修复和回归，最终UI／新helper待同候选复审记录。
- 模块架构／源API库存零违例；02/04图各showcase9项、四视口包含性通过，并实际查看同哈希明暗截图。README、文件索引、安装静态资源与原Checks清单同步。

本报告为提交前检查点；最终候选的完整changed-set Router、CI实际checkout、独评确认、受管PR／合并／资源收尾在私有交付回执和后续记录绑定。没有执行常驻部署、正式数据库操作、真实供应商或模型调用；其他平台保持对应设备交接，不把源码、健康探针或fixture提升为业务研究质量。
