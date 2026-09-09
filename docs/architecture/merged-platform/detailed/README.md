# Research Workbench × LSH 详细实施蓝图

本目录把产品能力、页面、65 个 HTTP/SSE 接口、Service、数据 Owner、领域事件和状态机连接成可执行追踪链。开发时先确定 `CAP-*`，再沿 `PAGE-* → API-* → SVC-* → DATA-* / EVT-*` 实施，禁止从页面直接推导数据库结构。

## 阅读入口

- 可交互总索引：`outputs/merged-platform-blueprint/index.html`
- 可筛选 API Atlas：`outputs/merged-platform-blueprint/api-atlas.html`
- 功能与追踪契约：[00-traceability-contract.md](00-traceability-contract.md)
- 共享平台：[01-shared-platform.md](01-shared-platform.md)
- 全市场首页：[02-market-home.md](02-market-home.md)
- 主题 Research Pack：[03-theme-research.md](03-theme-research.md)
- 资产观察与提醒：[04-asset-observation.md](04-asset-observation.md)
- FinGPT 即时研究：[05-fingpt.md](05-fingpt.md)
- Claw 多 Agent 研究：[06-claw.md](06-claw.md)
- 平台能力与调度内核：[07-platform-core.md](07-platform-core.md)

## 38 张实施图

| 分组 | 图号 | 覆盖 |
|---|---|---|
| Shared | `A01..A08` | 能力追踪、部署、依赖、数据所有权、核心 ER、事件调度、安全边界、迁移删除门禁 |
| Market | `D01-01..05` | 功能、接口、请求、交易状态、首页事实流 |
| Theme | `D02-01..05` | Pack 功能、接口、请求、生命周期、Observation 流 |
| Asset | `D03-01..05` | 资产功能、接口、提醒请求、提醒状态、事实流 |
| FinGPT | `D04-01..05` | 即时研究功能、接口、请求、Run 状态、研究数据流 |
| Claw | `D05-01..05` | 多 Agent 功能、接口、请求、Run 状态、协作数据流 |
| Platform Core | `D06-01..05` | Runtime/Skill/Schedule/Notification 功能、接口、请求、作业状态、事件流 |

每个 JSON 是唯一可编辑图源；对应 HTML 是冻结源、通过 showcase 校验后的交付物。每张 HTML 都带 1440×900、1600×1000、1920×1080、2048×1320 的 containment 收据，以及最小/最大视口的浅色和深色截图。

## 实施顺序

1. 共享 Contract、统一资产 ID、数据 Owner 和数据库迁移。
2. 资产查询、Watchlist、提醒和持久化通知纵切。
3. 首页 live 投影、close 快照、主线规则和 SSE 失效事件。
4. 黄金 Pack 纵切，再扩展航天、光伏和 AI Pack。
5. Workspace、Session、Message、FinGPT Run、Evidence/Claim/Artifact/Note。
6. Runtime Provider、Skill、Agent Team、Claw Supervisor 和 Scheduler。
7. 旧接口通过适配器收口；迁移等价、零调用和回退证据齐全后删除重复实现。

