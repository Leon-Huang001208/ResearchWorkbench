# Market collector resident 空闲证明修复

- 宿主：macOS；任务类型：Web 功能缺陷修复；基线：`19e9890f2`。
- 隔离目录：既有 `etf-weekly-data` worktree；未更改常驻服务、依赖、供应商配置或其他任务目录。
- 根因：无会话市场采集由 `MarketService._collectors` 持有，原 resident 仅检查研究会话、资产历史、报告和 DataHub 任务，采集期间可能返回 `active=false`。请求取消状态先写入，不能证明底层 Provider 已排空；原 `close` 还会重复取消正在清理的 collector。

## 改动

- 增加同步、有界的 `MarketService.activity_witness()`：最多核对 16 个 collector，实际任务所有权、取消排空和 Provider 关闭期间均活动；畸形状态或关闭失败保持未知。
- 关闭计数覆盖 Provider 关闭阶段；不再次取消已经在排空的任务。失败记录安全日志，不再记作关闭成功；未知状态不会自动恢复为空闲。
- resident 严格要求活动见证的 `active` 是真正的布尔值。缺失、无效或未知沿原拒绝判空闲分支处理，保持其他活动保护。
- 刷新任务字典添加明确 `dict` 注解，修复原有 mypy 将异构值推断为 `Collection[str]` 的错误；不改变执行行为。
- 同步现有系统职责文档，保留部署授权边界。

## 实际验证

测试解释器为已获授权的本任务 `.venv/bin/python`，`PYTHONPATH` 指向当前 worktree 与既有运行库；无新依赖。

```text
python -m pytest -q --confcutdir=tests/research_web \
  tests/research_web/test_market_service.py tests/research_web/test_api.py \
  -k 'activity_witness or already_draining or resident_includes_market or sees_real_sessionless'
```

- 编辑实现前 RED：9 failed、1 passed、231 deselected，10.06s。实际包括无会话市场采集时 resident 误报空闲。
- 修复后同命令 GREEN：10 passed、231 deselected，10.77s。
- 完整两模块验证：240 passed、1 failed，359.06s。唯一失败为原有 `test_document_business_api_generates_download_and_reads_owned_word`，测试依赖环境作 `sys.executable` 时，真实沙箱不会继承宿主 `PYTHONPATH`，因该环境未装运行库而返回 `document_execution_failed`；未将原 full 标为全绿。
- 同一 Word 原例改用既有运行环境 `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python` 作解释器，当前 worktree 与任务测试依赖目录作 `PYTHONPATH`，复跑 1 passed，3.36s。只读沙箱诊断实际 stderr 证实测试环境 `ModuleNotFoundError: No module named 'docx'`，原运行环境同一 `import docx` 完成且 stderr 为空；未修改沙箱、依赖或测试门。
- 最终源码在正确运行环境重跑上述 10 项新增回归：10 passed、231 deselected，10.19s；日志 `logs/market-idle-fix/green-runtime-env.log`。
- 对 4 个变更 Python 文件执行 Ruff、Black check、isort check：通过。
- 对 `market_service.py`、`main.py` 执行 `mypy --follow-imports=silent --check-untyped-defs`：2 个源文件通过。先用 HEAD shadow 复核原有类型错误后才加注解，未使用 ignore。
- 离线日志：`logs/market-idle-fix/{red,green-targeted,full,mypy,mypy-baseline,document-isolated,document-runtime-env,sandbox-dependency-diagnostic}.log`。
- 完整两模块日志 SHA256：`fdb69470708af52c7026b430b329ca83cd0414b3436a483fe216495418137c5f`；正确运行环境 Word 原例日志：`f1db8f4480fa500c19c6d0a814aeca87bc50131aa31ad90a3ad25399f81e0b3c`；沙箱依赖诊断日志：`b7147d73c63f4614644e72f64963257270e2129b242346fb1bfb453e80c5ad20`。

## 边界

新增测试使用实际 MarketService 与阻塞、取消清理、关闭等待和关闭失败的 FakeProvider，并覆盖真实 HTTP resident 接线。未调用外部供应商、模型或 Office；未部署、重启或停止任何常驻进程。本次回归不能替代完整周报供应商验收、内容盲评或三个真实周周期观察。
