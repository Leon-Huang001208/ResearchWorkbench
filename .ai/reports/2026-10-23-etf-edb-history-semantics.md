# 华安周报 EDB 历史观测日期与负结算修复

宿主 macOS；任务类型为 Web 功能缺陷修复，本机只执行离线合成验收。
基线 `7f8fbf58909007bfa23fc1ac409f17aa11d36518` 已包含上游
`c4e953c4386c615cde89ad2d014d60c6e2959303`。本子任务不提交、push、合并或部署。

## 问题与边界

主任务的真实原生 EDB/TDAYS 对照记录在任务私有
`logs/etf-excel/edb-calendar-coverage-preflight.json`，本子任务只读核对该文件 SHA256：
`ae83f033942927c30c69920edf77c0f3118881a54648e0430d39c5f585e25946`。
该取证指出：伦敦金缺2017-01-30且另有原生非市场日点；原油 EDB 有额外观测日期，WTI
2020-04-20 原生结算为负值。把所有 EDB 观测日强制当成市场交易日、所有价格强制为正数，
会误拒这些历史事实。上述真实源文件由主任务保全，本子任务不调用供应商重新取证。

修复仅包含两条固定映射域规则，由 Provider 与 Host 共用：

- `kind=edb` 历史可以保留不晚于最后 `completed_dates` 日期的原生非市场日点。
- 仅 `S0031525/ICE`、`M0000005/NYMEX` 且字段为 `continuous_settlement` 的 EDB
  历史允许有限负结算。黄金、市场指数及普通原油行情不取得负值资格。

不修改原始导出、哈希、来源、字段、日历或已完成交易日；额外观测不增加行情交易日或成交天数。
未结束／未来非空观测、NaN、无穷、布尔值仍拒绝。零／空值不作为有效价格；Host 不让全零行
变为空字典后崩溃，也不让零值隐藏同日数值冲突。Provider 与 Host 分别记录
`native_non_session_count`、`negative_settlement_count` 汇总。

`assess_weekly_snapshot` 的必需市场历史点检查代码保持原样。伦敦金2017-01-30缺口在合成
回归中仍明确返回 `history_gold_london:weekly_history_incomplete`；额外日和零值不能填补。
不自动补查、换品种或校准伦敦金时钟。定时继续关闭，真实周报数据、模型、正式稿与部署状态
由主任务另行取证，本次离线通过不认证它们。

## 实际验证

日志均保存在主任务私有 `logs/etf-excel/history-semantics-*`：

| 验证 | 实际结果 | 日志 |
| --- | --- | --- |
| 首轮先失败 | 18 failed / 50 passed | `history-semantics-red.log` |
| 首轮定点修后 | 68 passed | `history-semantics-green.log` |
| 全零／零值冲突先失败 | 3 failed | `history-semantics-zero-red.log` |
| 最终完整 weekly/API 八文件 | 250 passed，67.50s | `history-semantics-weekly-api-final.log` |
| Ruff、Black、isort 四个修改文件 | PASS | `history-semantics-static.log` |
| Mypy 两个源码文件，含 `--check-untyped-defs` | PASS | `history-semantics-mypy-bodies.log` |
| `git diff --check` | PASS | 主任务工具回执 |

实际测试使用既有项目运行时与任务已有依赖覆盖，无安装新依赖：

```bash
PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages \
  /Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest --confcutdir=tests/research_web \
  tests/research_web/test_report_weekly_data.py tests/research_web/test_report_weekly_quality.py \
  tests/research_web/test_report_weekly_owner.py tests/research_web/test_report_weekly_evidence.py \
  tests/research_web/test_report_weekly_rendering.py tests/research_web/test_report_weekly_acceptance.py \
  tests/research_web/test_datahub_wind_excel_weekly.py tests/research_web/test_datahub_wind_api.py -q
```

本次未执行真实 Office/Wind、模型或网络操作；没有修改 API collector、依赖、安装器、CI、
Native profile 或固定版本。Router／完整性与合并资格、远端 CI 和后续真实数据复验由主任务统一记录。
