# 研究公开数据工具

`runtime/public-data.mjs` 将 `af_public_data` 注册为 DSH 原生工具，不启动旧摄入、爬虫、数据库或 MCP 服务。

## 契约与边界

- 参数仅 `source`、`code`、`limit`。`fund_nav` 要求六位基金代码；`cls_telegraph` 不接受代码。
- 每次调用 DSH 原生 ApprovalService，只有 `allowed-once` 后才发 HTTP。缺失审批服务、拒绝、取消均 fail closed。
- 固定 DSH 版本将后台子 Agent 的审批设为 `never`，会在请求进入 Web 前直接拒绝。公司、行业、基金 Skill 统一由父 Agent 经人工审批取数，再把结果交给子 Agent；不修改原生委派策略。
- 沿用原生父子会话目录校验；全局工具白名单和每轮调用上限不变。
- 固定 HTTPS 主机和路径，不接受任意 URL、Cookie、头、代理、环境变量或模型凭据。
- 15 秒（含响应体）截止，响应体最多 1 MiB，拒绝重定向，最多 100 条记录；不自动重试绕过访问限制。
- 输出包含 `source_url`、`retrieved_at`、`as_of`、`rows_json`、`limitations`。结果在内存中交给 DSH；模型通过已有沙箱生成文件。

## 数据源与口径

| source | 固定端点 | 返回值 / 限制 |
| --- | --- | --- |
| fund_nav | `https://api.fund.eastmoney.com/f10/lsjz` | FSRQ 日期、DWJZ 单位净值、LJJZ 累计净值、JZZZL 日涨幅；仅最近一页，不等同于总回报序列 |
| cls_telegraph | `https://www.cls.cn/api/cache?name=telegraphList` | id、content/brief、ctime 和 detail 来源链接；公开快照，非实时完整历史 |

基金协议参考当前已安装 AKShare `fund/fund_em.py` 的 lsjz 路径；CLS 复用
`data_layer/crawlers/cls/cls.py` 的 content/brief、ctime 解析语义。没有导入其服务生命周期。
2026-09-02 实测旧 `nodeapi/updateTelegraphList` 返回 404 HTML；当前公开 cache 路径返回 JSON。
页面脚本中的 `name=telegraph` 实测为空，因此只使用已实际取得记录的 `telegraphList`。
字段缺失保留 null；无记录、损坏字段、HTTP 错误与非 JSON 明确失败，不编造替代数据。

单页基金数据不足以做全量评价：复权/分红再投、基准、持仓、费率、规模与币种仍需核实。
2026-09-02 两次基金验收请求 limit=60/100 均返回20条，只代表本次响应，不能据此推断数据源全量上限。
工具不提供收益承诺、排名或买卖指令。

## 验证

`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web_public_data.test.mjs`

离线测试覆盖参数拒绝、来源失败、缺失值、响应大小、时间字段、审批拒绝/取消零请求、允许后请求及原生 schema。
真实公开端点、模型调用和 UI 审批必须另行记录，离线测试不能代替真实旅程。
