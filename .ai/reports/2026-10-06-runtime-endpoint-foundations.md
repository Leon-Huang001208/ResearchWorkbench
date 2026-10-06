# Task 1 私有端点与控制 origin 基础

宿主 macOS；任务类型：功能开发，隔离 worktree 本地基础合同验收。
基线 `9dee59fa9daedc1cedb4e5c99ccf75e3211cce6f`，分支
`codex/macos-runtime-port-allocation-20261006`。没有接入启动器、启动真实服务、读取用户控制配置、
迁移数据、安装依赖或操作远端。Windows/Linux、真实 Native/Docker 生命周期及 CI 均未验证。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新增尚未接入公开启动链的私有端点与内部origin事务helpers，复用原私有读写、锁及validator；无新引擎、部署节点或依赖事实源。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"同步新helper源码与测试清单、开发地图及Python生成索引，不改变文档服务的查询或展示拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"原DataHub控制reader将纯JSON与回环URL解析提取为stdlib共享函数，保留原异常和额外字段，不改变Broker、Provider或集成协调器调用图。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"原MCP控制reader复用stdlib纯parser并保持原版本与异常语义，不改变Host、工具授权、审批或DSH调用拓扑。","diagrams":[]} -->

## 实现与合同

- `runtime_endpoints.py`：schema 1、模式独立快照、严格端口、CAS、纯只读缺失查询与回环候选。
- `control_origin.py`：exact True 静止门；两份旧记录先共同校验再写 URL；token 不变；回滚恢复原始字节。
- DataHub/MCP 原 wrappers 共享提取后的 stdlib 纯 parser，原版本/额外字段与异常语义保持；
  事务另加严格版本类型、重复 key 和重写后 4 KiB 限制，先验证两份目标再写。
- `runtime_mode.py`：私有 POSIX 原子 writer 增加默认关闭的 strict_parent 参数，返回与保留 FD 对照
  的发布身份；已有默认调用保留创建/私有化语义，新 helper 不修复不安全父目录。
- 事务标记只保存固定名称、origin、阶段及私有身份/摘要，不保存 token 备份；进程中断或未知发布
  身份不自动恢复。当前路径与 inode 不再匹配则拒绝 commit/rollback。
- 接口不证明真实进程/容器归属、不保证关闭 probe socket 后的端口预留。

## 实际验证

所有 Python 命令在本 worktree 执行，`PYTHONPATH=$PWD`；解释器为已经获准的
`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`。

1. RED：两份新增测试，`--confcutdir=tests/research_web -q --tb=short`；2 个预期缺失 helper
   collection errors，exit 2，`logs/task-1-red.log`。最初 sandbox 日志写拒绝不是 RED；随后
   窄 escalation 运行成功并保留实际错误日志。
2. 首轮 GREEN：59 passed，0.75s，`logs/task-1-green.log`。
3. 补充负面与原边界闭包：198 passed，23.74s，`logs/task-1-closure.log`；包含两份新测试及
   `test_runtime_mode.py`、`test_runtime_auth.py`、`test_datahub.py`、`test_mcp_authorization.py`。
4. Python 索引生成与 `--check`：PASS。
5. 受管 planner manifest：11 个文件哈希匹配；完整 changed-set 规划 L4，未知路径风险保留。

6. 补充 RED：额外字段和无 site-package 导入 2 failed；重写后大小限制 1 failed；
   证据为 `logs/task-1-bootstrap-red.log`、`logs/task-1-size-red.log`。
7. 最终 Python 完整所选闭包：357 passed / 33.15s，`logs/task-1-final-python.log`；
   另在最终源码上补测启动后 commit / 非静止 rollback：2 passed / 3.80s，
   `logs/task-1-running-commit.log`。commit 只删标记并复核身份，不要求新服务仍静止。
8. 宿主 Python 3.12 `-I -S` 仅添加本 checkout 导入两 helper：PASS，无 core.settings/StoreError 业务图。
9. 文档治理：542 文件 / 79 current / 0 violations；Python index 和 diff：PASS。
10. 初次 Constraints 4 个文档回执缺项已真实保留并 signal 重规划，controller 批准最小文档扩围；
    加入 1 处已批准 JS 快照断言后，最终完整 24 文件终查 0 violations。
11. JS 初次 103 passed；README 回执真实改为 unchanged 后 102 passed / 1 failed；失败来自
    过期的生产快照 hardcoded updated，与同文件合法 unchanged fixture 相冲突。controller 批准
    仅改该断言为合法枚举，原 negative tests、changed-set gate 与 checker 均不改。
    最终复跑 103 passed / 0 failed / 2.131s，`logs/task-1-final-js-fixed.log`。
12. `logs/task-1-receipt.json` 经原 validator 核对 valid=true，result=BLOCKED：8 项本地 PASS、
    4 项外部 NOT_RUN，mergeReady/releaseReady=false。最初 evidence 引用带说明文字及遗漏
    显式外部风险的两次格式错误均保留日志，修正后记录在 `logs/task-1-receipt-validated.log`。
black/ruff/isort/mypy 在获准解释器及 PATH 不可用，未安装，NOT_RUN。
完整 scratch 报告：`.superpowers/sdd/2026-10-06-macos-runtime-port-allocation/task-1-report.md`。

## 未验证项

本报告不是真实生命周期或完整发布验收。所有 CI 均 NOT_RUN；没有 push、PR、merge、dispatch、
Docker 构建/运行或外部协调。规划器选择的外部门尚未执行，mergeReady/releaseReady 均 false。
正常 creators 在 prepare 后创建缺失文件时，必须有明确新文件身份交接，不能靠内容推断归属。
