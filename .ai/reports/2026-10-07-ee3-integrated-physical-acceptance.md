# ee3 macOS dual-runtime physical acceptance

hostPlatform=macos；taskKind=Web 功能开发与本地集成；hostAcceptance=BLOCKED；aggregateAcceptance=BLOCKED。
本报告只认证冻结源码 `ee3c96e552ef12c054d8dc93166b535e3183a5e0`，不认证后续质量分支或未实施的异根判断。

## Source and isolation

- 原 goal 基线 `4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7` 到 ee3：272 路径；当前集成基线 `c24a8a161674678d572bf9ac35fab30489b40605` 到 ee3：81 路径。两套既有 planner 均 L4，11 个受管内核哈希实查一致。
- 受管任务 `dual-runtime-task14-20261007-a1` 已从首次 prepare 的真实文档冲突恢复到 prepared，integrationCommit=ee3；未发布、未 dispatch、未清理任何 worktree。
- 实测 detached checkout：`/private/tmp/rwb-macos-ports-live.3av1gO/checkout`；HOME 分别为 `home-live` 与 `docker-first-home.KbDe9N`。Native 使用测试私有 credential home，不使用日常凭据。
- 原 a1d2087/eeb530c、旧分支、Task 1–12 及历史回执保留。runtime 后来已一致，更新执行者仍未知；本轮没有重查或修改 Harness/global 配置。

## Actual local checks

- `logs/task14-final-api-documentation-ee3.log`：API 与文档 74 PASS，316.85s。
- `logs/task14-final-contract-ui-ee3.log`：政策/回执/skill/UI/Docker 合同 181 PASS，14.588s。
- `logs/task14-final-goal-constraints-ee3.log`：完整 272 路径约束 PASS；文档治理实际退出 0。
- 原始 26 Python 路径质量检查：Ruff 132 项、Black 23 文件、isort 失败。发现已有独立工具环境后实际执行，不能沿用旧“工具不可用”记录当通过。后续质量分支另报结果，不覆盖本失败。

## Native: actual installed-source lifecycle

实测日志根均为 `/private/tmp/rwb-macos-ports-live.3av1gO/`：

- `native-install-ee3c96e55.log`：公开 `./setup-web.sh --runtime native --no-start` 退出 0；既有受管 venv/锁输入可复用，本次固定 DSH 与当前产品 overlay 实际构建。不是新空白 venv 首装证据，不替代干净安装 Mac CI。
- `native-start-ee3c96e55.log`、`native-doctor-ee3c96e55.json`：启动、Doctor 退出 0；实际 Web 53170 就绪。
- `native-restart-ee3c96e55.log`、`native-status-after-restart-ee3c96e55.json`：重启退出 0，Web 58688／DSH 58689，两角色 owned/listening/protocol passed/ready。
- `native-stop-ee3c96e55-correct-path.log`、`native-stop-release-ee3c96e55.json`：停止退出 0，原两个 PID missing、58688/58689 关闭，日常 8088/3081 与另一个测试 Docker 57444 保持。
- `native-start-again-ee3c96e55.log`、`native-doctor-start-again-ee3c96e55.json`：再次启动、Doctor 退出 0，Web 58688／DSH 60137 就绪。
- `native-final-stop-ee3c96e55.log`：最终正常停止退出 0；最终释放证据见下。

会话 `106746f3-4612-4192-a69f-b49b6bea2743` 和附件 `075d5a82d5196171ba5590fd` 在首启、重启、再次启动均 HTTP 200，session idle/id 一致。39 字节测试 CSV SHA-256 始终 `47ad7335dab05dd4668880628ab1fdbee1f1fd9642a4cd160484f167353912eb`；对应 `native-persistence*ee3c96e55.json`。
既有 RAM-only 比较进程在各启动阶段输出 tokens_preserved/other_fields_preserved/origins_match 全 true；未持久化 token 或其哈希。

执行者错误保留：首个 `native-stop-ee3c96e55.log` 因 PATH 把 `/usr/sbin` 错写为 `/usrsbin`，监听探测失败且操作拒绝。纠正回原标准 PATH 后一次正常停止成功；不是产品修复或绕过归属检查。

## Docker: first installation success, later lifecycle failure

- `docker-first-install-ee3c96e55.log`：公开 Docker no-start 首装退出 0，code_commit=ee3；接受镜像 `sha256:3ad266dd86f9f0e15119b1c64e59cd23826287ad8715f8611dbd6bbc0ef2c023`。安装后产品根、Native PID 与 endpoints 仍不存在，未手写 manifest 或先装 Native 到该 HOME。
- 实际 checkout 已有有效 Native venv，用于覆盖此前真实分类差异；不能声称本次测试证明所有无 venv 分支。
- 构建使用已授权测试 HOME 的既有代理。APT/锁定依赖/固定 DSH 构建完成；pnpm 下载内部重试后成功，不改 TLS、签名校验、源或全局代理。
- 构建结束后，仅该测试 HOME 的 Docker httpProxy 改成既有 HTTP 29758，避免把 SOCKS HTTP 设置注入 runtime 而触发 HTTPX 可选 socksio 缺失。HTTPS/noProxy 不变；没有安装 socksio 或改锁。
- `docker-first-start-ee3c96e55.log`、`docker-first-doctor-ee3c96e55.json`：首次启动/Doctor 退出 0，宿主自动端口 57444，内部 DSH 3081；双健康、owned，根 HTML 与静态入口 HTTP 200，state=tmpfs/logs=bind/volumes verified。
- `docker-first-permissions-ee3c96e55.json`：guest UID 10001，实际内核 `/state` tmpfs；runtime 0700/auth 0600/current owner；测试凭据写读删 true、目录 0700/记录 0600/nlink=1/current owner。只使用显式测试 namespace，不读模型密钥。
- `docker-first-repeat-start-ee3c96e55.log`：普通重复 start 实际退出 1，runtime_ownership_unknown；健康容器当时保留。`docker-first-native-observer-ee3c96e55.json` 证实 Native 观察也为此状态，不能把首次成功推导为完整生命周期通过。
- 未以相同原因继续 force restart/start 重试。该 HOME 的重启、stop→start、首次 Native 切换和共享数据往返仍 BLOCKED/NOT_RUN。
- `docker-first-logs-ee3c96e55.log`、`docker-first-stop-ee3c96e55.log`：日志与正常停止均实际退出 0；精确 CID `03fcc7b1d736427e9b9e73b6fd8efe5d26ac6c116b3fe13dca7407524e6ccc4d` 保留为 stopped，不删除镜像、容器或数据。

执行纪律记录：Docker logs 是只读，但执行者未先取得其 tool terminal 回执便发出 stop；两个最终回执均退出 0。不把这组调用声明为严格串行生命周期序列。

## Remaining gates and evidence boundary

`final-test-release-ee3c96e55.json`：58688/60137/57444 关闭，最后 Native PID 21370/21495 missing；日常 8088/3081 仍开放。没有停止无关服务或删除数据/卷。
旧 8e/1872 的双模式往返与私有状态证据只属于对应源码／镜像；本报告没有冒充在 ee3 重跑完整 Docker 往返。

异根缺项已有新的只读依据：日常根的两个 PID 经正常 Native ownership contract 验证，现有 stdlib `bootstrap_service_facts` 又复核完整私有记录/argv/start/listener/root pair；不只是不同 checkout。实际 Root B 后续 guard 尚未持有和重检该 pair 的调用内证明。推荐方案是有限标准根、pin/重检既有记录，不保存 fresh 权限、不假造 endpoint；行为方案等待用户选择，未实施。

必要远端门仍 NOT_RUN：macos-14 Bootstrap 与通用仓库 CI；已选择但阶段暂停的 Docker CI 仍保留未执行，不改为可选。Windows/Linux 产品任务按用户范围暂缓，不冒充通过，也不作为 Mac 真机替代证据。GitHub 阅读链接可达性待授权发布后验证。
当前不足以宣称本地验收全部完成或整个 goal 完成，不具备发布就绪声明；未执行 push/PR/merge/tag/dispatch/rerun/release。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Records frozen-source physical installation and lifecycle evidence plus explicit blocked subsequent Docker calls; adds no runtime component or authority.","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Records actual API fixture persistence and independent Native acceptance, without API/schema changes or model calls.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Preserves historical evidence and exact source affinity in an additional task report; no old receipt or visual evidence is rewritten.","diagrams":[]} -->
