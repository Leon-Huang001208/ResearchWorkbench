# Wind Realtime Workbook Design

## 背景

AlphaFoundry 当前通过 `xlwings` 临时向 Excel 写入 Wind 公式，再等待单元格从
`Fetching...` 变为结果。这个方式适合少量点查，不适合市场云图这种需要一次性
比较数十到上百个指数的页面。

Wind Excel 插件本身支持实时公式持续刷新。新的设计把 Wind 公式固定铺在一个
专用工作簿里，让 Excel 负责实时刷新，AlphaFoundry 只读取已经刷好的快照。

## 目标

- 页面切换 Wind 口径时读取快照，不再临时写入几百个公式。
- 指数清单可维护，后续补充 Wind、中信、申万、中证等口径不需要改代码。
- 后端能判断工作簿是否打开、Wind 是否刷新、数据是否过期。
- 前端保持 60 秒静默刷新，读取后端缓存和快照状态。
- 保留现有临时公式读取能力作为诊断或兜底路径，但不作为首选路径。

## 非目标

- 不把用户自己的 Excel 工作簿作为数据源。
- 不在前端直接读取 Excel。
- 不在首页请求里触发全量 Wind 公式生成或全 A 分页统计。
- 不把运行时 Excel 文件提交到 git。

## 文件布局

### 指数清单源文件

路径：

```text
data_sources/wind_index_catalog.csv
```

用途：

- 作为指数清单的版本化源头。
- 用于生成或更新 Wind 实时工作簿。
- 后续用户提供新的指数截图或清单时，优先更新这个 CSV。

建议字段：

```text
wind_code,name,family,category,is_active,priority,is_concept,view_key,view_label,notes
```

### 运行时工作簿

默认路径（跨平台，由 `core/settings/paths.py` 解析）：

```text
Windows: %LOCALAPPDATA%\AlphaFoundry\wind\AlphaFoundry_Wind_Realtime.xlsx
macOS:   ~/Library/Application Support/AlphaFoundry/wind/AlphaFoundry_Wind_Realtime.xlsx
Linux:   $XDG_DATA_HOME/AlphaFoundry/wind/AlphaFoundry_Wind_Realtime.xlsx
```

环境变量覆盖（优先级：显式参数 > 环境变量 > 平台默认）：

```text
ALPHAFOUNDRY_WIND_WORKBOOK_PATH=/path/to/custom.xlsx
```

开发环境可选路径：

```text
data/runtime/wind/AlphaFoundry_Wind_Realtime.xlsx
```

这个文件只用于本机运行，不提交到 git。后端启动时按配置查找工作簿；如果找不到
或未打开，应返回清晰的健康状态，而不是阻塞页面。从旧 macOS 风格路径
（`~/Library/Application Support/AlphaFoundry/wind/...`）升级时，
`WindWorkbookManager` 会自动将旧工作簿迁移到新规范路径，避免重新 prime 公式。

### Wind 插件登录检测

工作簿打开且公式已 prime 后，若 `Snapshot` sheet 仍无数据，reader 返回
`status=snapshot_empty`，消息提示"Wind快照暂无数据，请确认Wind插件已登录"。
该状态经 `/api/dashboard/sector-movers` 透传到前端，首页在板块列表为空时
显示登录提示，而非通用的"暂无数据"。Wind 插件登录为 GUI 人机交互
（账号 + 验证码/证书），代码层只做检测与提示，不自动登录。

## 工作簿结构

采用一个工作簿、多个 Sheet。

### README

给用户看的说明页。

内容包括：

- 这个文件由 AlphaFoundry 维护。
- 使用前需要打开 Excel 并登录 Wind 插件。
- 不要手工修改公式区。
- 若要新增指数，应改 `IndexCatalog` 或源 CSV。

### Config

全局配置和生成信息。

字段建议：

```text
key,value,description
```

核心配置：

```text
refresh_enabled,true,是否启用实时刷新
expected_update_seconds,60,超过该秒数视为数据可能过期
formula_version,1,公式模板版本
last_generated_at,ISO时间,工作簿最后生成时间
timezone,Asia/Shanghai,时间区域
data_owner,AlphaFoundry,数据维护方
```

### IndexCatalog

工作簿内部的指数清单镜像。由 `wind_index_catalog.csv` 生成，也允许用户在 Excel
里检查。

字段：

```text
row_id,view_key,view_label,wind_code,name,is_active,is_concept,priority,source_family,notes
```

约定：

- `view_key` 必须与前端和后端一致。
- `is_active=false` 的行不参与公式生成和快照读取。
- `priority` 用于决定页面或菜单中的默认排序。

首批口径：

```text
wind_hot_concept,Wind热门概念
wind_l1,Wind一级
wind_l2,Wind二级
wind_l3,Wind三级
wind_l4,Wind四级
citic_l1,中信一级
citic_l2,中信二级
citic_l3,中信三级
sw_l1,申万一级
sw_l2,申万二级
sw_l3,申万三级
```

### RealtimeRaw

Wind 公式常驻区。工作簿保存全量指数清单，但不再为每个指数单独铺实时公式；每个 `view_key` 的第一行放一条 Wind 批量 `wss` 公式，由 Excel/Wind 插件向下填出该口径所有指数的名称、最新价、涨跌幅。后端请求时只读取结果，不再写入 Excel 单元格。

字段：

```text
row_id,view_key,view_label,wind_code,catalog_name,
wind_name_value,last_value,pct_change_value,update_time_value,
is_concept,source,status
```

公式示例：

```text
=wss("8841258.WI,8841089.WI,...","sec_name,rt_last,rt_pct_chg","cols=3;rows=19")
```

后端切换口径时不写 Excel。公式在打开工作簿后由 `scripts/prime_wind_realtime_workbook.py` 通过 Excel 写入一次，让 Wind 插件接管刷新；软件端只读取已刷好的结果。

### Snapshot

后端优先读取的干净快照表。这里不放复杂公式，只放值。

字段：

```text
view_key,view_label,wind_code,name,last,pct_change,is_concept,source,updated_at,status
```

后端读取规则：

- 只读取 `status=ok` 且 `pct_change` 可转为数字的行。
- 按 `view_key` 分组。
- 每组按 `pct_change` 排序，生成上涨和下跌列表。
- 读取到有效实时行时，后端以本次读取时间作为快照时间，避免 Excel `NOW()` 不重算导致误判 stale。

### ViewRanges

后端读取优化索引。工作簿生成时按 `view_key` 记录该口径在 `Snapshot` 里的起始行和行数。

字段：

```text
view_key,view_label,snapshot_start_row,row_count,updated_at
```

读取规则：

- `/api/dashboard/sector-movers?view_key=...` 会直接读取 `Snapshot` 中对应口径的行范围。
- 如果旧工作簿仍是 `ActiveSnapshot` 活动槽位结构，后端保留兼容读取。
- 重新生成工作簿后必须包含该 Sheet，避免每次切换口径都扫描全部指数。

### Health

诊断页，给后端和用户看。

字段建议：

```text
metric,value,updated_at,notes
```

核心指标：

```text
workbook_open,true/false
wind_session_ok,true/false/unknown
excel_calculation_state,done/calculating/unknown
snapshot_updated_at,ISO时间
snapshot_stale_seconds,数字
active_index_count,数字
valid_snapshot_count,数字
error_count,数字
```

也可按 `view_key` 维护聚合：

```text
view_key,active_count,valid_count,error_count,last_updated_at
```

### FormulaLog

可选日志页，用于记录生成和读取异常。

字段：

```text
timestamp,level,component,message,details
```

## 后端读取设计

新增一个 Wind 工作簿快照读取服务，职责只做三件事：

1. 连接指定 Excel 工作簿。
2. 读取目标口径在 `Snapshot` 中的行范围和 `Health`。
3. 转成后端市场口径 payload。

读取服务不负责生成公式、不负责修改用户数据、不直接参与前端渲染。

建议接口：

```text
load_snapshot() -> WindWorkbookSnapshot
get_view(view_key, limit) -> SectorMoverViewPayload
get_health() -> WindWorkbookHealth
```

缓存策略：

- 后端内存缓存 TTL：1-3 秒。
- 前端静默刷新：60 秒。
- 工作簿 stale 阈值：默认 60 秒，可由 `Config.expected_update_seconds` 控制。

## 数据流

```text
wind_index_catalog.csv
        |
        v
工作簿生成/同步脚本
        |
        v
AlphaFoundry_Wind_Realtime.xlsx
        |
        v
Excel + Wind 插件持续刷新 RealtimeRaw
        |
        v
Snapshot / Health
        |
        v
后端读取服务 + 内存缓存
        |
        v
/api/dashboard/sector-movers
        |
        v
前端市场云图和上涨/下跌列表
```

## 前端行为

- 首页默认仍优先显示快速稳定的数据源，例如同花顺行业。
- 用户选择 Wind 口径时，请求后端 sector-movers 接口。
- 接口返回 stale 状态时，列表仍可展示，但页面提示“Wind 数据可能未刷新”。
- 页面每 60 秒静默刷新当前口径。
- 切换口径只读缓存，不触发 Excel 公式写入。

## 错误处理

后端必须区分以下情况：

- `workbook_missing`：工作簿不存在。
- `workbook_not_open`：Excel 未打开或无法连接。
- `wind_not_logged_in`：Wind 会话不可用。
- `snapshot_empty`：快照表没有可用行。
- `snapshot_stale`：快照更新时间超过阈值。
- `formula_errors`：部分行有 Excel/Wind 错误。

这些状态应返回给前端，前端显示可读提示，不用“暂无数据”掩盖真实原因。

## 更新维护流程

新增或修正指数：

1. 更新 `data_sources/wind_index_catalog.csv`。
2. 运行工作簿同步脚本。
3. 打开 `AlphaFoundry_Wind_Realtime.xlsx`。
4. 等 Wind 插件刷新。
5. 在 Health 页确认有效数量和更新时间。
6. 在 AlphaFoundry 页面选择对应口径验证。

## 测试计划

单元测试：

- CSV 清单解析。
- 工作簿路径解析。
- Snapshot 行解析。
- stale 状态判断。
- view_key 分组和上涨/下跌排序。
- 错误状态映射。

集成测试：

- 使用模拟 `.xlsx` 文件读取 Snapshot。
- 模拟空表、过期表、部分错误行。
- 验证 `/api/dashboard/sector-movers` 在工作簿不可用时快速返回错误状态。

手工验证：

- Excel 打开且 Wind 登录时，Wind 四级返回快照数据。
- 关闭 Excel 后，接口快速返回 `workbook_not_open`。
- 修改 CSV 后重新生成工作簿，新增指数出现在 Snapshot。

## 设计决策

- 使用单工作簿多 Sheet，而不是多个工作簿，降低 Excel/Wind 会话管理成本。
- 使用 CSV 作为源头，Excel 作为运行时快照，兼顾版本管理和实时刷新。
- 前端 60 秒静默刷新，后端 1-3 秒内存缓存，避免频繁跨进程读 Excel。
- 默认不在首页首屏加载 Wind 全口径，避免启动慢和页面卡顿。
