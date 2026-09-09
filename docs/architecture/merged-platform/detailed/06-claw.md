# Claw 多 Agent 研究实施说明

## 产品定位

Claw 负责复杂、长时、多角色协作研究。入口和研究沉淀与 FinGPT 共用，但运行面展示 Supervisor、Agent Team、Shared Blackboard、步骤、预算、工具调用、阻塞和恢复状态。

## 编排边界

`AgentTeamDefinition` 声明角色、Skill、依赖和预算；Supervisor 动态分解任务并通过 Blackboard 协作。每个 Run 强制最大步骤、最大并发、token、费用和截止时间。声明式 Skill 只能使用提示词、I/O schema、内部工具、附件、受控网页和已注册 MCP；任意代码、Shell、文件系统、任意 URL 和未授权 MCP 均被拒绝。

`API-AGT-001..004` 管理 Team Definition；Claw Run 仍使用 `API-RES-011..016`，确保状态、SSE、取消、重试和 Artifact 都回到共享研究内核。

## Runtime 行为

DSH 通过 `RuntimeProvider` 侧车接入且无数据库权限。普通 Provider 故障可回退，但 Claw 所需多 Agent 能力不满足时必须进入 `blocked_runtime`，不能假装退化成单 Agent 已完成。恢复 Provider 后从持久化 Blackboard 和 Run checkpoint 继续。

## 实施图

- `D05-01`：Supervisor、Team、Blackboard、Skill 和预算能力。
- `D05-02`：Team API、Runtime 和研究内核边界。
- `D05-03`：多 Agent 请求与进度时序。
- `D05-04`：Claw Run、blocked_runtime 和预算终止状态机。
- `D05-05`：Team 输入、协作、质量门和 Artifact 数据流。

