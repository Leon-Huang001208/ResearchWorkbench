# macOS 受管离线 Python MCP 子任务

宿主：macOS；任务：Web 功能开发与本机 Native 安全验证。工作区为既有隔离
`datahub-plugins-20261022`，基线 `35f4a3950`。未提交、push、合并、部署，未安装依赖，
未调用模型、供应商或真实凭据。最终 Host/DSH/浏览器、CI 与整体验收由主任务负责。

## 实现

- `mcp_runtime/managed_sandbox.py` 单独定义 TrustedManagedStdioTarget，保留普通
  `validate_stdio_target` 契约。仅固定 Host Python 的 PyPI module/MCPB .py 入口；
  `-I -S -B`、包内依赖、不读取环境凭据，不使用宿主 site-packages/.pth。
- Seatbelt 只读固定 runtime/精确 Homebrew 链接库/安装树及系统 runtime；每连接独立私有
  scratch 作为 HOME/TMP/XDG。禁止宿主/兄弟文件数据、安装写入、网络、fork、非固定解释器
  exec、Mach lookup/register、POSIX IPC、signal 和 process-info。仅 literal `/` 目录读取
  用于 Python 原生启动，未扩大为用户目录读取。
- 官方 MCP SDK Client/SessionMessage 完成实际握手与工具协议；Host专用transport拥有stdio字节和唯一子进程，不合并宿主环境，stderr丢弃到null。固定64KiB分块，解析前单行1MiB/连接8MiB上限、请求单帧1MiB、连接35秒时限；有界关闭/terminate/kill/wait，确认reap与句柄关闭后验证scratch inode/dev并回收。独立launch/reap任务和shield/drain循环处理重复原生asyncio取消，回收后传播取消；未知进程或scratch清理失败保留runtime.operations栅栏。
- `PackageInstaller.managed_target`、runtime 目标/缓存/启动/调用重验与插件原审批链连接。
  新政策 SHA 权限及 native policy/runtime/package/schema 摘要不继承旧授权；显式重新导入
  同包显示新权限，并清空旧 review/schema review。远程 HTTP 与非受管 Native 入口保留。
- UI 保留受支持的 offline Python 原生预览/探测/启用按钮，不再按 package_index 永久禁用。
  不支持平台保持拒绝。Doctor 仅报告入口存在与固定能力，acceptance 保持 NOT_RUN。
- 真实 SDK 的合法省略 description 为 None；仅此值在 register_tool 前规范为 ""，
  其他非法类型仍拒绝。此修复由真实 RuntimeService 探测覆盖。

## 实际验证与证据

解释器（既有批准环境）：
`/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python`

首次 TDD：新测试因缺少 managed_sandbox 模块失败；根 tests/conftest 导入 sqlalchemy 缺失，
因此使用既有 Web 定点通道 `--confcutdir=tests/research_web`，没有安装包或绕过 Web 必需用例。

本机最终定点命令：

```text
python -m pytest --confcutdir=tests/research_web tests/research_web/test_mcp_managed_sandbox.py tests/research_web/test_plugins_mcp_security.py tests/research_web/test_plugins.py --junitxml=logs/managed-mcp-sandbox.junit.xml -q
node --test tests/javascript/research_web_plugins_ui.test.mjs
python -m ruff check [本次变更的 10 个 Python 源/测试文件]
python -m black --check [同上]
python -m isort --check-only [同上]
python -m mypy --follow-imports=skip [managed_sandbox/sdk_host/service/package_installer/mcp_policy/packages/plugins.service 七模块]
git diff --check
```

定点 Python 50 PASS（25.94秒，1 条现有 Starlette deprecation），Node 4 PASS，ruff/black/isort、
七模块 bounded mypy 通过。实际 stdout 与 JUnit 分别留在
`logs/managed-mcp-sandbox-tests.log`、`logs/managed-mcp-sandbox.junit.xml`。

真实官方 SDK canary：initialize/list/call、PyPI 包内依赖导入、RuntimeService +
PackageInstaller + PluginService 的固定审批/schema复审/enable/人工分类/会话授权/call
完整调用成功。自有兄弟“凭据/DB”哨兵读写、包写入、scratch 到兄弟文件硬链接、外部软链、
Data alias、继承的测试 FD、fork、posix_spawn、subprocess、直接 exec 均拒绝。
IPv4/IPv6/Unix socket 测试目标均为测试自己创建并监听的本地端点。scratch 正常可写，
调用后已删除且已返回的自有子进程 PID 不存在。AnyIO取消、asyncio.wait_for取消、出生与回收中的两次raw task.cancel及真实SDK短read_timeout都完成回收；giant无换行、超大完整JSON、连续小帧总量超限均在adapter前拒绝，真实子进程已reap、scratch已删除。注入scratch回收失败验证保留准入栅栏，测试最后只回收自己的scratch。改包真实字节拒绝旧目标；runtime/policy 摘要注入漂移、
旧普通 target 缓存、平台不可用与凭据环境均拒绝；恢复重新构造沙箱目标。

这些 fixture 在构造 Host 前安装全内存 MCP 凭据后端，真实 keyring get/set/delete 全部
设置失败哨兵；不接触真实账号、模型配置或凭据。未修改系统 Python/runtime 字节；runtime
漂移测试注入摘要变化，不冒充系统文件变更测试。

## 未验证项与风险

- 新宿主 API/UI 最终真实 Host/固定 DSH/浏览器验证、整体验收 Router/receipt、GitHub Mac
  干净安装、独立 Python/TypeScript 安全评审由主任务继续；本子任务不宣称插件整体完成。
- Mach/Keychain 动态 canary NOT_RUN；profile 明确禁止，测试未注册真实 Mach 服务或访问
  真实 Keychain。其他平台原生验收 NOT_RUN；npm/Node 本地执行明确不支持。
- 解析前cap只适用于新增受管本地transport；普通Native与远程传输保持原合同。SDK原每请求30秒，受管连接总时限35秒另加有界teardown时间；不宣称这是OS级内存/磁盘配额。
- 信任 Host 与同 UID 管理员；不宣称抵抗可信管理员在验证与启动之间的恶意竞争。
- requirements/web.in 的现有 mcp>=2,<3 与 lock 中 mcp==2.2.0 已核对；不新增依赖。
  setup_web.py 与既有 Bootstrap 未改，仍须主任务的同候选干净安装 CI 证明兼容。

## 冻结源码与证据摘要

- `app/research_web/mcp_runtime/managed_sandbox.py` SHA-256 `68bb57c0885598a0466f1a380c60c2574f2fec716b86c9d899298fe560b5164f`
- `app/research_web/mcp_runtime/sdk_host.py` SHA-256 `0d98246310bbbef318e134328d044207180af14cea95fb725bba7cf337fbb0ae`
- `app/research_web/mcp_runtime/service.py` SHA-256 `46b645465c2bbd7b3529477386daaa571279568c9fc1c2551792e3e342bb3c1f`
- `tests/research_web/test_mcp_managed_sandbox.py` SHA-256 `ea96d7604510c5b8627b1577f4fd3f657c3700c3da4f1c3685a208f7daa6579c`
- `logs/managed-mcp-sandbox-tests.log` SHA-256 `5d5a57409e0a2c64afedb904aedba9a633e13932f25baf6b1bc0108c90ecad6f`
- `logs/managed-mcp-sandbox.junit.xml` SHA-256 `aadb6d87f9d98d03d6196df2bc8133baf6a391fe98a782dda28a4f79e7d56a6d`
