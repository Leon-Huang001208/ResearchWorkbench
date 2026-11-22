# 长期研究档案独立评审修复

macOS Web功能修复，在原Core隔离worktree实施。未改Root扫描、main新增router、CI或常驻数据；未联网、处理真实凭据或调用收费服务。

## 复现与修复

独立评审指出三个真实缺陷。先新增6个失败回归，`/tmp/rwb-dossier-review-red.log` 为 **6 failed**：

- 一项绑定旧证据missing／changed／revoked让整个目标会话读取与普通发送失败。
- 可变报告被覆盖后关联仍只有旧quality，缺少字节状态和受控打开检查。
- 数据集公开rows完整时，已删除／变化的raw原件仍被视为可用。

修复采用逐项缺口投影：来源保留state/error_code，精确读取继续拒绝，只有available来源获admission并进入质量观察；质量上下文明确携带dossier_evidence_gaps，失效项不能贡献事实。好来源与无关会话操作保持可用。普通send回归通过原生turn/end事件结束先前fixture任务，保持原delivery_pending门。

报告关联优先绑定同hash的既有不可变report-version，缺少版本时持续检查保存hash；新增受控links/{id}投影，覆盖或缺失的原件拒绝打开。历史quality保持原内容的语义。

数据集原始响应逐项验证路径、size和SHA256；同一验证用于归档、读、service备份及恢复。失败保留旧SQLite，不用可读取rows冒充原始来源完整。

按Root追加的P2评审，signal记录处置在已有可选dossier_signal_index上同事务json_set更新state，保留其他字段，不创建该表。故障注入证明记录、事件、索引状态一起回滚。

## 验证

使用主任务已批准现有venv，MCP关闭且传输／keyring均为隔离fixture，无新依赖。

- 修复后的档案单测／API：**25 passed，16.51s**，含上述6项及不可变报告优先、备份恢复校验；日志 `/tmp/rwb-dossier-review-green.log`。
- 近处回归包含档案、API、Store、来源读取及质量scope：**61 passed，17.70s**，日志 `/tmp/rwb-dossier-review-regression.log`。随后追加的可选信号索引回归：**1 passed，0.39s**；两次实际执行分别记录，不冒充同一次62项运行。
- 本次修改文件的Black、isort、Ruff及git diff --check由提交前实际检查确认。
- 受管MCP组合、完整Router、CI／同候选Mac安装与独立再审仍由主任务执行，未宣称通过。
