# Research Workbench 全仓改名与持久 Web

## 目标

将当前产品、Python distribution、CLI、Research Web、DSH 工具、数据目录、数据库默认名和 Tauri 标识硬切为 Research Workbench；增加项目级持久 Web 启动器，并安全迁移已有研究数据。GitHub 仓库同步改名属于交付步骤，但只有远程 API 实际成功后才记为完成。

## 已实施

- `research-workbench` distribution 与 `rwb` CLI；旧命令不再发布。
- CLI 历史子命令改为按需导入，`rwb web` 与迁移命令不再因旧研究、爬虫或回测模块初始化而阻塞。
- `rwb` 使用唯一入口包并优先解析当前仓库，避免复用解释器中同名 `app` 包遮蔽新实现；外部 runtime core 环境保持不变。
- `rwb web start|status|stop|restart` 从 `~/.research-workbench/dsh-source/` 的固定提交私有构建管理专属 3081/8088，状态和日志写入 `~/.research-workbench/`；命令指纹与最终 Node CLI/overlay 归属签名不匹配时拒绝终止，3080 明确不在管理范围。
- 启动前用 DSH 原生 helper 重建 profile 模块链接，并拒绝失效或越出项目私有源码树的链接；迁移前构建锁保留为 `build-lock.pre-private-build-20260904.json`，新锁绑定实际私有构建闭包。
- `rwb migrate-research-data` 白名单复制会话、附件、能力版本、数据集、产物和 DSH 历史，逐文件核对数量、大小和 SHA-256；不复制模型凭据、控制令牌、overlay、缓存和日志。
- DSH 原生脚本工具改为 `research_run_script`，数据工具只保留 13 个品牌无关 `datahub_*` 契约；移除旧平行数据查询 API。
- Web、favicon、ARIA、日志、配置、默认数据/数据库路径、Tauri 产品名、bundle、crate、sidecar 和文档身份同步更新。
- Research Web 架构图 01–03 更新服务管理、3080 安全边界、数据迁移和硬切查询入口；showcase 9/9、零错误零警告，四视口检查及人工截图核对通过。

## 验证证据

- Research Web Python：`313 passed`，包含私有 DSH 默认路径、profile 模块边界与 `exec` 后进程归属回归。
- Research Web JavaScript：`133 passed`，零 skip。
- 服务管理、迁移与运行时聚焦回归：最终 `20 passed`，归属签名修正后相关测试 `12 passed`。
- 新增 Python 文件：Ruff、Black、isort 通过；mypy 以 Python 3.12、`--follow-imports skip` 验证 2 个模块通过。全仓 Ruff 仍报告 123 个旧 CLI 历史问题，未在本轮扩大修复范围。
- Research 架构一致性检查：零 violations。
- macOS：`npm run desktop:build:debug` 成功生成 `Research Workbench.app`。
- 数据迁移：698 个文件、20,400,249 bytes，内容清单 SHA-256 `f33ea96b027cd0e03a0325f70646a3808f4ea6b033c2164938a2235eb887e232`；恢复 26 个会话后，旧研究目录已转为带时间戳的只读迁移归档。
- 持久服务实测：8088 与专属 3081 均为 healthy，重复 `rwb web start --no-open` 保持 PID 不变；原有 3080 PID 77454 未被修改。`/api/research/runtime` 返回真实模型 `deepseek-v4-flash`，新目录按安全边界不含凭据。
- GitHub API 已把远程仓库改名为 `Leon-Huang001208/ResearchWorkbench`，本地 `origin` fetch/push 同步更新并通过 `git ls-remote` 验证。

## 尚未完成或不能宣称

- 本地最终提交仍需推送并等待 GitHub Actions 的真实结果；未完成前不把远程 CI 记为通过。
- Windows 原生 CI 尚未获得本轮结果，真实 Windows 安装级冒烟未执行，因此桌面新版不可宣称可发布。
- DeepSeek Key 按迁移边界不复制；新数据目录首次运行需要用户在设置页重新填写。
