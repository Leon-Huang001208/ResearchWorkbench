# Research Web 本地依赖与测试基线修复报告

## 结果

- 根目录现有 `.venv` 已补齐 Research Web 最小依赖；`uv pip check` 验证环境内 95 个包兼容。
- Research Web 全量回归从安装前的 231 个初始化错误，以及补齐基础依赖后的
  `6 failed, 893 passed, 4 skipped`，收敛为 `901 passed, 4 skipped`。
- Starlette 的 `httpx2` 兼容弃用警告已消失。剩余 1 条警告来自 Starlette 对
  `anyio.abc.BlockingPortal` 旧别名的上游使用，不是依赖导入或 setup error。
- 当前主 checkout 的未提交内容和 `.venv.broken-*` 均未修改；源码在基于最新
  `origin/master` 的隔离 worktree 中完成。

## 本地最小依赖

按用户授权，仅在安装命令中移除失效代理变量后，向现有 `.venv` 安装：

- `keyring 25.7.0`
- `matplotlib 3.11.2`
- `beautifulsoup4 4.15.0`
- `mcp 2.2.0`
- `httpx2 2.12.0`
- `apscheduler 3.11.3`
- `pdfplumber 0.11.10`
- `PyMySQL 1.2.0`

后三项是第一轮安装后由静态导入检查与真实测试暴露的、项目已声明的 Research Web 直接依赖。
未执行 `pip install -e ".[dev]"`，也未安装 `sentence-transformers`、`vectorbt`、`akshare`、
`cjpy` 或其他机器学习、回测和行情采集栈。未创建、读取或修改真实 API 密钥与系统凭据。

## 源码与测试修复

- `pyproject.toml` 的 `dev` 依赖加入 `httpx2>=2,<3`；其他最小依赖沿用已有正式声明。
- `rwb` 在隔离 worktree 没有本地 `.venv` 时，通过 Git common directory 复用主 checkout 的项目
  解释器，同时保持当前 worktree 为源码根。
- MCP PyPI 安装器优先使用当前解释器的 pip；精简 uv 环境没有 pip 时，回退到宿主已有 uv，继续
  强制 `--no-index`、哈希、无依赖和目标目录，并使用 staging 私有缓存、禁用用户配置。pip 与 uv
  都不可用时返回稳定的 `package_installer_unavailable`。
- 能力目录和 Report Workflow 测试显式注入来源可调用性及 Provider readiness；不再把本机可选
  SDK、Keychain 状态或后台进程调度速度当作产品契约。生产检测、安全门和失败语义没有放宽。

## 已执行验证

- 八个最小模块导入：通过。
- `uv pip check --python .venv/bin/python`：95 packages compatible。
- Artifact/PDF、Capability、MySQL 定向回归：`22 passed`。
- 启动器、Capability、MCP Runtime 与 Provider readiness 定向回归：`43 passed`。
- `python -m pytest tests/research_web -q`：`901 passed, 4 skipped, 1 warning`。
- 定向 Ruff：通过。
- 定向 Black 与 isort：通过。
- MCP installer 定向 mypy：通过。
- Research Web 架构完整性：`violations: []`；文档同步检查通过。
- `git diff --check`：通过。

真实外部服务测试保持明确跳过，不把网络、厂商软件或凭据缺失伪装为通过。本报告不处理仓库既有
全量格式化与类型检查债务，也不声明桌面端或 Windows 安装级验证。
