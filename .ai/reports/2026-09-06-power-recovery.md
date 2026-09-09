# Research Workbench 断电恢复记录

## 症状与根因

- `127.0.0.1:8088`、专属 DSH `127.0.0.1:3081` 均未监听；断电结束了后台进程，本轮未配置开机自启。
- 源码仍在 `codex/web-consolidation`，起点提交为 `39c377a`；报告 Workflow 与研究数据目录均存在。
- 旧状态文件记录的 PID 已死亡，但项目路径来自先前 checkout，严格状态校验在清理死 PID 前失败。
- `.venv` 继承的 macOS hidden 标志使 Python 跳过项目 editable `.pth`，导致 console script 报 `ModuleNotFoundError`。

## 修复与验证

- 新增“先前 checkout + 死 PID”回归；修复后 `tests/research_web/test_service_manager.py` 11 项通过。
- stale 状态只在 PID 已确认不存在时清理；存活或无法确认的 PID 继续拒绝接管。
- 清除该项目虚拟环境的 macOS hidden 文件标志，使 Python 正常读取 editable `.pth`；没有安装或升级依赖。
- `rwb web status` 可从仓库外目录执行。
- 重新启动后 DSH 3081 PID 3224、Web 8088 PID 3227，二者健康；`/api/research/runtime` 返回已连接且模型为 `deepseek-v4-flash`。
- 浏览器重新打开 `#/claw` 和 `#/workbench/assets`，创业板50周报、华安ETF周报和资产观察均可见，console 零错误。
- 图 03 已加入断电恢复启动序列；Archify showcase 9/9、零错误零警告，四个视口无溢出，四张明暗截图均已人工查看。
- Research Web 全量 Python 回归为 401 项通过、3 项跳过、零失败；服务管理目标文件通过 Ruff、Black 与 isort，架构一致性门禁无违规。

## 边界

- 原有 3080 没有被启动、停止或修改。
- 本轮仍未安装开机登录项；电脑再次关机后需要执行 `rwb web start`。
