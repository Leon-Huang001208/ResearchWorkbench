# macOS 双运行时当前验收回执

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"记录实际验收、失败与待确认的最小行为方案；本回执不增加部署节点、权限、协议或实现。","diagrams":[]} -->

- hostPlatform: macOS；taskKind: 功能开发与本平台验收；不包含桌面或 Windows/Linux 真机任务。
- source: `3fafbc3a3a8bce5b4203f97aa90c6c332ee47c0c`；分支 `codex/switch-finalize-diagnostic`。
- integration baseline: `c24a8a161674678d572bf9ac35fab30489b40605`；original goal baseline: `4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7`。
- source snapshot 完整范围：集成 93 路径／15 本地门，原 Goal 281 路径／20 本地门，均 L4。此新增报告随后另计入完整 changed set，不伪称已经包含在上述快照。
- `a1d2087`、`eeb530c` 均为该 source 祖先；原 Task 1–12、旧 prepared integration/worktree、主工作树额外文件保留，无 reset、删除、push 或远端变更。
- hostAcceptance: BLOCKED；aggregateAcceptance: BLOCKED；mergeReady=false；releaseReady=false；整个 goal 未完成。

## 实现与源码审查

异根 Native 私有记录认证已在 `681e261c5dcb825f9d0120ea2b159a2b8d5ef276` 实现并完成规格／Python／安全审查。正常目标 lifecycle lease、目录／记录 FD、原进程与监听事实复查不放宽；RAM 观察不持久化或转移。该源码已被当前分支包含。

Docker 完整页面探测每轮预算修复在 `3fbe2645e693d358779d19a40188be0722ce1583`，审查通过。此后的 `444e3cbb6cbdb81b26fc6861eb4525e8c2a9984c` 与当前 source 仅增加已有 Native/switch 拒绝分支的固定诊断日志，均经规格与独立 Python 安全审查；不改变 JSON、检查调用次数、超时、lease、CAS 或权限。没有宣称历史切换故障已修复。

## 当前实际本地检查

- source 当前固定运行时门：`PYTHONPATH=. <原隔离 .venv>/bin/python -m pytest tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py --confcutdir=tests/research_web -q`：390 PASS，85.35 秒，exit 0。证据 `logs/main-runtime-mode-3fafbc3a.log`。
- 新阶段诊断：3 RED → GREEN；Native bridge 10 PASS，runtime-mode/protocol 94 PASS；独立 reviewer 重跑阶段用例 3 PASS。
- 当前增量 Node 114 PASS；Ruff／Black／isort、生成索引、文档治理与完整增量 Constraints PASS。来源与命令见相邻诊断任务报告；这不是主任务在当前 source 重新执行全部原 Goal 门的主张。
- 原最近 catalog 的 386 PASS／1 FAIL 及定点复测仍保留；新 390 PASS 是独立新执行，不修改旧日志或 receipt。
- 新生成 `logs/main-native-stage-receipt-3fafbc3a.json` 仅以实际新门结果替换其 NOT_RUN；原 receipt 不修改，validator exit 0。CI 仍 NOT_RUN，result 仍 BLOCKED。

## 真实安装与生命周期（严格区分 host CLI 与 guest image）

任务隔离目录 `/private/tmp/rwb-macos-ports-live.3av1gO`；共享测试 HOME `budget-home.2EF7Xe`。宿主测试 checkout 从干净 detached source 顺序更新至当前 source，没有强制覆盖或重置。

已接受 guest image 仍为 source `3fbe2645`，image `sha256:6a874f509ffb4fc6e832433bb677be5f39d610dc1e5f182d802d3a01702d77e8`；容器 `be612ad76dbaa3f7e8524a0cf80e28357052c263cad143445480e3a4caccba12`。后续 host CLI 诊断不改变任何 guest 源码或安装 manifest；不把这个镜像写成新 host HEAD 构建。

真实 Docker source3fbe 公开安装、首次／重复启动、Doctor、重启、日志、停止、端口释放、再次启动及非秘密数据保持通过。私有 tmpfs 与实际 guest UID、凭据叶／auth 文件 mode、owner、nlink 检查通过。原先 Docker 安装网络与完整页面等待失败不再作为当前构建失败；旧失败日志和容器保留。

同 HOME 的首次 Native 公开锁定安装、Docker→Native `--stop-current`、Native 启动／Doctor及同一会话和附件读取通过。另有 source681 的完整 Native restart／stop／start-again 回执，Native core/app 在后续诊断提交未变化；不把它写成新 HEAD 重跑。

共享 fixture：会话 `2aeb6ca5-37aa-4b36-9658-d6e67c9bcbf6`、附件 `68c65938b96229b45aa64e92`，34 字节 CSV，SHA-256 `d24b8b77c187b138e9907058fe1efae0f662f86d40c13d273b4e144b34dbb2ee`。Native 当前复启前读取仍为 HTTP200／idle／相同哈希。原控制 token 与附加字段比较仅保留在 RAM，实际比较布尔均 true，不输出或保存认证内容。

Native→Docker 活跃切换仍 FAIL：source3fbe、444、当前 source 的日志均保留。当前日志明确为 `native_probe phase=status_precheck code=runtime_ownership_unknown`，随后 `finalize mode=native reason=report_not_ok` 与 `runtime_stop_failed`。Native 停止成功，但模式 CAS 未执行；不能把 fresh status PASS 写成此切换 PASS。

最新两项测试服务已停止；日常 Native 的 Runtime PID68985/3081、Web PID69730/8088 未变。未删除任何真实或测试卷／容器／数据。测试 Docker 私有后端的单个合成凭据仍保留，尚未完成最终 roundtrip 后的正常删除；没有厂商凭据或付费模型调用。

## 有界诊断与尚未确认

一次只读同对象／真实 lease 观察、一次 pre/child/post 阶段观察均当前 PASS，不能认证历史失败来源。

独立临时 socket 实验实际复现：SO_REUSEADDR listener 连接由 server 主动关闭，所有 fixture socket 都关闭后，`listener_pids=closed`、PID0，而普通 bind 返回 errno48／EADDRINUSE、`port_busy=true`。活跃 bound/nonlisten 对照得到相同二元结果。因此现有检查不能区分 TIME_WAIT 与活跃预留；不能移除 bind guard 或改用 SO_REUSEADDR 掩盖占用。产品端口随后检查均 closed／可 bind，仅与时间性现象一致，不证明失败现场必为 TIME_WAIT。只读 sysctl 的 `net.inet.tcp.msl=15000`；没有修改系统值。

待确认的最小方案：只在已验证 Native 停止之后、最终安全 scope/检查之前，有界等待原端口真正可 bind，最终检查、模式 CAS、超时拒绝与 unknown/bound 拒绝保持。未实施等待、OS 新解析器、新 authority 或新框架；这项行为设计须先确认。

Harness runtime 后来一致，但更新执行者未知。未追查更新者，也未修改 runtime、manifest、全局配置、插件缓存或信任状态。

## 剩余必要门与影响

1. 活跃 Native→Docker→Native、共享 fixture／控制 origin 保持、合成凭据持久化及最终删除：BLOCKED；反向切换失败阻止本地完成声明。
2. 最终行为修复后的目标门、完整分支规划／证据 affinity 与 managed integration verification：待后续 source 完成；旧 prepared integration 仍旧 source，不冒充当前集成。
3. GitHub macOS clean installation／DSH／健康／Doctor：NOT_RUN；本地不能代替，影响 macOS 完成及远端交付声明。
4. 规划器的 Project Constraints／Research Web Checks／Docker CI：NOT_RUN；Ubuntu 证据不算 macOS，Docker Linux 责任边界保持记录，不从 Mac 调度或伪报通过。
5. 远端 push／PR／merge／dispatch／cleanup：未执行。本地尚未完成，暂不请求远端操作授权；后续必须集中读取 current budget/visibility/条件并单独授权。
