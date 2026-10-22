# Plugin fixture: real offline Host and SDK

宿主：macOS；任务：Web 插件验收夹具修正；范围：本机 Native Seatbelt + 官方 Python MCP SDK。未执行浏览器、完整 DSH bridge、模型推理或跨平台验证。

## 实现

`tests/e2e/research_web_plugins_fixture.py` 不再导入测试模块的 `make_service`、Fake Host、Fake Installer 或 Fake Authorization。真实构造 PluginService、CapabilityCatalog、MCPRegistryService、PackageResolver、PackagePlanner、ConfirmationTokenManager、InstallationStore、PackageInstaller、RuntimeCredentialStore、SDKHost、MCPRuntimeService 与 AuthorizationManager。

仅固定离线 registry metadata/artifact transport 与 NoModelsNative DSH transport。导入 ZIP 自带确定性、纯标准库 Python MCPB；空 environment_names。实际确认令牌由 HMAC manager 生成，真实安装器重验 artifact bytes，真实 managed_target 在 Seatbelt 下通过官方 SDK initialize/list/call。DSH binding update callback 只记录 NoModels 边界，不能作为真实 DSH restart 或模型执行证据。

构造任何 Host graph 前清空继承环境并设置显式 Memory credential backends；DataHub factory、Registry、runtime、installation integrity、delivery 与 AI news credential factory 均使用 Memory。系统 keyring get/set/delete、SystemKeyringBackend 和 PrivateFileCredentialBackend 构造 fail closed。

## 实际验证

执行：

```sh
PYTHONPATH="$PWD" /Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python -m pytest -q -o addopts= --confcutdir=tests/e2e tests/e2e/test_research_web_plugins_real_fixture.py
```

结果：`1 passed in 11.46s`。日志 `/tmp/rwb-real-plugin-pytest.log`；本次 evidence `/private/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/pytest-of-leon/pytest-1820/test_real_plugin_host_sdk_life0/state/lifecycle-evidence.json`。

真实 HTTP 顺序：ZIP import → 权限审核 → Host projection enable → 原生 preview/HMAC confirmation → 实际 MCPB install → SDK probe → snapshot schema review → enable → owned session grant → internal tool call 请求 → pending call approval → approve → SDK child 返回 `RWB_REAL_SDK_CANARY_20261022:actual-child`。

负向验证：伪 confirmation 拒绝409；credential environment 拒绝403；多余 fingerprint key 拒绝422且 mcp_reviews 无修改；缺少 session grant 的 call 拒绝403。测试发现原 NativeReview.max_length=3 不接受 managed sandbox 的第4字段，主任务修复公开契约后本链通过。

Black/isort/ruff 对夹具与测试执行通过。未安装依赖。未启动长驻服务器、未操作浏览器、Docker 或现存服务，未执行 Git mutation。

## 浏览器入口与边界

主任务冻结提交后，使用新的不存在 root：

```sh
PYTHONPATH="$PWD" /Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python tests/e2e/research_web_plugins_fixture.py --root /tmp/rwb-plugin-browser-real-20261023 --port 18991
```

URL `http://127.0.0.1:18991/#/skills?kind=plugin`。上传该 root 下 `fixture-plugin.zip`，依次点击选择全部权限、审核、启用、生成原生安装预览、确认原生安装（无 WEATHER_TOKEN 输入）、探测、查看快照、锁定 schema、空闲时启用 MCP，然后为 `Real SDK canary (no models)` 会话授权 `canary`。

产品 UI 尚无直接 tools/call 按钮；浏览器覆盖到实际 session grant。API `--verify` 单独覆盖实际 tool call 和 call approval，不得将其报告为完整 DSH/model 或浏览器触发 tool call。单用户 local-owner 角色与网关 admin/user 角色测试分别记录。

## 冻结源码浏览器实测

Root 在 macOS 以源码检查点 `7e156fb9c` 启动上述独立 18991 实例，经可见页面完成 ZIP 上传、安全预览、全部声明权限审核、启用投影、原生计划预览与真实安装、官方 SDK 探测、四项指纹审核、启用 MCP 和无模型会话授权。最终页面明确显示“已由原生 MCP 授予此会话的固定工具权限”，此前启用返回 `MCP：enabled`。包摘要为 `abb0f46521e91d66ab1ccdbe2fa5ab8f95905794135fe3a162bec61960e4fb00`。

截图仅含本任务离线 Canary，无用户凭据：`/Users/leon/.codex/visualizations/2026/10/23/plugin-real-sdk/capability-granted.jpg`。测试页已关闭，精确归属进程 PID34780 已收到 TERM 并退出，日志显示 `market_service_closed`；原18993数据源隔离实例及其他服务未操作。浏览器未触发工具调用，实际工具返回仍由前述独立 Host/SDK HTTP 生命周期证明；无真实 DSH 发现、模型或厂商调用声明。

## 固定 ToolRuntime 桥接与 CI 修复

独立质量复审在 `c88ecac3f3e2b0d363fe57dcac7abaea453b2f79` 用固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73` 的真实 Context/SystemPrompt/ToolRuntime 执行原 MCP adapter，经自有18996 HTTP Host、逐次调用审批、官方 SDK 和 Seatbelt 返回 `RWB_REAL_SDK_CANARY_20261022:native-bridge`，11.71秒通过。仅一次adapter HTTP调用，模型为0；Python/Node/自有服务器及7个SDK子进程均退出，scratch回收，端口可重新绑定。私有回执 `/private/tmp/rwb-nativebridge-quality-_z64gg3t/bridge-evidence.json` SHA-256 `08a39828c09c37ed2c7e23ab8c2bae291e107cb2d9b2a4f51002baddca4bd0a3`。该结果证明固定ToolRuntime组件的真实工具桥，不等同完整DSH服务、浏览器触发调用或模型验收。

PR191首轮Checks `39815289736` 在JavaScript合同失败：新增插件页签后，旧methods测试仍把End键末项断言为data（实际plugin）。本机单模块已重现失败，仅修正该断言并补Home返回skill，保留方法页原只读/十条/选择与重试用例；未改产品导航或削弱权限门。原失败日志保留于 `logs/plugins-final/methods-keyboard-before.log` 和 `/tmp/rwb-plugin-ci-checks-failed.log`，完整JavaScript合同及新候选原必需门仍须重验，不将旧CI改写为通过。

## 最终页面审批复审修正

`4ac8ba42` 的三CI均成功且同preview `c38c59428a039d84372c8939695eaa7d7bb1f35a`，但新增的独立JavaScript终审发现两项P2，合并因此停止：服务器普通MCP入口封闭，而插件页没有单次调用批准/拒绝；切换共享/个人范围保留旧mcpKey，页面所选和实际请求可不一致。原HTTP验收直接调用decide，不能覆盖缺失的页面入口。

Root只补插件页专用待审队列、按当前插件/组件/用户会话的approvals与decide、上下文清理及异步回包复核，不放宽后端授权。事件级测试先出现两项RED，修正后approve/deny、陌生会话/过期行拒绝、scope/自动选择及成功import的新旧上下文清理共8项PASS；import残余由SPEC事件harness先证明旧preview/snapshot/queue残留，再补reset和回归。SPEC和独立TypeScript质量复审均PASS。

冻结UI源码SHA-256 `f21bcb91a4c8c89143ed1584649848a4aa853b0c75c2ee69224365ba2ea24294`，UI测试 `3b31eaa744109995ddcf9f645cd7f5c91e1020084b17f147a218843860f9b77e`。待root在新源码提交上执行真实浏览器approve/deny及SDK结果；新候选完整本地门与CI另行取证，不能沿用4ac三CI声称最终通过。
