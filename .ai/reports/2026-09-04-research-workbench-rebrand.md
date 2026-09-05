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

- Research Web Python 最新完整回归：`310 passed, 3 skipped`，包含私有 DSH 默认路径、profile 模块边界与 `exec` 后进程归属回归；跳过项受当前运行环境条件控制。
- Research Web JavaScript 最新完整回归：`132 passed, 1 skipped`；跳过项是固定 DSH schema 条件检查。
- 服务管理、迁移与运行时聚焦回归：最终 `20 passed`，归属签名修正后相关测试 `12 passed`。
- 新增 Python 文件：Ruff、Black、isort 通过；mypy 以 Python 3.12、`--follow-imports skip` 验证 2 个模块通过。全仓 Ruff 仍报告 123 个旧 CLI 历史问题，未在本轮扩大修复范围。
- Research 架构一致性检查：零 violations。
- macOS：`npm run desktop:build:debug` 成功生成 `Research Workbench.app`。
- 数据迁移：698 个文件、20,400,249 bytes，内容清单 SHA-256 `f33ea96b027cd0e03a0325f70646a3808f4ea6b033c2164938a2235eb887e232`；恢复 26 个会话后，旧研究目录已转为带时间戳的只读迁移归档。
- 持久服务实测：8088 与专属 3081 均为 healthy，重复 `rwb web start --no-open` 保持 PID 不变；原有 3080 PID 77454 未被修改。`/api/research/runtime` 返回真实模型 `deepseek-v4-flash`，新目录按安全边界不含凭据。
- GitHub API 已把远程仓库改名为 `Leon-Huang001208/ResearchWorkbench`，本地 `origin` fetch/push 同步更新并通过 `git ls-remote` 验证；`master` 首次推送后本地与远端均为 `36c5c4d28e7e9178adb852619aa2ed12153b9ce7`。
- 推送前 `git fsck --connectivity-only --no-reflogs` 发现一次 2026-08-06 本地历史合并缺少 `docs/superpowers` 树对象；依据两个父提交合并后的完整 Blob 清单重建，生成哈希与缺失对象 `68958c5d3c7afb95fff27b1a9d1434f8cb9343e3` 完全一致。仓库随后无 missing/broken link 并正常推送，未强推或改写提交。
- GitHub 首轮 Project Constraints 正确发现 4 个旧服务缺少异常边界、2 个数据仓库反向依赖服务层；现已把事务内市场首页失效 helper 下沉到数据层，并在旧研究执行边界加入结构化异常日志后原样抛出。聚焦回归 `54 passed`。
- 首轮 Desktop Verify 的 macOS/Windows job 均在 PyInstaller 阶段发现 `data/industry_graphs/` 缺失；这是硬改名提交误删的 3 个既有中性资源。已从改名前父提交逐文件恢复，三个 Git Blob 哈希分别精确匹配 `d0abee1c...`、`5e7d726b...`、`e99f44ad...`，sidecar 资源契约回归通过，等待下一轮原生 CI。
- 边界修复后的聚焦旧链回归为 `97 passed`。完整 Research Web Python 为 `310 passed, 3 skipped`，JavaScript 为 `132 passed, 1 skipped`；跳过项是环境/固定 DSH schema 条件，不是失败。项目约束、文档同步、Research Web 架构一致性和产品身份检查均通过。

## 尚未完成或不能宣称

- GitHub `master` 已完成首轮推送；Project Constraints 的边界修复正在复验，Desktop Verify 仍需等待本轮真实结果，未完成前不把远程 CI 记为通过。
- Windows 原生 CI 尚未获得本轮结果，真实 Windows 安装级冒烟未执行，因此桌面新版不可宣称可发布。
- DeepSeek Key 按迁移边界不复制；新数据目录首次运行需要用户在设置页重新填写。
