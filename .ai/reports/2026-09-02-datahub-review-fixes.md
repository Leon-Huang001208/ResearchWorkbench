# DataHub Task 1 — review fixes

日期：2026-09-02。基线提交：`ab007ffdcc59b625e57c88593ad46fcdee7a5cf8`。
范围仅后端三项审查P2、回归测试与文档；未修改UI、父任务计划/来源/验收报告。

## 修复与根因

1. `main.upgrade` 已将快照复制为新ID，但draft只有原会话消息。现在保留原消息，在结尾追加origin_dataset_id→dataset_id、原/新manifest hash、原retrieved_at以及当前会话manifest/rows路径和各文件hash。明确旧路径不属于新会话，不替模型改历史、不自动发消息、不重新HTTP取数。复用detail的归属/hash校验和StoreError处理；新增结构化计数日志，不记录正文。
2. `snapshots.publish` 原先先发布私有UUID，进程在下一rename前退出会令目录枚举发现缺少公共文件的资料，阻塞健康目录及查询缓存枚举。现在先发布并fsync公共目录，私有UUID最后发布作为提交标记。中断留下的公共孤儿与私有.pending均不枚举、不自动删除；重启pending收据仍拒绝自动重试。既有文件校验和普通错误清理保持不变。
3. 分红字段曾无条件声明CNY，与含美元或未提供币种的来源原文矛盾。现在统一currency=null并加入verified_currency缺失；不猜币种，不改变每10份分红原文。

## RED / GREEN

以下`python`均为`python`；测试仅MockTransport，日志中的HTTP目的地不是实际网络访问。

- 升级RED：`python -m pytest tests/research_web/test_api.py::test_datahub_read_only_catalog_authenticated_queries_and_upgrade --confcutdir=tests/research_web -q`，1 failed，追加handoff为空而缺少origin_dataset_id。仅实现映射后同命令1 passed / 0.51s。
- 进程中断RED：`python -m pytest tests/research_web/test_datahub.py::test_crash_between_snapshot_renames_does_not_poison_catalog_or_retry_pending --confcutdir=tests/research_web -q`，1 failed / 0.24s，重建Hub后summaries在公共UUID缺失处抛StoreError。测试通过在第二次rename前抛BaseException模拟进程退出，不执行常规异常清理；重建对象使用同一磁盘资料和新HTTP客户端。
- 币种RED：`python -m pytest tests/research_web/test_datahub.py::test_distribution_currency_is_unverified_and_original_is_preserved tests/research_web/test_datahub.py::test_crash_between_snapshot_renames_does_not_poison_catalog_or_retry_pending --confcutdir=tests/research_web -q`，3 failed / 1 passed / 0.27s；美元、元、未知`---`三种原文均错误标CNY，发布顺序修复此时已GREEN。
- 最终定向GREEN：`python -m pytest tests/research_web/test_api.py::test_datahub_read_only_catalog_authenticated_queries_and_upgrade tests/research_web/test_datahub.py::test_distribution_currency_is_unverified_and_original_is_preserved tests/research_web/test_datahub.py::test_crash_between_snapshot_renames_does_not_poison_catalog_or_retry_pending --confcutdir=tests/research_web -q`，**5 passed / 0.44s**。
- 升级断言覆盖保留原正文、仅新会话路径、文件可读、原/新ID和hash/取数时间、旧owner不可读、provider调用计数不增加。
- 重启断言覆盖健康资料可读、孤儿不可读/不枚举、普通files不混入输入资料、pending调用不重发、新call正常查询、孤儿仍保留。

## 完整回归和静态检查（实际执行）

- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q`：**119 passed in 13.87s**。
- `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`：**32 passed / 0 skipped**。
- `python -m ruff check app/research_web tests/research_web`：passed。
- `python -m black app/research_web tests/research_web --check`：passed，30 files unchanged。
- `python -m isort app/research_web tests/research_web --check-only`：passed。
- `python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip`：passed，18 source files，默认未检查函数体提示仍明确存在。
- `python -m mypy app/research_web/datahub --follow-imports=skip --check-untyped-defs`：passed，6 source files。
- `python scripts/check_task_completion.py`：passed。
- `python scripts/check_doc_sync.py`：passed；app/research_web没有命中该脚本的来源前缀规则，相关文档已手工同步。
- `git diff --check`：passed。

## 边界和未验证项

不启动或重启任何服务；无新依赖、模型凭据、真实取数、3080、主工作区、DSH版本/模型/额度/沙箱变动。
本次仅离线回归，真实模型与资料UI验收由父任务继续；不声明Windows/Linux验证。
快照保持不可变：本修复不追溯重写旧币种元数据，也不自动迁移/删除旧版本异常发布遗留；未提交孤儿保持隔离供后续明确授权诊断。
采用项目bugfix-minimal流程，三项均先复现RED再最小修复；提交前以新的完整回归证据收口。
