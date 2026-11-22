# 主账号设置中的数据源入口

宿主：Mac mini／macOS；任务：Web UI 最小修复。本轮只验本机相关 JavaScript 与隔离 Chrome CSS，不提供 Windows/Linux 原生、生产登录或部署验收。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"本次仅将既有服务器可信主账号布尔值投影到页面，并缩小原样式隐藏规则的适用范围。沿用原设置路由与账号接口，不新增后端、权限、数据流、依赖或运行节点。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"既有Mac Bootstrap只补四个确切文件的PR/push触发和原步骤内的两个wheel资源字节检查，不新增job、runner、服务、权限、依赖、超时或其他平台执行。原安装、固定DSH、健康检查及Doctor流程保持。","diagrams":[]} -->

根因：网关向登录页面加载的 `ui/server/profile.css` 无条件隐藏 `#/settings/data`，主账号展开设置侧栏后仍没有数据源。静态导航目录包含该链接不能证明登录页面实际可见。

产品只改两处：`session.mjs` 在加载该样式前，将现有严格布尔 `identityData.primary === true` 写入 `document.documentElement.dataset.rwbPrimary`；`profile.css` 只对非主账号隐藏数据源。其他隐藏规则与后端权限不变。两个相邻 VM 测试夹具仅补真实浏览器的 `documentElement.dataset` 形状，并增加四种身份的标记及加载顺序回归。

实际验证：

- RED：原实现执行 `node --test tests/javascript/research_web_multiuser_session.test.mjs`，既有用例 1 PASS，新增四身份用例均因标记为 `undefined` 失败。
- GREEN：Node 24.19.0 执行该文件及 `research_web_mcp_login`、`research_web_account_menu`、`research_web_account_workspace`、`research_web_module_navigation` 五个 `.test.mjs`，43/43 PASS、0 SKIP。
- Chrome 157.0.8103.79／现有 PlaywrightCore：真实 session、CSS 和 `renderModuleSidebar`，仅 `/api/server/me` 使用合成身份。原 HEAD 主账号不可见；候选主账号可见并点击进入 `#/settings/data`；普通用户、非主 admin、字符串 `"true"` 均隐藏。local/hot/operations/旧 plans/provider option 仍隐藏，模型设置仍可见。0 浏览器错误、外部请求及业务写入，浏览器与临时 loopback 服务已关闭。
- 独立 JavaScript 只读评审 APPROVE，0 P1/P2；其 10/10 相邻测试包含在上述 43 项内，不重复累计。`git diff --check` 通过。
- Bootstrap 局部静态检查：YAML 解析、PR/push 各四路径覆盖及其余工作流结构不变断言、5 段 Bash 语法、4 段内嵌 Python AST 均通过，独立只读复核未发现 P1/P2。检查脚本首次因系统 Ruby 2.6 不支持 `filter_map` 停止，改为兼容写法后通过；未执行安装或 CI。

本地浏览器证据在本任务 Scratch 的 `primary-settings-fix/result.json`、`primary-admin-settings.png` 与复现脚本。该夹具只证明页面可见性，不代表生产账号或后端权限验收。

安装契约已核对：`requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py` 和安装文档无需因本次无依赖、无安装步骤变化而修改。实际先验发现 Bootstrap 原 PR/push 清单各缺本次四个确切路径，覆盖断言 RED exit 1；现分别补齐，并在原静态资源冒烟 Python 块逐字节核对已安装 wheel 中 `ui/server/session.mjs`、`ui/server/profile.css` 与 checkout，复用原 `asset-static-smoke.json`，明确记录 `installed-wheel`。未新增服务、job、runner、权限、依赖、timeout 或他平台 dispatch；现有单用户 Host 不承担多用户 `/server-static/` 入口验收，生产 gateway 仍须另验。

正式 Router 对原四路径选 L4/full-delivery，两个测试留有 unknown-path 风险；新增文档及 workflow 后须按最终完整候选重规划。CI 触发已补不代表本轮 CI 已实际运行，Mac 干净安装、固定 DSH、3081/8088、Doctor 及 wheel 资源比较均仍待最终候选 CI。

源码提交、最终候选 CI、Mac 干净安装、受管部署及生产三身份复验仍由主任务接续；未在本报告中标为通过。未新增依赖、模型调用或全链路验收。
