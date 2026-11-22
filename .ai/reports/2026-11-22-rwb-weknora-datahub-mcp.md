# WeKnora 主动调用 DataHub

宿主：Mac mini / macOS；任务：Web 功能开发。本机仅认离线协议和数据链测试，真实 WeKnora、金融源、生产 OAuth、Mac CI 与其他平台均另验。

<!-- architecture-review {"group":"research-web","structure":"unchanged","reason":"复用既有账号网关/OAuth→Host→DataHub→Provider拓扑和Store/快照；新增显式scope、固定入站工具与无DSH数据上下文，不增加运行节点、数据库、执行内核或依赖。","diagrams":[]} -->

原四项 `rwb.read` MCP 工具只能读批准冻结资料，不能主动取数；原研究台省略 session_id 又会调用 DSH 创建会话。因此增加 WeKnora 可显式申请的 `rwb.data.query` 和三项公开 FRED/BLS 查询、状态及取消工具，用 Store 注册 grant 独立数据上下文，再复用原 DataHub。旧 grant 不增权，原四工具的选材/零 Provider 语义保持。

修正本次实际暴露的两个研究台问题：新查询记录保存参数摘要，防同幂等键异参被误当相同请求；准确取消同时处理尚未执行的 desk 外层任务和 DataHub Provider 任务，确保终态而非永久 running。已完成数据不删、不重发。

实际首轮：新8项测试先出现6个预期失败（scope拒绝、metadata缺项、context/cancel路由404、异参被受理、构建器不存在），实现后8/8 PASS。失败事实保留简短摘要，已结束且可由测试重建的夹具按本轮用户规则正常清理；成功批经原工具 retired。首轮8项包含在下述13项中，不把 mock Provider 说成金融实源成功。

最终本机 WIP 源验证为新增 **13 unique PASS**，包括真实 SDK bearer→工具→账户 HTTP→原 DataHub→冻结 manifest/rows、scope 授权码/刷新 HTTP 链、同键异参、准确取消、跨 grant、读取中撤权和 BLS mock403。固定 SDK 的资源元数据原只公布 required read scope，实际反例失败后改用 SDK 公开 metadata route factory，支持 query 但不要求旧 read token增权。`data_success` 两项反例先失败再修，区分 completed 与 dataset failed；scope 权限集合按标准接受不同顺序，存储与响应规范化。原 store/OAuth/HTTP四工具/研究台五模块另外80项 PASS，四批各20顺序执行并全部 retired。13与前述8/12重叠，只计13；合计93 unique，不重复累计中间批。

相关 Ruff、Black、isort 检查通过，9份所改产品源码的 targeted mypy（`--follow-imports=silent`）通过。所有 pytest 使用原 `test_artifact_retention.py run --mode wip`，没有活动测试根。证据位于本任务 Scratch 的 `datahub-adapter`，最终13项与80项各有原 JUnit/回执；这不是最终提交 SHA 或CI认证。新增 Python 测试的索引、最终全变更集门、独立评审和干净 Mac 安装由主任务统一完成。

Scope/工具契约、参数及结果限制见[模块文档](../../docs/research-web-mcp-datahub.md)。没有新增依赖、SQL结构迁移、生产修改或模型调用。DataHub 值、单位、缺失、原件、日期与 PIT 保留原语义；WeKnora全任务链与成熟工具替换是否通过，由真实现场及独立金融核验决定。

## 真实 Host HTTP 门补修（2026-11-23）

首次真实 WeKnora→隔离 Gateway/Host 请求只到元数据与工具发现，query 在 `POST /data/contexts` 之前被实际 Host 的 service-only 白名单以 `embedded_research_disabled` 拒绝。Host PID/cwd 与当前0a源码工作树一致，日志明确 `embedded_research_route_denied`，不是旧安装包或内部 business-query。原13项使用裸 FastAPI 路由夹具，未覆盖 `create_app` 总门，不能再将其称为真实 Host/launcher 证明。

因此只在 `main.py` 既有白名单补上下文、查询、按ID状态及取消四类准确路径，不打开其他 data 写或原生执行。新增两项先在未修代码真实失败403：正常 `create_app(ExternalExecutionClient)` 的中间件/生命周期加 FRED mock；以及实际 RuntimePool→process_spec→uvicorn Web子进程的 contexts/query/poll/cancel。后者使用未注册 source 在 DataHub 内部收口为 failed，零外部金融请求，不宣称实源成功。真实旧driver/Agent未由此补修操作或重发；最终GREEN与Root重新实源续接分别记录。

补修本机 WIP 实测2/2 PASS（4.54秒），原入口 middleware 的 FRED Mock 得到1行快照，实际子进程的无网络查询得到正常 failed 状态；contexts201、query202、status/cancel200，原生session、模型PUT及来源配置PUT仍403。两根按期望RED→GREEN后成功批正式 retired，真实测试子Host均由原RuntimePool正常关闭；当前任务的真实9543 driver未动。仅跑这2项，不重跑原93项。相关Ruff、Black、isort及diff检查通过；最终提交、独评、CI和真实WeKnora复测仍由Root接续。证据为本任务Scratch `datahub-adapter/service-only-boundary-20261123/`。
