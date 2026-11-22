# 自选导入集成索引补齐

本次为 macOS Web 集成文档修复，基线 `a7956f9c7721d935bd6fcad7d0461111233cf3f2`。只由原生成器刷新 `docs/generated/py_file_index.md`，不修改 app/tests、依赖、生成器或验证规则，不重新解释 source `6e85dc96` 的历史执行证据。

首轮完整集成检查真实失败：`python scripts/generate_py_file_index.py --check` 返回 1，耗时 0.789 秒，未因资源中断；原始日志与回执保留在 `logs/watchlist-full-verification/pyindex.log` 和 `pyindex-receipt.json`。此时后续 Node/API 门为 NOT_RUN，不能把索引修复当作完整集成通过。

只读诊断确认 integration a795 与 feature 8ff 的索引 blob 相同。生成器扫描当前目录的 Python AST，不依赖 Git tracked 状态或 checkout 路径。差异仅为本任务已有源码：AssetDirectory.offline_snapshot、两条导入路由及 DTO、AssetWorkspace 的导入方法、Store threading 导入，以及 watchlist_import 模块和类型结构。此前 feature 现有日志未找到对应当前源码的真实 PASS 回执，不能推断绝对从未执行；当前索引确实 stale，原通过声称不可认证。不能归因“提交后才变旧”、clone 或路径变化；本轮以 fresh expected 和实际 --check 结果重新认证当前机械门。旧日志与 handoff 保持原 hash，不回填；source 6e85 的 pin 仅认证 app/tests，不表示旧文档索引正确。修复前 expected 差异 111 行，SHA256 `11e5aa2e89dae82633365658a3427187450a9d9d41ba3b0f143dca6821a476e6`。

本轮只运行原生成器及对应索引、文档治理、架构、约束和差异完整性检查。命令与实际结果在 `logs/watchlist-index-fix/`；完整集成、同候选 CI、远端与部署仍交由 root 后续执行，不在本次文档修复中宣称完成。

实际结果：原生成器刷新成功；fresh `--check` 返回 0（0.854 秒），架构 0（0.487 秒）、文档治理 0（0.178 秒）、完整 changed-set 项目约束 0（0.162 秒）、`check_doc_sync.py --project . --base 1be480183187f181dbcee486d943aabb3559c9d5` 0（1.150 秒）、`git diff --check` 0（0.020 秒）。逐字 argv、日志 SHA256 和耗时见 `logs/watchlist-index-fix/results.json`。本次差异仅生成索引和本补充报告，源代码、测试和原证据均未改变。
