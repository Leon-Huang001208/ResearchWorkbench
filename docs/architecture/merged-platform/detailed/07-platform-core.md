# 平台能力、调度与通知内核实施说明

## 内部模块

平台内核包含 Runtime Registry、Skill Validator、Scheduler Coordinator、Domain Event Dispatcher 和 Notification Service。它们通过内部 Contract 被业务 Service 调用，不额外包装一套公共万能 API。

## 公共接口

| API 组 | 用途 |
|---|---|
| `API-PLT-001..004` | Runtime Provider 注册、读取和更新 |
| `API-PLT-005..008` | 声明式 Skill 注册、验证和更新 |
| `API-SCH-001..005` | Agent Schedule 生命周期 |
| `API-NOT-001..002` | 通知收件箱与已读状态 |

## 调度一致性

所有刷新、快照、Agent 日程和提醒求值先持久化 `scheduled_job`。Coordinator 使用 PostgreSQL 租约保证唯一执行者，默认禁止同一日程并发重入；错过多次执行只合并最近一次并记录事件。执行结果和 `domain_event` 在事务边界内关联，Handler 幂等消费。

通知必须先进入 PostgreSQL 收件箱；Web 展示和 Tauri 原生通知是两个交付适配器。原生通知属于桌面增强能力，不得成为业务成功条件。

## 实施图

- `D06-01`：Runtime、Skill、Scheduler、Event、Notification 能力。
- `D06-02`：公共 HTTP API 与内部 Contract 分界。
- `D06-03`：日程创建、租约和领域事件时序。
- `D06-04`：Scheduled Job 租约状态机。
- `D06-05`：配置、作业、事件和通知数据流。

