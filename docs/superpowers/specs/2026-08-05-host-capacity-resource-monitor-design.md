# AlphaFoundry 主机容量资源监控第三期设计

**日期：** 2026-08-05  
**状态：** 已确认，待实施  
**范围：** AlphaFoundry 桌面端“系统监控”页面

## 目标

在不扩大 AlphaFoundry 进程监控边界的前提下，同时展示应用自身资源归因与整机容量余量。用户应能在同一页面判断：

1. AlphaFoundry 使用了多少 CPU 与物理内存；
2. 这些用量相对整机能力的占比；
3. 整机是否因 CPU 或可用内存不足而处于压力状态；
4. 压力来自整机容量还是 AlphaFoundry 任务本身。

## 已确认的边界

- AlphaFoundry 进程表仍只显示 API、其子进程及已登记的 Worker/Scheduler。
- 整机侧只读取 CPU 与内存的汇总容量，不枚举、持久化或展示其他应用的名称、PID、命令行、连接或资源明细。
- AlphaFoundry 原始快照继续每约 2 秒采集，并在页面保留最近 5 分钟，用于定位短时任务突发。
- 整机趋势按分钟汇总、持久化 24 小时，用于判断日内容量压力；异常事件继续遵循现有长期事件策略（默认查询 90 天，未解决事件始终可见）。
- 本期不增加原生桌面通知；整机容量事件在系统监控页置顶、确认和解决。

## 指标定义

### AlphaFoundry 指标

- `alpha.cpu_percent`：受控 AlphaFoundry 进程 CPU 百分比之和，以单个逻辑核心为基准；可大于 100%。
- `alpha.memory_bytes`：受控进程 RSS 之和，表示当前驻留物理内存，不是虚拟地址空间。
- `alpha.cpu_host_percent`：`alpha.cpu_percent / host.logical_cpu_count`，表示 AlphaFoundry 相对整机总计算能力的占比。
- `alpha.memory_host_percent`：`alpha.memory_bytes / host.memory_total_bytes * 100`。

### 主机指标

- `host.cpu_percent`：操作系统给出的整机 CPU 使用率，范围 0–100%，跨全部逻辑核心平均。
- `host.cpu_idle_percent`：`100 - host.cpu_percent`，仅用作当前空闲算力近似值。
- `host.logical_cpu_count`：逻辑 CPU 核心数，用于换算 AlphaFoundry 的整机 CPU 占比。
- `host.memory_total_bytes`、`host.memory_used_bytes`：整机物理内存容量与当前已用量。
- `host.memory_available_bytes`：操作系统可立即或可回收后提供的内存。页面的“剩余内存”只使用该字段，避免把缓存占用误认为内存耗尽。
- `host.memory_available_percent`：`available / total * 100`。

采样失败必须返回字段不可用状态，不可将未知值改写为 `0`。

## 页面设计

顶部使用四张并列摘要卡：

| AlphaFoundry | 整机 |
| --- | --- |
| CPU：核心等价用量与整机占比 | CPU：当前已用、近似空闲、逻辑核心数 |
| 内存：RSS 与整机占比 | 内存：已用/总量与可用内存 |

页面中部保留 AlphaFoundry 最近 5 分钟 CPU/内存原始曲线，并增加整机最近 24 小时的分钟级 CPU/可用内存趋势。页面下部继续仅列出 AlphaFoundry 进程和已登记任务归因。异常卡与历史项增加来源标签：`AlphaFoundry` 或 `整机容量`。

## 架构与数据流

1. `ResourceMonitoringService` 在现有 AlphaFoundry 受控进程快照中附加主机汇总快照。主机采集只调用操作系统汇总 API；不得调用系统进程枚举 API。
2. 当前快照接口返回 `summary`（AlphaFoundry）与 `host`（整机）以及稳定的可用性/警告字段。
3. 当前快照每约 2 秒用于页面刷新。服务在首次进入一个新的 UTC 分钟时，将主机汇总写入既有 `MonitoringRepository` 的 `HealthMetrics`，使用 `Subsystem.RESOURCE_MONITORING` 和受控的 `extra` 字段。
4. 查询历史时从既有监控仓储读取过去 24 小时的分钟级记录；保存新记录时删除超过 24 小时的同类容量汇总。异常/事件记录不受此清理影响。
5. `ResourceMonitorAlertService` 在当前快照上分别评估整机容量压力和 AlphaFoundry 进程压力，并继续使用既有告警/事件生命周期。

## 接口

- `GET /api/system/resource-usage`：扩展当前响应，返回 `host` 对象及 AlphaFoundry 相对整机占比。
- `GET /api/system/resource-usage/host-history?hours=24`：返回最多 24 小时的分钟级主机汇总点；不返回其他应用进程字段。
- 现有 `GET /api/system/resource-events`：每条整机告警包含稳定来源 `source_scope: "host_capacity"`；AlphaFoundry 告警为 `source_scope: "alphafoundry"`。

所有 API 响应继续仅输出字段白名单；内部异常、命令行、其他应用身份和原始系统错误均不对前端暴露。

## 告警规则

| 事件 | 连续条件 | 严重级别 | 自动恢复 |
| --- | --- | --- | --- |
| 整机 CPU 压力 | 3 个分钟样本 ≥ 85% / ≥ 95% | warning / critical | 连续 3 个分钟样本低于警告阈值 |
| 整机可用内存不足 | 3 个分钟样本 ≤ 15% / ≤ 8% | warning / critical | 连续 3 个分钟样本高于警告阈值 |
| AlphaFoundry 任务失败、Worker 消失、采样失败、自身压力 | 沿用第二期规则 | 沿用第二期规则 | 沿用第二期规则 |

同一规则在未解决期间去重；恢复时更新已有事件为已解决，而不是反复创建事件。

## 故障处理与日志

- 主机采样异常写入结构化日志，仅记录稳定错误类型；AlphaFoundry 进程采集不受阻断。
- 主机历史持久化异常只记录警告并继续返回当前快照；界面保留上一帧历史，显示“历史暂不可用”。
- 读数部分缺失时，独立标记具体字段不可用，其他有效指标继续展示。

## 验收与测试

1. 服务单元测试：主机指标换算、内存可用量口径、不可用字段、逻辑核心数缺失、无系统进程枚举。
2. 持久化测试：每分钟仅写一条、查询 24 小时、过期汇总清理且不影响事件。
3. 告警测试：warning/critical 阈值、连续样本、升级、去重、连续恢复与来源标签。
4. API 测试：当前快照与 24 小时历史响应白名单、参数验证和安全降级。
5. 前端静态/交互测试：四张卡、双趋势图、来源标签、无数据和历史失败状态。
6. 运行验证：分支桌面预览中检查当前接口、历史接口、图表加载与事件置顶；不将 macOS 验证表述为 Windows 验证。

## 非目标

- 不展示整机其他应用的进程树、命令、网络连接、磁盘 I/O 或内存明细。
- 不保留主机 24 小时以外的资源时序数据。
- 不新增桌面原生通知、云端遥测或第三方监控依赖。
