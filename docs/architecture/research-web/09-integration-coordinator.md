# 统一集成协调器

一键安装为协调器提供可复现的 Web 依赖与 CJPY 0.5.2，但不把“已安装”当成探测或可调用成功。
没有 `CJ_KEY` 时天软保持待用户配置；保存后的秘密由凭据库在每次探测/查询时动态读取，协调器仍
按既有五阶段模型和责任归因记录结果。
安装器对 Windows DSH checkout 启用命令级长路径，Runtime 首次启动先初始化固定 `web` Profile；
Profile junction containment 与 PowerShell PID 探针仅保证 Windows 3081 安全启动和回收；
这些修复只保证协调器所在 8088/3081 可复现启动，不把任何来源状态提升为可调用。
服务管理器在 spawn 前校验 Doctor 安装事实；安装未就绪时协调器和启动探测都不会创建。
该前置门不把 CJPY 已安装、数据源已登记或历史探测快照误报为当前可调用。
Node 选择与 Runtime build lock 的一致性只决定 3081 是否可安全启动，不改变协调器五阶段状态、
授权或 Provider 可调用结论。

## 目标

`IntegrationCoordinator` 是 Research Web Host 内的数据源与本机能力状态编排层。它不替代
DataHub Provider、本机验证器、Tabbit 或 MCP Host，也不创建新的守护进程。它负责把这些既有
边界的登记、授权、探测、适配和 Runtime 可调用事实聚合成一个可恢复、可审计的状态模型。

```text
设置页 / Runtime 状态
        ↓
IntegrationCoordinator
  ├─ DataHub 单来源 probe（公共来源最多并发 4）
  ├─ 本机发现 probe（串行）
  └─ Tabbit 保存配置 + Runtime 应用配置 + 实时诊断
        ↓
原子状态快照 + 批次进度 + 兼容接口
```

## 状态契约

`IntegrationItemStatus` 使用 `schema_version=1`，每项包含：

- `registered` 与 `implementation_state`：区分目录登记、已实现和未交付。
- `configured` 与 `authorized`：配置存在不代表已授权。
- `stages`：固定为登记、授权、探测、适配、可调用五阶段。
- `last_attempt_at`、`last_success_at`、`stale` 与安全 `error_code`。
- `capabilities`：品牌无关业务能力 ID。
- `runtime_callable` 与 `responsibility`：责任限定为 `user/system/vendor/developer`。
- `bucket`：`available/checking/user_action/system_fault/not_delivered` 五类页面汇总。

认证失败和账号权限不足归入 `user_action/user`，因为下一步是用户更换本机凭据或联系供应商开通账号；
依赖缺失、版本错误和凭据库不可用归入 `system_fault/system`；限流、供应商不可达和供应商响应异常归入
`system_fault/vendor`。页面不再把无效 Key 误显示为本机系统故障。

快照仅保存白名单字段，不保存密码、Token、Cookie、MCP 环境变量、用户文件正文或本机绝对路径。
Provider、配置和环境指纹变化时，旧的成功证据保留为历史时间，但当前探测阶段变为过期，不能继续
证明可调用。

## 探测与授权

- 服务启动先读取最后一次原子快照，再异步创建 `trigger=startup` 的全量批次。
- `trigger=manual` 的全量刷新会对全部公共来源和已经取得逐来源授权的来源真实执行探测；未授权的
  账号、终端或可能计费来源明确显示跳过，不以一次“刷新全部”绕过授权。同 scope 同时只保留一个
  活动批次。
- 无凭据公共来源默认允许自动探测；账号、终端或可能计费来源需要逐来源一次性授权。
- 授权撤销后不再自动探测该来源，旧成功证据立即过期。
- DataHub 继续拥有单来源探测语义；本机管理器继续拥有软件发现和真实 Office 验证语义。
- 协调器关闭时取消未完成任务并把批次标为取消，不静默留下“检测中”。

写操作同时要求精确同源 `Origin` 与页面显式用户动作头，用于阻止普通跨站页面驱动本机探测。
当前产品是单用户 Web-only 回环服务，没有可向普通浏览器安全发放且能抵御同用户本机进程的私有
会话凭据；因此同源 XSS 和能直接伪造 HTTP 请求的同用户本机进程属于本批明确保留的威胁边界，
不能把上述头部描述成此类攻击的认证机制。

## API

- `GET /api/research/integrations/status?scope=all|data|local`
- `POST /api/research/integrations/probe-batches`
- `GET /api/research/integrations/probe-batches/{id}`
- `PUT /api/research/integrations/{id}/auto-probe-consent`

原 `/data/sources/{id}/probes`、`/data/probes/{id}`、`/local-integrations/probes` 和本机验证接口继续
保留；本机验证内部的 Workbook timeout 明确受 180 秒总预算减 10 秒协调余量约束，不改变协调器
状态或来源可调用判定。旧页面数据接口允许增加字段，但不删除既有字段。

## Runtime 工具

十五个 `datahub_*` 品牌无关工具常驻 Runtime。可用来源由 DataHub Broker 在每次调用时根据最新
配置、探测、适配和授权状态选择，因此连接状态变化不要求重启 Runtime。没有可调用来源时查询明确
失败；显式 `source` 且 `allow_fallback=false` 时不得静默换源。

Wind binding 只投影已登记且能由现有 `WindAdapter` 证明等价的业务能力、数据集、字段、日期、
复权和单位；不接收公式、表达式、路径或凭据。股票行情要求显式 `asset_type=stock`，指数继续走
独立 points 口径，无法等价映射的宏观利率、基金持仓和大宗交易保持不可调用。自动 Excel 查询使用
容量为 1 的专用 worker 和独立隐藏工作簿；超时或关闭未确认时保持单飞或 poison，不选择、保存或
关闭用户工作簿。

十八个 CPU 有界 Skill 不是新的协调器来源，也不直接持有 Provider 会话；它们只消费会话内已经
物化并带 dataset refs 的相对 JSON 快照，受统一行数、字节、序列、标的和 64 KiB 完整结果预算约束。
不可变能力快照仍由既有会话生命周期发布，清理只处理产品会话目录、调用收据和快照引用，不跟随
链接、不删除 DataHub 原始来源或用户打开的 Excel 文件；真实 Wind/Excel 对照不足时能力保持
disabled。

## 当前批次边界

协调器底座批次已交付协调、持久化、自动探测、统一 API/UI、Tabbit 双状态和 Runtime 工具常驻。
现有 Provider 闭环批次进一步完成 AKShare 轻量真实网络探针、天软/MySQL 安全错误投影，以及
精确 `cjpy==0.5.2` 的离线哈希锁、`PyMySQL>=1.2.0` 依赖契约。AKShare、财联社和东方财富基金已有真实探测、查询、
快照及 Runtime 调用证据；天软和 MySQL 在用户完成逐来源授权并提供真实外部条件前仍保持
`user_action`，不得以依赖可导入或模拟连接替代成功证据。

专业数据源扩展、其他公共/监管来源、文件同步和本地 MCP 真实调用属于后续批次；未交付项必须显示为
`not_delivered/developer`，不能计入用户“需处理”。

## 2026-09-23 稳定性变更回执

本轮服务重启活动门禁、会话/子 Agent 目录有界读取和浏览器目录加载呈现均不进入
`IntegrationCoordinator`。五阶段状态、五类责任桶、探测授权、批次并发、快照持久化、DataHub
动态选源和 Tabbit 双状态关系均未变化；无需修改协调器 API、Automation 关系或架构图。
