# FinGPT 即时研究实施说明

## 产品定位

FinGPT 负责单会话、交互式研究：用户连续追问，系统检索证据、生成 Claim 和 Artifact，并允许把 Claim 或段落置顶为版本化 Research Note。它与 Claw 共用 Workspace、Session、Message、Research Run、Evidence、Claim、Artifact 和 Quality Gate，但不暴露多 Agent 编排细节。

## 输入与接口

统一输入路由支持文本、URL、PDF 和图片。`API-RES-001..010` 管理 Workspace、Session 和 Message；`API-RES-011..016` 管理 Run、取消、重试和 SSE。创建、重试和取消使用幂等键；SSE 支持 `Last-Event-ID`，切换会话不终止后台 Run。

普通研究优先使用配置的 Runtime Provider，DSH 不可用时可回退 LangGraph。用户主动升级为复杂任务时，沿同一个 Research Run/Workspace 上下文移交 Claw，不复制会话、附件或证据。

## 状态与沉淀

主路径为 `queued → retrieving → reasoning → quality → completed`；缺少附件或范围进入 `blocked`，用户停止进入 `cancelled`。完整 Run 自动归档，Note 只进入研究区，不写入事实表。

## 实施图

- `D04-01`：即时研究能力。
- `D04-02`：研究 API、Service 和共享内核。
- `D04-03`：从输入到 SSE 的请求时序。
- `D04-04`：FinGPT Run 状态机。
- `D04-05`：输入、证据、Claim、Artifact 和 Note 数据流。

