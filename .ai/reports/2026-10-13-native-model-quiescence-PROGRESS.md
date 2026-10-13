# Native 模型设置的历史活动校验修复

宿主 Mac mini/macOS，功能修复。正式 Native 已部署 Claw 合并提交3bd1a9a05，8088/3081健康；用户另明确批准切换到目录中的deepseek-flash并最小生成验证。切换尚未成功，原Key保持；不能认证配置或生成成功。

真实复现：PUT /api/research/runtime/model 返回503 protocol_error「原生子会话状态未知」。原生session/list和逐父session/projections显示历史mode=unknown，但live parentSessionId/origin=subagent/running=false均明确且一致。产品历史数据未删改。

最小改动：DSHClient内部subagent.list activityOnly须真bool，只有True可让mode=unknown条目提供活动；仍必须有live且父归属、subagent来源和严格bool running通过。唯一生产调用在configure_model空闲检查。默认详情/交互/执行依旧拒绝未知模式。

RED：新增3用例实际失败。GREEN目标36 passed（13.06秒），后补缺live和unknown模式+外来父/来源/字符串布尔的活动上下文拒绝回归；完整Router闭包执行中。Ruff、Black、isort、mypy已通过。Python只读评审无重要问题。源代码发布/合并与该修复的macOS CI尚未执行，正式模型生成仍NOT_RUN成功，首次旧ID探测记录failed/session-model-unavailable未隐藏。

下一步：完成全部本地门和提交后请求修复分支的发布、PR、合并及macOS CI授权，再按公开入口更新正式服务、保存目录模型并完成真实最小生成。最后归档本任务worktree、移除已合并分支，保留研究和证据。

本地收口：完整Python闭包539 passed/1 skipped/5 warnings（211.33秒），Router JS110 passed（4.466秒）；完整changed set Project Constraints、架构、文档治理、Python索引、Ruff/Black/isort/mypy通过。新增source没有Python公开符号变化。真实正式DSH的10个历史父会话活动查询全部验证为inactive，未改历史或凭据，证据deploy-fix-real-activity-proof.json。正式服务尚使用3bd1a9a05，不能把只读查询成功等同于配置已应用或生成已通过。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"仅现有DSHClient内部活动查询区分历史模式与实时running，模型设置仍用既有Host锁和原生归属事实，没有HTTP字段或进程变化。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service.py仅模型设置使用活动查询，Automation创建监控恢复、能力准入、历史执行和默认严格模式均不改变，不引入调度或schema。","diagrams":[]} -->
