# WeKnora 正式 RWB MCP 与金融数据网关

<!-- architecture-review {"group":"inbound-mcp-readonly","structure":"unchanged","reason":"在原OAuth、账号Host和DataHub链扩展scope与业务工具，部署节点、凭据归属、冻结存储和研究执行器保持原拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"金融网关是现有外部Provider类目中的固定上游，复用查询、凭据和快照，不新增存储、调度器或第二套数据平台。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"界面改动仅为进度目录中的待验证能力条目，不修改导航、页面布局、交互、外观或报告生产流程。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅将新增金融Provider回归纳入原Checks命令，job、runner、依赖、权限、预算和平台验收拓扑不变。","diagrams":[]} -->

平台：macOS arm64 Mac mini；功能开发及现有服务配置。任务基线
`3c3f84ddd2a03b837474e56d606b3453e9ab2129`，独立受管工作树。

## 实现

- 配置 DataHub 金融 MCP Provider，固定 HTTPS 地址、五项原生工具、OS 凭据库。
- 新增显式 `rwb.data.configured` 范围及两个入站工具，复用原 BusinessQuery、账号后端、
  grant 上下文、查询记录、幂等、取消和冻结结果读取。旧 FRED/BLS scope 不自动增权。
- 金融 MCP 的网关／工具／已识别厂商业务错误分别处理；异构未认证结果保留原 envelope。
- 无新依赖。SDK、公开安装入口及锁文件保持；新增 Provider 测试纳入原 Checks 作业。

## 已观察

- 金融 MCP 鉴权、五工具发现、八家目录通过；目录均为 windows_worker，不能代表权限通过。
- 新 DataHub Provider 实取岗底斯 `600519.SH` 的 2026-11-16 至 19 日 K 线 4 行，
  保留原字段及空值，未认证单位、复权、完整历史及 PIT。
- 正式 WeKnora 到 RWB 的端到端 TLS 已通过固定目的地址的本机字节转发连通，保留原证书校验。
  OAuth 已由正式 admin 确认，工具目录 7 项同步成功，原生会话提交 FRED 查询成功。
- 该会话读取快照返回 410：运行中的旧版将 MCP data-only 上下文误判为退役 FinGPT。
  主线已有对应修复，其他部署任务正在切换；本任务不改其事务或宣称该读取已通过。

## 验证与剩余

Provider 7 项定点检查通过（SDK fixture 缺 tools/list 的失败已修正）；新 configured scope 的
7 项检查通过，非 FRED 来源的查询读回断言修正为原合同 items 后单项通过。
静态 Ruff／Black 通过，测试成功临时根已由原工具退休。

最终源码候选 d8b67e70 的 MCP/OAuth 与金融适配 178 项回归通过；架构／文档／预算合同 208 项通过。
新增 iFinD 嵌套错误检查已纳入该批。完整 changed-set 项目约束、Ruff、Black、isort 和文档治理通过。
必要 CI、独立审查、生产部署以及
正式账号的完整快照读回尚待最终候选验证；不得把本记录当作发布或全部数据源验收。
OpenBB 未变更；其他厂商本轮未逐家取数，不沿用旧文档的额度状态。
