# Docker 私有临时状态修复

宿主为 macOS；任务为 Web Docker 功能修复。本任务只做隔离 worktree 本地源码验收，真实镜像、Native/Docker 往返与 macOS CI 由主任务负责；Windows/Linux 未验收。

最终补丁基线为 a316e2af6（生产源码仍来自 981e20f10，含已批准设计及 CI logs/README/Engine 投影兼容范围补充）。
`/state` 使用 rw,nosuid,nodev,noexec,uid=10001,gid=10001,mode=700,size=1m 私有 tmpfs；原宿主 state/logs 独立 bind 到 /state/logs。数据与凭据绑定保持原路径；supervisor 产品日志仍为 data-root/logs。
删除无效 initialize_state 文件预写与状态映射例外，原 runtime_state.py、认证交换与健康协议保持不变。旧 host runtime 原样保留，不迁移、不自动处置旧停止容器。
Mounts 实际 RW 和 HostConfig.Tmpfs 同时参与严格所有权检查；必需全部三个 tmpfs，拒绝缺失、重复、类型替代、错误来源、readonly 与未知/矛盾/重复选项。选项顺序、八进制 mode 与等价字节 size 按语义比较。
主任务实际 Docker 29 Engine 证明 --tmpfs 的 HostConfig.Tmpfs 完整但 Mounts 可省略重复 tmpfs 条目；因此三个 tmpfs 在 HostConfig 中必需，任何显式 Mounts 条目仍严格检查，bind/volume 遮盖拒绝。新 RED 为 actual-engine-red.log 的 3 failed、225 deselected（0.98s），随后才修改生产核验；不把这个 API 投影差异当作权限豁免。
同一 Engine 投影也约束原有无网络/无端口 control-preparer：四个 tmpfs 保持原 options，唯一实际 data bind 必须精确且 RW；未改变 creator command、image、nonce、cleanup 或 token。preparer-red.log 为 2 failed、4 passed（1.42s），随后才修改生产核验；normalized-focused-green.log 为 57 passed（3.48s），覆盖真实缺重复 Mounts 与原健康/超时/替换，以及缺失/type/uid/gid/mode/未知/重复选项、错误 RW/source、额外挂载、volume 遮盖和重复挂载拒绝。
已有 Docker CI 的 task-owned mount fixture 仅补 state/logs 的相同私有目录创建，无 runner、触发器或平台扩展。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Single Docker supervisor and DSH/Web topology remain unchanged. The mount storage boundary changes from host state bind to private ephemeral tmpfs with separately persistent logs and is documented in system, runtime, data and security modules; no graph encodes the former state bind.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Updates existing authoritative module descriptions and records source-bound verification without new architecture nodes or documentation authority.","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"The deployment graph has no state bind or filesystem mount node. Native and the single Docker DSH/Web supervisor retain their topology; only the documented Docker state storage and separate persistent log mount change.","diagrams":[]} -->

RED（生产改动前）记录于 /tmp/rwb-tmpfs-red-python.log：1 failed、21 passed、199 deselected，0.82s；/tmp/rwb-tmpfs-red-state.log：1 failed、2 passed、75 deselected，0.26s；/tmp/rwb-tmpfs-red-js.log：Compose 新绑定断言失败。测试不宣称真实镜像可用。
首次聚焦运行 /tmp/rwb-tmpfs-green-focus.log：4 failed、294 passed，40.95s；四项日志 fixture 的递归 mkdir 生成非私有 run/state 父目录，已修正 fixture，不放宽生产 guard。中间复核 /tmp/rwb-tmpfs-green-host.log：1 failed、3 passed，0.31s，保留原失败记录。
首次完整选中 Python 闭包为 752 passed、1 failed（56.11s）；原有 managed mapping mismatch 测试在一次模式记录身份瞬变时拒绝，保留失败，原源码定点复核为 6 passed（0.78s）。随后 753 passed（55.25s）；正常 Engine 投影修正后 756 passed（56.45s），均为各自当时源码快照，不替代最终控制准备器修正验收。

最终冻结生产/测试源码的 Python 闭包：785 passed（58.79s），证据 `logs/docker-private-tmpfs/python-final-complete.log`。命令为 `PYTHONPATH=. <既有验收venv>/bin/python -m pytest --confcutdir=tests/research_web -q`，随后指定 `test_runtime_mode.py test_docker_runtime.py test_container_supervisor.py test_runtime_launch.py test_protocol.py test_setup_web.py test_runtime_auth.py test_credential_backend.py test_docker_packaging.py test_runtime_contract.py`，全部位于 `tests/research_web/`。未安装包、未执行真实 Docker/service 操作。

最终 JavaScript 闭包：203 passed（4.893245375s），证据 `logs/docker-private-tmpfs/js-complete.log`。`node --test` 指定 `verification_policy.test.mjs verification_receipt.test.mjs incremental_validation_skill.test.mjs research_web_architecture.test.mjs documentation_governance.test.mjs actions_quota_governance.test.mjs repository_cross_platform_contract.test.mjs docker_runtime_contract.test.mjs`，均位于 `tests/javascript/`。

完整 changed set 为 17 个拥有路径。共享内核 11 个 manifest SHA 已核验；planner 同时保留 unexpected_behavior 与 validation_failure，选择 L4。`check_doc_sync.py`（完整 changed set）组合运行文档治理、架构与生成索引，PASS，总耗时 1.417369667s，证据 `logs/docker-private-tmpfs/doc-sync-complete.log`。Project Constraints PASS（0.155677875s）及独立 architecture PASS（0.087734875s），证据 `logs/docker-private-tmpfs/constraints-complete.log`；`git diff --check` PASS，生成索引无需变化。

规划与 schema-v2 回执分别为 `logs/docker-private-tmpfs/plan.json`、`receipt.json`；使用既有 validator 校验。12 个 local validation 的 durations 是对应真实组合命令的总耗时，重复引用不代表独立 gate 计时，不能相加。外部四个已选 gate（project-constraints、research-web-checks、research-web-docker、research-web-bootstrap）均 NOT_RUN，result BLOCKED、mergeReady/releaseReady false；未知边界与 Windows/Linux 未验证保留，不冒充其他平台证据。

自审确认 runtime_state.py、runtime_auth.py、healthcheck、依赖锁和临时 guest creator argv 无改动；状态叶不采用 bind 映射例外，既有凭据/产品日志首建行为未扩大。旧主任务三个未跟踪报告与 primary checkout 未触及。非报告 16 路径最终 binary diff SHA-256 为 `facf3c3f51e0f507c34ebe83910bd34c0510ffdf6a08482006711067c5bc551a`。

风险：Docker VM tmpfs 可能被 swap；不宣称秘密永不落盘。正常启动/重启必须用原链重建认证，固定 image 的 VOLUME /state 由 exact tmpfs 覆盖。物理生命周期与 CI 尚待主任务验证。
参考：[Docker tmpfs 文档](https://docs.docker.com/engine/storage/tmpfs/)。

实际解释器为 `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`；验收未调用全局 Python 包。最终 `node scripts/validate_verification_receipt.mjs --project . --plan logs/docker-private-tmpfs/plan.json --receipt logs/docker-private-tmpfs/receipt.json` 退出 0，valid=true，仍为诚实 BLOCKED 外部门回执。

评审后文档补充：独立 spec、Python、JS/Compose 与 security 评审无阻塞项；只修正 `03-data-files.md` 残留的宿主 Docker 状态路径段落，明确 Native 原 runtime 构建锁与 Docker `/state/runtime` 临时 build-lock、持久 logs 和保留旧 host runtime。此补充不改生产/测试字节，785/203 结果仍归属 `86c85a390` 的源码验收；仅执行该两文档 changed set 的 L0 文档治理、索引和现有 Project Constraints，结果见 `logs/docker-private-tmpfs/doc-review-*.log`。
