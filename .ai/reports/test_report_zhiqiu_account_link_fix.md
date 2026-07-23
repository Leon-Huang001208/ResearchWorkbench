# 测试报告:知丘账号配置链路断裂修复

**Task ID**: env-5-vast-ripple
**日期**: 2026-07-15
**状态**: 完成

## 问题描述

`.env` 里知丘账号只剩 2 个(huangyongjia、zhanzhengkai),但系统配置工作台应是 5 个。
排查发现是两个 bug 叠加:

1. `.env` 的 `ZQ_ACCOUNTS_JSON` 被覆写成 2 个(完整 5 个在 `.env_mac`)。
2. `AccountManager._load_config` 只读旧版 `ZQ_ACCOUNTS`,不认系统配置保存时写入的 `ZQ_ACCOUNTS_JSON` → 账号池为空 → 5 个账号连续失败 10 次被 `is_disabled` 永久禁用。

## 修复内容

| 文件 | 改动 |
|---|---|
| `data_layer/crawlers/zq/zhiqiu/account_manager.py` | `_load_config` 重构:优先解析 `ZQ_ACCOUNTS_JSON`,回退 `ZQ_ACCOUNTS`,兜底 `config.yaml`。新增 `_load_accounts_from_env` / `_parse_accounts_json`。与 `ConfigurationService._parse_zhiqiu_accounts` 优先级对齐。 |
| `.env` | `ZQ_ACCOUNTS_JSON` 恢复为完整 5 个账号 |
| `data_layer/crawlers/zq/.config_account_state.json` | 5 个账号 `is_disabled=false`、`consecutive_failures=0`,保留历史统计 |
| `tests/unit/test_connectors/test_zq_account_manager.py` | 新增 14 个测试(新建文件) |
| `docs/modules/data_layer_crawlers.md` | 新增 `account_manager.py` 小节,说明账号来源优先级 |
| `docs/CHANGELOG.md` | Fixed 段追加本次修复记录 |

## 运行的命令

```
ruff check data_layer/crawlers/zq/zhiqiu/account_manager.py tests/unit/test_connectors/test_zq_account_manager.py  → All checks passed!
black --check (同上)        → 2 files unchanged
isort --check-only (同上)   → 通过
mypy data_layer/crawlers/zq/zhiqiu/account_manager.py  → Success: no issues found
pytest tests/unit/test_connectors/test_zq_account_manager.py -v  → 14 passed
pytest (zq 三件套回归)      → 35 passed
python scripts/generate_py_file_index.py  → Generated
python scripts/check_doc_sync.py           → No changed files (非 git 仓库)
python scripts/check_task_completion.py    → No changed files (非 git 仓库)
端到端验证 (load_dotenv + AccountManager)  → loaded=5 available=5 VERIFY_OK
Playwright http://127.0.0.1:8765           → 工作台显示 5 个账号,截图 verify-zhiqiu-5-accounts-restored.png
```

## 测试结果

- **新增测试**: 14 passed (test_zq_account_manager.py)
- **回归测试**: 35 passed (含原 zq_connector 21 + zq_adapter + 新增 14)
- **lint/mypy**: 改动文件全部通过(既有债务未触碰)

## 文档同步结果

- `docs/modules/data_layer_crawlers.md`:新增 `account_manager.py` 小节
- `docs/CHANGELOG.md`:Fixed 段追加记录
- `docs/generated/py_file_index.md`:已重新生成

## 剩余风险

1. **需重启服务**:当前 API / knowledge_worker / crawl_scheduler 进程是修改前启动的,内存里持有旧的 `ZQ_ACCOUNTS_JSON`(2 个)和空账号池。工作台"读取"接口实时读盘显示 5 个,但运行中的 worker 仍用旧值。需重启这些服务才能让运行时完全生效。
2. **majingyi 账号**:历史 `success_count=0 / failure_count=61`,可能凭证本身有问题。解禁后会重新尝试,若仍连续失败将按正常机制再次被自动禁用 —— 属预期行为,非 bug。
3. **config.yaml 仍不存在**:`base_fetcher.py:210` 传入的 config_path 指向不存在的 yaml。修复后账号走环境变量,yaml 回退不再被触发,但该依赖未根治(计划步骤 4,本次未做)。
4. **`check_doc_sync` / `check_task_completion` 返回空**:本项目当前不在 git 版本控制下(`Is a git repository: false`),两个脚本基于 git diff 检测变更故无输出。实际检查项均已逐项手动运行通过。
