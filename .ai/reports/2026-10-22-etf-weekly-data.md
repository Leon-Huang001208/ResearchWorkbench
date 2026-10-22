# 华安 ETF 周报数据实施记录

宿主：macOS；任务：功能开发；基线：`9b436613aad9136f4959c992c89dd72fc7354ed5`。
实施 worktree：`/Users/leon/.codex/worktrees/etf-weekly-data/ResearchWorkbench`。

已实现冻结实际旧底稿的 57 序列映射及名称、周五 15:30 合同、逐交易日新鲜度和 96 位
Decimal 独立复算、Client API 惰性封闭适配、真实 Future 容量、私有 DataHub 取数与
快照/幂等/交接、同源校准材料与配置绑定的等价证据，以及 Run 副本 Office 投影。
模板、图表缓存、海外表和经济日历都由同一实际快照投影，不修改旧 AlphaFoundry。

实际检查：新增数据与 API 测试、既有 `test_datahub_broker.py`、
`test_datahub_wind.py` 合计 **94 passed，8.70 秒**。
日志：`logs/etf-weekly-data/pytest.log`。九个变更 Python 文件的 Ruff 通过；
新增文件 Black/isort 已格式化。首轮测试先因实现文件缺失失败，后有图表单单元格
引用解析失败，修复同时支持绝对与相对引用后通过；失败未当作通过。

所有供应商调用均使用注入的合成 SDK，没有真实取数、登录、Office 刷新或模型调用。
本机 WindPy 及账号权限、跨市场日历/收盘定义、经济日历精确查询、真实口径对照、
三周无人值守与浏览器/Word 视觉验收均未执行。源码实现不等于生产定稿就绪，缺失
合同或数据时明确 `blocked_data`。主管理员权限、规范正文、内容质量和定稿由主任务
接入并按最终候选独立验收；本记录不认证 CI、部署或其他平台。

后续独立评审发现首次校准的局部 manifest 遮蔽和等价证明缺少实现身份。已消除
Workflow/Dataset manifest 名称冲突，将适配器版本与三项实现源码 SHA 绑定到证明，
并实际打通 API/Excel 分组采用、首次准备回调与后续纯 API 复用。默认无外部比较引用
的正向回归读取真实生成的 XLSX 与刷新清单，不 mock“比较通过”；另覆盖不等价长期
序列保留当前 Excel 原始行、配置/代码语义变化使证明失效。

最终本子任务回归 **99 passed，20.18 秒**（两新增模块及既有 Wind/Broker），日志
`logs/etf-weekly-data/pytest-final.log`。四个新源码模块的 mypy
`--follow-imports=silent --check-untyped-defs` 已通过，未添加 ignore 或压低门禁；
九项 Python 文件 Ruff 通过。原 AlphaFoundry 三个实际 XLSX 的临时副本以合成输入
完成投影，曾发现 Wind 名称公式 `t=str` 缓存及 Decimal 历史值写成文本，均补回归
修复；这项兼容性验证不证明真实行情、Office 或业务质量已通过。
