# 私网邀请制多用户实施与验收

- 状态：`IN_PROGRESS`；本报告的局部证据不等于 PR、CI、合并或资源收尾完成。
- 宿主/任务：macOS Mac mini，Web 功能开发；仅验收本平台 Native 与适用通用仓库/同平台 CI。
- 授权范围：管理员开账号、Tailscale/受控网络使用；不部署、不迁移原个人数据、不新增依赖、不复制密钥、不发起付费模型请求。

## 实现边界

显式 `rwb server init|serve|doctor|reset-admin` 提供交互初始化、独立账号网关和只读诊断。SQLite 保存 scrypt 摘要和哈希登录态；网关固定 origin，通过认证 UUID 选取每用户独立 Web/DSH、数据、HOME/TMP、状态、端口及凭据命名空间。默认两实例且不自动驱逐，管理员可显式停用/停止；关闭浏览器不停止研究。

服务器 profile 拒绝宿主浏览器、Office/Wind、MCP、Hot、日程/自动化、报告 Workflow、本机配置和运维。模型只允许官方 DeepSeek；文件式文档继续原校验，native 文档在执行/内部回调拒绝。后台同 UID 代码和固定工具仍受信任，目录分离不是 OS 租户安全边界；不宣称抵御同 UID 恶意进程或任意插件。浏览器草稿/导航偏好按用户 UUID 命名，Cookie 不进入 JavaScript 存储；同浏览器 profile 的本地数据保密限制另记于安全/数据说明。

原单用户 Native/Docker 安装、数据与 resident 不转换为服务器。Doctor 明确 runtime/model `not_checked`；构建文件存在不证明固定 SHA、健康、模型或实际研究通过。

## 已实际执行的文档验证

- `node /Users/leon/.codex/skills/archify/bin/archify.mjs validate architecture docs/architecture/research-web/diagrams/01-deployment.json --quality showcase --json`：最终 9/9，0 errors/0 warnings；初次新增关系有标签碰撞，保留语义后调整标签位置再通过。
- 同一 Archify `deliver ... outputs/research-web-architecture/01-deployment.html --quality showcase --json`：PASS；规范 JSON/HTML/交付回执已同步。
- 同一 Archify `visual-check outputs/research-web-architecture/01-deployment.html --json`：四视口 1440×900、1600×1000、1920×1080、2048×1320 包含性均 PASS，自动 `visualReview` 仍为 `pending`。
- 已实际查看当前 HTML 哈希的 1440 浅色与 2048 深色截图，新增网关、用户 pair、数据与兼容分支可读；`visual-review.json` 单独记录真实查看。图形证据不认证产品功能。
- `node scripts/build_research_web_api_atlas.mjs .`：生成 PASS，291 项源码声明 / 288 个唯一 Method+Path；包含独立服务器账号及代理声明。
- `python3 scripts/generate_py_file_index.py`：已生成包含新 Python 模块的索引；该操作不执行产品代码。
- `node .agents/project-constraints.mjs --project .` 加从 Git staged/unstaged/untracked 收集的完整 63 文件逐项 `--changed-file`：exit 0、`violations: []`，日志 `logs/multiuser-project-constraints.log`。
- `node scripts/check_documentation_governance.mjs --project .`：676 份 Markdown / 92 current，`violations: []`，日志 `logs/multiuser-documentation-governance.log`。后续源码/清单变化须对最终完整集合重跑，不将本次局部证据冒称最终候选通过。

## 已实际执行的产品验证

- 既有开发解释器只读复用，无安装新依赖：`python -m pytest tests/research_web/test_api.py tests/research_web/test_protocol.py -q --confcutdir=tests/research_web`，283 passed，549.58秒。
- 同解释器 `test_service_manager.py test_local_integrations.py test_runtime_launch.py test_report_rendering.py test_multiuser_accounts.py test_multiuser_cli.py test_multiuser_gateway.py test_multiuser_runtime.py`，678 passed / 1 skipped，35.13秒。随后管理慢请求撤销新增回归另跑并通过，不用旧计数替代新增案例。
- `test_runtime_mode.py test_docker_runtime.py test_platform_capabilities.py test_multiuser_gateway.py`，502 passed，106.64秒；末次 gateway 已含管理撤销竞态回归。
- `test_sandbox.py test_runtime_contract.py test_setup_web.py test_web_bootstrap.py`，330 passed / 1 skipped，95.38秒；包含本机Seatbelt与既有安装合同，不能替代GitHub干净安装。
- `node --test tests/javascript/research_web*.test.mjs`，668 passed / 2 skipped；后续服务器默认目录/样式/包装器修复对同一命令重跑，最终日志另记。独立包装器与存储测试验证RequestInit/Abort/SSE身份及A/B草稿。
- Docker静态合同18 passed；文档/额度/跨平台仓库治理29 passed。平台合同fixture通过不等于对应平台产品已验收。
- 真实两个临时DSH/Web pair：不同root/端口/key，两端均认证200/connected=true，未带key直连403；关闭后两pair均runtime_stopped。未请求模型。
- Playwright实际管理员登录→创建账号→退出→普通用户登录；A/B侧栏各仅出现所属sentinel会话；普通账号页无管理控件。最终普通用户页面console 0 errors，桌面1920与移动390×844已查看。截图归档在`logs/multiuser-evidence/`，不进入产品包；部分早期截图受路径限制后改用工具允许位置并校验归档。
- 独立Python/安全及JavaScript评审修复Cookie jar、CSP、静态入口、RequestInit、slow-body和SSE撤销问题后复审无剩余已复现高/中问题；审查哈希与候选提交在交付时绑定。
- 原生smoke首次回收遇只读能力目录，保留错误；核对runtime_stopped、无owner记录及无打开句柄后，仅恢复本任务临时目录写权限并成功回收两个已知fixture根。回执`logs/multiuser-evidence/temporary-resource-closeout.json`。

Router为L4，完整改动集合约束PASS；最终候选/CI/收尾仍待受管交付。Windows/Linux原生及Docker多用户、真实模型、常驻部署和数据迁移保持`NOT_RUN`或不在本轮范围。服务器新数据库仅由用户显式init创建，未对现有个人目录执行迁移。

## 架构复核

<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"增加显式macOS服务器网关及按用户惰性启动的Native pair，原单用户与Docker入口保留独立。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"changed","reason":"新增SQLite账号网关与逐用户运行时资源边界，部署图明确邀请制及同UID受信限制。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"ui","structure":"changed","reason":"登录与账号页进入可选网关路径，原研究界面在认证后复用，部署图显示新增入口。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"服务器网关选择已认证用户的独立Host，原Host增加私有令牌校验，原研究协议保持。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"原Native DSH按用户私有HOME和状态惰性运行，原生guard增加profile拒绝而无第二执行引擎。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"仅在既有文档执行入口增加服务器native模式拒绝，报告组装与原Workflow拓扑及持久合同不改变。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"原离线HTTP扫描器仅增加有实际CLI装配证明的独立gateway入口，图文与Atlas生成拓扑不改变。","diagrams":[]} -->
