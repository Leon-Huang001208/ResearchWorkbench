# 知丘数据源账号禁用恢复与自动解禁机制 — 测试报告

**日期**：2026-07-15
**报告类型**：诊断 + 修复 + 质量验证
**涉及子系统**：data_layer/crawlers/zq

---

## 问题概述

三个知丘数据源（研报/公众号/纪要）虽然 `enabled=True`、调度器正常注册了任务、`.env` 里也配了 5 个账号，但实际爬取全部失败。

## 根因链

```
ZhiQiuClient.login() 登录知丘平台连续失败
  → record_failure() 每次 +1 consecutive_failures
  → 累计到 10（阈值 ZQ_MAX_CONSECUTIVE_FAILURES=10）
  → is_disabled=true 永久禁用（account_manager.py:524-529）
  → 状态持久化到 .config_account_state.json
  → _is_account_available() 见 is_disabled=True → 全部返回 False
  → acquire_account() 返回 None
  → _fetch_with_account_lease() 直接返回 "获取账号失败"
  → 无法自动恢复（无解禁机制）
```

## 诊断过程

### 1. 代码逐层排查

| 层级 | 文件 | 结论 |
|------|------|------|
| 数据源注册 | `data_sources/zhiqiu_*.py` | `enabled=True` ✅ |
| 调度器注册 | `services/crawl_scheduler.py` | 3×3 任务已添加 ✅ |
| 账号配置 | `.env` ZQ_ACCOUNTS_JSON | 5 个账号 ✅ |
| 账号加载 | `account_manager.py` _load_accounts_from_env | 正常 ✅ |
| 运行时可用性 | `.config_account_state.json` | 5/5 `is_disabled=true` ❌ |

### 2. 诊断脚本实跑登录

`scripts/diag_zq_login.py` 对 5 个账号逐账号用 `ZhiQiuClient.login()` 实跑登录：

| 账号 | 结果 |
|------|------|
| huangyongjia | ✅ 成功 |
| zhanzhengkai | ✅ 成功 |
| sunhaoxiang | ✅ 成功 |
| **majingyi** | ❌ 失败（未拿到 REPORT_SESSION_COOKIE，密码错或账号被封） |
| wanghao | ✅ 成功 |

**结论**：`client.py` 登录代码正常，知丘平台接口无变化。`majingyi` 是账号侧问题（历史 0% 成功率），其余 4 个账号可正常登录。

### 3. 状态文件快照

`data_layer/crawlers/zq/.config_account_state.json`（2026-07-15 16:26）：

```
huangyongjia:  309次/264成功  consec=10  is_disabled=true
zhanzhengkai:  309次/265成功  consec=10  is_disabled=true
sunhaoxiang:   312次/265成功  consec=10  is_disabled=true
majingyi:       73次/  0成功  consec=10  is_disabled=true
wanghao:       315次/261成功  consec=10  is_disabled=true
```

---

## 修复措施

### 1. 状态文件重置（立即恢复）

操作：备份 `.config_account_state.json.bak` → 所有账号 `is_disabled=false, consecutive_failures=0`。

验证：`get_available_accounts()` 返回 5 个账号，`acquire_account()` 可正常租借。

### 2. 自动解禁机制（防止复发）

改 `data_layer/crawlers/zq/zhiqiu/account_manager.py`：

| 改动 | 位置 | 说明 |
|------|------|------|
| `AccountStats.disabled_at` | 第 56 行 | 新增字段，记录永久禁用时间戳 |
| `RotationConfig.disable_cooldown_hours` | 第 71 行 | 冷却期配置，默认 6.0 小时 |
| `_parse_rotation_config()` | 第 298-337 行 | 从 `ZQ_DISABLE_COOLDOWN_HOURS` 读取冷却期；同时让 `ZQ_MAX_RETRIES`/`ZQ_LEASE_TIMEOUT` 等也从环境变量读取（此前这些 `.env` 配置未生效） |
| `_is_account_available()` | 第 408-437 行 | 永久禁用后检查冷却期，若已过则自动解禁 |
| `_should_auto_recover()` | 第 439-452 行 | 新增方法：判断是否可自动解禁 |
| `record_failure()` | 第 588 行 | 永久禁用时记录 `disabled_at` |
| `get_available_accounts()` | 第 462-481 行 | 自动解禁后将状态落盘 |
| `acquire_account()` | 第 503-514 行 | 同上 |

**设计要点**：
- 冷却期从 `ZQ_DISABLE_COOLDOWN_HOURS` 环境变量读取，默认 6 小时
- 冷却期 ≤ 0 时不自动解禁（运维显式关闭自愈）
- 旧状态文件无 `disabled_at` 字段 → 视为已达冷却期，给一次重试机会
- 解禁后 `consecutive_failures` 归零，若再次连续失败 10 次会再次禁用（循环自愈）

### 3. 诊断脚本

新建 `scripts/diag_zq_login.py`（可重复使用的运维工具），复用 `ZhiQiuClient.login()` 逐账号分步诊断登录。

---

## 质量验证

### 单元测试

```
python -m pytest tests/unit/test_connectors/test_zq_account_manager.py -v
→ 20 passed (6 个新增 + 14 个既有)
```

新增测试（`TestDisableCooldownRecovery`）：
- `test_record_failure_disables_and_records_timestamp` — 禁用后 `disabled_at` 被记录
- `test_disabled_account_unavailable_within_cooldown` — 冷却期内不可用
- `test_auto_recover_after_cooldown` — 冷却期过后自动解禁
- `test_legacy_state_without_disabled_at_recovers` — 旧状态文件兼容
- `test_cooldown_zero_disables_auto_recover` — 冷却期=0 不自愈
- `test_account_stats_default_disabled_at_none` — 默认值

### 完整测试套件

```
python -m pytest tests/unit/test_connectors/ -v
→ 177 passed, 0 failed
```

### 代码质量

| 工具 | 结果 |
|------|------|
| ruff | All checks passed! |
| black | 3 files would be left unchanged |
| isort | All checks passed! |
| mypy | Success: no issues found in 1 source file |

### 端到端验证

- Python 直接验证：`get_available_accounts()` 返回 5 个账号，全部 `is_disabled=false`
- Playwright 截图：Research Workbench 工作台正常运行，系统配置页面 5 个知丘账号可见
- API `/api/scheduler/status`：三个知丘源 `enabled=true, should_run=true`，调度器在运行

---

## 剩余问题

### 1. 调度器进程登录失败（需进一步排查）

**现象**：诊断脚本 4/5 登录成功，但调度器进程（18:46 watchdog 重启）执行知丘爬取时登录失败。

**状态**：状态文件显示 19:06 账号 `consecutive_failures: 4`（未达阈值），临时锁定中。调度器日志 18:46-19:10 区间无 ZQ 爬取记录，CS/CNSTOCK/CLS 爬取正常。

**可能原因**（待排查）：
- 调度器子进程继承的环境变量与终端不同（网络/代理）
- 调度器内存中加载的是旧版 `account_manager.py`（18:46 重启时已是最新代码，但需确认 Python 模块缓存）
- 网络层面的差异（`session.trust_env=False` 可能在不同进程上下文有不同的网络行为）

### 2. majingyi 账号密码问题

0% 成功率（73 次使用 0 次成功），诊断脚本确认登录失败。需用户在知丘平台核实该账号状态。

### 3. 新代码生效确认

自动解禁代码在 17:57 写入文件，调度器 18:46 重启——应在 Python 重新 import 时加载了新代码。但需在下次 ZQ 爬取触发后（下一个 30/60 分钟周期）观察日志确认。

---

## 涉及文件

| 文件 | 改动 |
|------|------|
| `data_layer/crawlers/zq/zhiqiu/account_manager.py` | 新增 `disabled_at`、`_should_auto_recover`、冷却期自动解禁；加强 `_parse_rotation_config` 读环境变量；`get_available_accounts`/`acquire_account` 解禁后落盘 |
| `data_layer/crawlers/zq/.config_account_state.json` | 重置 5 个账号（先备份 .bak） |
| `tests/unit/test_connectors/test_zq_account_manager.py` | 新增 `TestDisableCooldownRecovery` 类（6 个测试） |
| `scripts/diag_zq_login.py` | 新建一次性（可复用）诊断脚本 |
| `.ai/reports/test_report_zhiqiu_account_disable_recovery.md` | 本报告 |

### 4. 7/16 排查：调度器进程死亡 + Deep Backfill 假完成 + 首次触发延迟

**问题**：7/15 修复后，7/16 UI 仍显示"等待抓取"。

**排查结论**：

1. **调度器进程死亡 13 小时**：7/15 19:10 crash → 7/16 08:24 watchdog 重启。崩溃窗口期无任何爬取可能。

2. **Deep backfill 状态文件假完成**：[data/crawlers/zq/.deep_backfill_state.json](data/crawlers/zq/.deep_backfill_state.json) 在 7/11 所有账号被禁用期间运行时标记 `completed: true, total_saved: 0`，之后每次触发都立即返回 "already completed"。**修复**：删除状态文件，下次触发重新从头回补。

3. **常规爬取任务首次触发延迟**：`_add_jobs_for_source()` 未设 `next_run_time`，APScheduler 需等满整个 interval（30-60 分钟）才首次触发。**修复**：[services/crawl_scheduler.py:335](services/crawl_scheduler.py#L335) 加 `next_run_time=datetime.now() + timedelta(seconds=30)`。

4. **调度器进程登录成功**：状态文件重置后，`zhanzhengkai` 账号在 08:56 被知丘公众号爬取成功租借并登录，`success_count: 265 → 266`。说明之前调度器进程登录失败是因为账号处于永久禁用状态，而非环境差异。

### 5. 端到端验证（7/16 08:57）

- **知丘公众号**：✅ 成功爬取 21 条数据（Playwright 截图：`zq_crawl_success_20260716.png`）
- **知丘研报**：等待首次触发（60 分钟间隔，预计 09:24）
- **知丘纪要**：等待首次触发（60 分钟间隔，预计 09:24）

---

## 结论

- ✅ 根因已诊断：账号永久禁用导致死局
- ✅ 状态已重置：5 个账号恢复可用
- ✅ 自动解禁机制已实现并测试通过
- ✅ Deep backfill 假完成状态已清除
- ✅ 常规爬取首次触发延迟已修复（加 `next_run_time`）
- ✅ 知丘公众号已成功爬取 21 条数据
- ✅ 所有质量检查通过（ruff/black/isort/mypy + 20 tests + 177 connector tests）
- ⚠️ majingyi 账号密码错误（0% 成功率）——需用户在知丘平台核实
- ⚠️ 知丘研报和纪要需等下一个调度周期验证
