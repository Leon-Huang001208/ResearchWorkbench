# DataHub 全源目录实施记录

## 目标

让用户在 Research Web 能看到当前仓库登记的数据能力、来源数量和真实接入状态，同时让 DSH 通过与产品品牌解耦的业务 Tool 调用 DataHub。目录存在不得等同于来源在线或已授权。

## 已实施

- 后端静态目录：13 项业务能力、21 个来源及 ProviderBinding；GET 目录不导入连接器、不联网。
- 就绪状态：代码、适配、配置、依赖、允许、可调用和最近健康分别表达。
- DataHub 业务边界：`BusinessQuery` 拒绝 URL、请求头、凭据、模块和路径；Broker 只选择目录白名单来源。
- 新 DSH Tool：13 个 `datahub_*` 名称，与 Research Workbench 品牌解耦；旧 `datahub_get_fund_data` 仅保留运行时兼容，已从新研究可选目录和消息受理白名单移除。
- 当前真实 Provider：东方财富基金和财联社；其他来源只展示登记与缺口，不伪报可调用。
- 前端数据页：能力/来源双视图、汇总、筛选、详情、来源矩阵、放入草稿和单源异步探测。
- 快照：业务查询 Manifest 记录 capability、实际 Provider、尝试来源、稳定参数及底层 Provider 查询。
- 文档与架构：更新当前主入口、API、能力、DataHub 说明；重建图 02、03、04。

## 安全边界

- 目录加载零网络；只有显式 probe 或经过 DSH 原生审批的业务 Tool 才可能访问上游。
- source 只能使用目录 ID；显式来源默认不静默切换。
- Probe 只返回安全化状态、失败代码和耗时，不返回密钥、认证材料或上游正文。
- 取消后不发布快照；数据集继续按会话归属和哈希验证。

## 当前限制

- 本轮没有把 Wind、天软、iFinD、AKShare 等旧请求代码直接包装成可调用 Provider；它们需要逐项抽取请求/解析逻辑和真实权限验收。
- 当前自动路由每项已接入能力只有一个 Provider，尚没有多来源运行时失败后的真实降级证据。
- 专业来源无实际终端或凭据时只显示 blocked/disabled，不将静态目录测试当连接成功。
- 桌面端、Windows、外部 MCP、旧摄入调度器和历史事实系统不在本轮范围。

## 验证记录

- 后端完整回归：`python -m pytest tests/research_web --confcutdir=tests/research_web -q -o log_cli=false` 最终单独运行结果为 `290 passed, 3 skipped in 33.25s`。一次与三项静态检查并行执行时，文档库隔离脚本超过固定 15 秒而失败；该用例单独重跑为 `1 passed in 11.63s`，随后完整回归通过，未把首次超时隐去或直接当作成功。
- 前端完整回归：设置 `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness` 后运行 `node --test tests/javascript/research_web*.test.mjs`，结果为 `134 passed, 0 failed, 0 skipped`。
- Python 静态检查：本轮 Python 文件及相关测试通过 Ruff、Black、isort；`mypy app/research_web --exclude '/skills/' --follow-imports=skip` 为 `Success: no issues found in 28 source files`。相关 JavaScript 文件通过 `node --check`。
- 真实公开来源最小探测：未使用账号或附件，`cls` 与 `eastmoney_fund` 均返回 `health=healthy`、`failure_code=null`。这只证明固定探测请求当时可达，不代表全部字段、日期范围或供应商 SLA。
- 真实 Web：在 DSH 3081 离线、Research Web 8088 运行时，能力中心仍展示 13 项能力、21 个来源和 2 个当前可调用来源。页面打开及切换数据页只有目录 GET；点击财联社探测后网络记录仅包含 `POST /api/research/data/sources/cls/probes`、该 probe GET 和目录刷新，没有探测其他来源。浏览器曾发现详情仍显示旧健康状态，先补失败回归，再修复为探测完成后重新读取当前来源详情；复验显示“已接入 / 健康”。
- 布局：1440×900、1600×1000、1920×1080、820×1180、390×844 五个视口均保持目录与汇总可见，`documentElement` 和 `body` 宽度不超过 viewport。人工查看了 `.ai/reports/assets/2026-09-04-datahub-catalog-1440.png` 与 `2026-09-04-datahub-catalog-mobile.png`。
- Archify：02、03、04 三张受影响图均 showcase 9/9、零错误零警告，并通过 1440×900、1600×1000、1920×1080、2048×1320 四视口及浅/深色人工核对。最终 spec/HTML 哈希分别为：02 `1429a92b…` / `1d82e926…`，03 `8c2ece42…` / `5ef7c7a6…`，04 `2a01c862…` / `8524b097…`；完整哈希在各 receipt 与 `visual-review.json`。
- 架构/项目门禁：因本工作树 Git index 的 `mmap failed: Operation timed out`，无法可靠使用普通 `git diff/status` 自动枚举；没有重建或覆盖 index。改用检查器支持的显式本轮文件清单（源码、测试、文档、图源和产物）执行 `.agents/project-constraints.mjs`，结果 `violations: []`。分支仍为 `codex/dsh-web-v1`，当前 HEAD `30748f73b195fdd2094841e95ae2248b5d99b678`；本轮修改未提交。
- Harness：任务 `task-datahub-full-source-20260904` 已记录 `completed/passed`，最终硬门返回 `verificationStatus=passed`。
- 交付运行状态：完成离线容错验收后，重新启动项目专属 DSH 3081 与本工作树 Web 8088；`GET /api/research/runtime` 返回 `connected=true`、`owned_runtime=true`、`credential_configured=true`、模型 `deepseek-v4-flash`。未修改用户原有 3080。

没有执行桌面、Windows、专业终端真实连接或所有 21 个来源的业务查询；这些结果不能解释为全源已经可调用。
