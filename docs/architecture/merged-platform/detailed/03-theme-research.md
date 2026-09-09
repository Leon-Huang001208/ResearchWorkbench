# 主题研究 Pack 实施说明

## 职责

Theme Pack 是声明式事实产品。`ThemePackManifest` 固定主题边界、产业链、数据集、KPI、单位、频率、来源优先级、新鲜度、事件、资产暴露、研究模板和兼容版本。插件只能实现 `normalize/validate/derive`，不得联网、直接写库或调用模型。

## 接口

| API | 读模型 |
|---|---|
| `API-THM-001..002` | Pack 目录与 Manifest |
| `API-THM-003` | `ThemeSnapshot` |
| `API-THM-004` | KPI Series |
| `API-THM-005` | Value Chain |
| `API-THM-006` | Theme Events |
| `API-THM-007` | Related Assets / Exposure |
| `API-THM-008` | Data Health |
| `API-THM-009` | 从主题创建 Research Workspace，要求幂等键 |

所有主题事实进入统一 `theme_observation`，再投影为类型化读模型。首批 Pack 为黄金、航天航空、光伏、AI 基础设施/光模块；创业板 50 作为指数资产通过成分暴露关联光伏和 AI Pack。

## 生命周期与质量门

生命周期为 `discovered → validated → enabled → refreshed → ready`，质量或兼容问题进入 `degraded/disabled`。隔离记录必须保存原始值、来源、哈希和拒绝原因，不能静默丢弃。

## 实施图

- `D02-01`：Pack 功能边界。
- `D02-02`：九组 API 与数据 Owner。
- `D02-03`：主题详情请求时序。
- `D02-04`：Pack 生命周期。
- `D02-05`：Observation 到 Snapshot 的事实流。

