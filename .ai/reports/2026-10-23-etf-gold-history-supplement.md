# 华安周报伦敦金单点历史补查

宿主 macOS；任务类型为隔离 worktree 内的 Web 功能修复。本子任务不执行 Git 写入、
Office/Wind 实时调用、模型、部署或日程启用。资源包由主任务维护，本子任务只读核验。

## 固定范围与实现

2026-10-23 试点的 schema4 来源合同严格继承 schema3，只增加
`history_supplement:{path,sha256}`。补查只接受原 EDB `S0270980` 的
2017-01-30 唯一空格，从同一 Wind Excel 的 `SPTAUUSDOZ.IDC/close` 十段 WSD、
IDC 十段 TDAYS 和同公式单点重查独立复算。2534 个重叠价格按 Decimal 精确相等；
原 XLSX 和两个原生非交易日观测保留，补查值与来源哈希单列 lineage。
第二处必需交易日空／零、原价格改变、公式、日期、单位、资源或快照 lineage 改变均拒绝。
代码与资源固定2026-10-23报告期、2026-10-22历史覆盖截止；下一周须重新审源和实采，
不能借本次 proof 认证未来周或宣称已稳定生产三周。
Host 在有 Run 上下文时重新读取同版本来源合同与原始资源；无上下文的补查快照阻断。
原历史完整性门、schema1–3/API 旧语义及定时禁用不变。

接手前已有 4 个旧 schema2 Provider 回归因新增 Host 完整来源合同重读而误拒；
修复为只对 schema4 执行完整资源重放。真实原生 EDB 带独立末尾
“数据来源：Wind”尾注，Helper 与 Provider 读取时只排除该固定尾注。
其他非日期行仍拒绝。
规格复审发现公式 XML 扫描原先位于工作簿解压预算检查之前；现先执行既有
`_workbook` 的成员数、累计解压大小及行列上限，再读取 worksheet XML 查公式。
65 MiB 高度压缩的 worksheet 先失败测试捕获了过早扫描；修后在扫描前以
`weekly_excel_export_size_limit` 拒绝。合法预算内的公式仍被拒绝。
质量复审发现 Helper 先丢弃晚于最后已收盘日的原 EDB 行，可能绕过旧 Provider 的
`weekly_excel_unclosed_observation` 硬门。现与旧 `_series` 对齐：只读
`history_start..period_end`，先拒重复日期、再拒布尔值；本报告期内未收盘日的
非空值拒绝，`None`／空串／数值零跳过，报告期之后仍按旧筛选忽略。
完成日期的四种空／零与非空重复组合均拒绝，原 EDB 非交易日保留。

## 实际证据

所有日志位于主任务私有 `logs/etf-excel/gold-supplement-finish-*`：

| 检查 | 实际结果 | 日志 |
| --- | --- | --- |
| 首轮四个旧 schema2 回归 | 4 failed / 201 passed | `pytest-initial.log` |
| schema4 必须继承 schema3 India 日历，先失败 | 1 failed / 1 passed | `schema4-red.log` |
| 原生尾注先失败、修后通过 | 1 failed；随后 1 passed | `footer-red.log`、`footer-green.log` |
| Provider 原生尾注先失败、修后通过 | 1 failed；随后 1 passed | `provider-footer-red.log`、`provider-footer-green.log` |
| 解压预算先于公式扫描，先失败、修后通过 | 1 failed；随后 1 passed | `budget-red.log`、`budget-green.log` |
| 未收盘非空原值，先失败、修后通过 | 1 failed；随后 1 passed | `unclosed-red.log`、`unclosed-green.log` |
| 同日两条空／零未来记录，先失败、修后通过 | 1 failed；随后 1 passed | `unclosed-duplicate-red.log`、`unclosed-duplicate-green.log` |
| Gold 定点边界回归 | 33 passed | `unclosed-gold-final.log` |
| weekly/API 九文件最终回归 | 284 passed / 92.86s | `unclosed-weekly-api.log` |
| Ruff、Black、isort 九个改动 Python 文件 | PASS | `unclosed-ruff-final.log`、`unclosed-black-final.log`、`unclosed-isort-final.log` |
| Mypy 三个关键源码文件（`--check-untyped-defs`） | PASS | `unclosed-mypy-final.log` |
| `git diff --check` | PASS | 本任务工具回执 |

使用现有主环境 Python 和任务已有 site-packages，无新依赖安装。
九文件回归实际命令为 `python -m pytest --confcutdir=tests/research_web -q`
加八个原 weekly/API 测试文件与新增 `test_report_weekly_gold_supplement.py`；
所需 `PYTHONPATH` 包含本 worktree 和既有任务 site-packages。新增测试已由主任务
登记到原 Research Web Checks 的同一 Python 步骤，没有新增 job、runner 或依赖。

原 `source-package-20261023-v2` 的 `verification.status=pending`，完整
`load_run_source_contract` 按门拒绝；仅单点 helper 离线回放通过。主任务准备的
`source-package-20261023-v3` 已审资源允许完整来源合同读取及单点 helper 回放：
来源合同 SHA256 `4c898cf051c2935986e4d9ddfaec5a8f8ce88271b3444b8019fb6aa628bfee8c`，
补查 SHA256 `5459176bfb014eff05654999d04891bedc92e9a9026dd5c95619e27ca68d87ef`，
输出 2537 行、2534 重叠点、单点 `1191.27`，原 EDB 字节未修改。
两次审查修复后对 v3 重跑仍得相同2534个重叠点、1191.27和2537行。
日志见 `v2-replay.log`、`v2-helper.log`、`v3-replay.log`、
`budget-v3-replay.log`、`unclosed-v3-replay.log`。
这只是资源级离线核验，
尚无正式 Run、完整 57 组真实采集、报告质量、macOS 干净安装 CI 或常驻验收。
完整 changed-set Router、CI、独立评审与最终交付由主任务统一绑定。
