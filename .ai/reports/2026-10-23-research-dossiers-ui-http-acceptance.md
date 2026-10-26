# 长期研究档案 UI 与真实 HTTP 联合验收

宿主：macOS。任务：Web 功能开发与验收补齐。本任务不更新常驻、生产数据或凭据，不安装依赖、不调用真实模型／供应商、不派发他平台任务。

## 组合与变更

- 原 UI 与 P2 回归保留；正常 merge `96657c68f`、`5fed393ab`、`37f2d0c94`，不复制其他工作树源码。Root 后续统一更新最新 master 并做最终组合验证。
- 档案／记录／证据用真实 32hex，session 独立 36UUID；读取真实 payload 时间线、state/error_code、quality.status、24000 服务端截断与 ISO 时间窗。
- 只有实际 Prompt 带 opaque receipt。预创建、上传准备、@ 候选、创建响应丢失均不消费；接受后检查内存及两个持久首页草稿，清同 receipt，保留文字及新 receipt。
- 新成果入口走 `GET links/{id}`，保留 Host 原质量，失效状态禁用原件。signal_type 独立于 kind；已有信号修订固定 kind。交接路由准备期间锁输入与发送。
- 新 Python helper 在 TemporaryDirectory 中运行真实 Host／路由／SQLite／快照；NativeFixture 取代原生 transport。lifespan off，不启动采集器、MCP、调度或真实 DSH；凭据空读／禁写，浏览器与 Python 外网阻断。

## 实际验证

- JS 目标与既有 UI、intel、asset、navigation、capabilities、multiuser storage、Claw redo、FinGPT fusion 回归通过。精确计数见 `logs/research-web-dossiers-real-all-js.log`。
- 原离线 HTTP fixture Chrome：1440 light／768 dark／390 light 通过，保留原失败日志，不用它替代真实后端证据。
- 真实 HTTP Chrome：1440 light／390 dark，通过 UI 新建、五区、观点、证据、受控链接、扫描缺口与合格空快照零信号、review 线索筛选、准备锁、@ 零绑定、目标刷新、202 接收后绑定、持久清理、第二新会话接续、read_handle 及 403 缓存清理。
- 两视口共 4 次 NativeFixture Prompt；真实模型、供应商和外网请求均为 0。临时 fixture 登录不等于生产网关／多用户认证。
- `python -m pytest --confcutdir=tests/research_web tests/research_web/test_dossier_browser_fixture.py -q`：2 passed；Ruff、Black check、isort check、相关 mypy 通过。
- `node --check` 与 `git diff --check` 通过。首次 Python 命令遗漏项目规定的 confcutdir，触发 legacy conftest 的 SQLAlchemy 缺依赖；改用既有 Web 路径，没有安装包。实际 HTTP runner 按真实返回将 Prompt 断言修为 202，并等待 runtime／新 receipt 就绪；fixture 登录页保留 same-origin Referrer-Policy，产品权限边界未改变。

## 证据与边界

`outputs/research-web-dossiers-real/receipt.json` 记录源码 hashes、两视口结果及外网／真实模型零调用；同目录保存 UI／signals／revoked 截图、历史失败现场。`logs/research-web-dossiers-real-*` 保存 Python、JS、真实后端与错误日志。旧合同 JSON producer SHA 仅证明生成时身份；不声明等于当前组合源码。

实际 DSH 构建、真实模型质量、收费 MCP、常驻更新、Mac 干净安装 CI、跨平台及最终组合 Router／独立评审交由 Root，缺证据保持未完成。业务质量状态未改判。

## 最终复审补丁

- 仅修已指出的两个问题：opening 使用独立代数 token，只有当前 owner 的 finally 解锁；旧完成／失败保留导航身份检查且不能覆盖新 owner 的错误状态。回归从实际 app.mjs 提取 onDraft，控制两组 showRoute Promise 验证交错顺序。
- Uvicorn 固定 asyncio；增加 connect_ex 守卫。积极拒绝测试通过当前 Uvicorn get_loop_factory 建立实际 asyncio selector loop，分别验证连接、DNS 和 connect_ex；底层 tripwire 调用为 0，测试不访问网络。空 blocked_outbound 仅是运行观察，不能独自认证封闭。
- 本次目标 JS＋原核心：84 passed。Python：3 passed；Ruff、Black、isort、mypy 通过。真实 HTTP 两视口重新执行，sourceHashes 对应本补丁。此前广回归记录不冒充新补丁的再次执行。
- 积极守卫证据：`outputs/research-web-dossiers-real/network-guard-check.json`、`logs/research-web-dossiers-network-guard.log`；本次目标日志为 `logs/research-web-dossiers-final-review-{js,python,mypy}.log`。未合并 Root 更新或改变生产权限。
