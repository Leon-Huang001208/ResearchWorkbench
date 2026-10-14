# G2B 受管制品、晋级与回退交付

宿主：24GB Mac mini，macOS/Docker Desktop，目标 linux/arm64。DSH 仍为唯一研究引擎。
本任务不更新日常生产，不合并 PR96，不发布 GHCR，不运行收费模型，不执行 Windows/Linux 产品 dispatch。

## 代码与制品身份

独立 worktree：`/Users/leon/.codex/worktrees/docker-release-g2b/ResearchWorkbench`，分支 `codex/docker-release-g2b`。
已集成依赖 PR96 的 `ca0249f309bd9689a38c496bf842141fd4a57f0d`，包含 master `0cf38ff23`。
PR96 在本轮重新核对时仍 OPEN/draft；G2B 保留依赖关系，独立 PR 不表示日常生产更新授权。

| 制品 | 实际冻结源码 | 实际 daemon image ID | 用途 |
| --- | --- | --- | --- |
| r0d | 85effb2321f3b70bcf118c0464f687bb9c155794 | sha256:ee865bcf91711dc528bd881e547875edefdc952d79157d06d720b683d60b56d2 | 历史兼容链 R0 |
| r1a | ee2461d662b4b13125162936808d410da2e8d768 | sha256:38b9d12fdcb007e0d935db7b0de47654d87789f1214f822dd41f40a8b04e10b0 | 历史兼容链 R1 |
| r2 | 64373a9460d7d689cf020aed5ee26a3d4d8b891b | sha256:f7ba7a56f0d856fe741fc1b6b24b99d13b55d16d3f36737ce853f77e27c29f4e | 最新凭据依赖集成制品 |

R0d Config digest 为 `sha256:e8f49b2d12d7928b9c343ae32e849e546470522af92ee6cd2ae96f138a5a7720`；
R1a Config digest 为 `sha256:4337a63983715c71760ab0e4a6f48ea40f0d2cbeac8c1ba3479165186056f823`。
daemon ID、Config、BuildKit manifest、归档 manifest.json/index 和 registry manifest/index 分别记录。
GHCR 未发布，registry digest 为 null；本地导出哈希不能充当远端 digest。
证据和文档后续提交不改变上表镜像来源，不把最新 HEAD 冒称已运行镜像来源。

## 实际验收

| 项目 | 结果与边界 |
| --- | --- |
| implementation | 合并后相关闭包通过；最终 PR/CI 状态以最终回执为准 |
| local_release | r0d/r1/r1a/r2 实际冻结、构建、封存、流式校验、标准归档导入 PASS |
| stage_acceptance | r0d/r1/r1a/r2 的真实协议/API/静态/版本/加密后端/空闲 PASS |
| promotion_rehearsal | r0d → r1a PASS；与 stage 同一 image ID，没有第二次 build |
| rollback_rehearsal | r1a → r0d PASS；真实运行旧镜像，合成数据和 processBridge 解析均保留 |
| registry_publish | NOT_RUN，未获独立远端镜像发布授权 |
| registry_digest_pull | NOT_RUN |
| real_supplier_for_this_artifact | NOT_RUN，不索要 Key，不借用 G2A 旧调用证据 |
| daily_production_deployment | NOT_RUN，用户明确排除 |

演练只使用 `prod/g2b-rehearsal`，loopback 18089，可信登记 `purpose=rehearsal`。
stage 使用 18088。二者五卷完全不相交，随机模型身份不同；升级、回退及中断恢复保留目标五卷和身份。
合成模型值为公开测试夹具，经现有 JS/Python 桥解析，只保存布尔证明，不读取/输出主密钥。

实际故障：候选在维护窗口被本任务夹具 TERM，控制器确认候选退出、运行已验旧版本后返回
`candidate_failed_previous_restored`，账本为 `restored`。中断夹具在 begin 成功后等待，
仅本任务控制器被 KILL；旧写者继续，新的 Web POST 实际收到 503，重复 apply 返回
`unfinished_transaction_recovery_required`；显式 `rollback-plan --recovery` / apply 完成，
账本再次 accepted/r0d，没有第二个写者或重新初始化五卷。

维护并发、已受理工作继续/排队等待、DSH 主/子活动事实、报告与 Automation worker、
恢复入口后账本/控制回复失败不强停、错平台/未验收/过期回执/归档错误等使用受控回归夹具。
它们不证明收费研究、真实供应商、Linux 任意研究代码沙箱或公网/多人能力。
任务专用故障脚本 `tests/fixtures/g2b_fault_controller.py` 只由管理员显式运行，未进入应用镜像。

新 G2A 修改凭据格式源身份，r2 与历史 r0d/r1a 的兼容性未知。不得通过修改 seal/receipt/账本、
放宽格式门或重新初始化旧密钥来强行晋级。历史演练和最新制品 stage 分别记录。
实际 r2 deploy-plan 返回 `release_format_compatibility_unknown`，没有写入业务或部署事务。
实际管理员拒绝夹具对过期计划、错 image ID、错 seal、陈旧 target hash 全部提前拒绝，
每次后完整目标账本保持相同；结果在 `actual-refusals.json`，不是修改真实封存制品来伪造通过。
R2 Config digest 为 `sha256:87a5eef5bdc6591c37db23b5a142550fb493641a1e5f346fa4e2f0687fab0bca`，
seal 为 `sha256:45334f51b0c321162bc063565e492c412747d487d347613047dede1e23f04a66`。

## 本轮实际命令与复现

完整入口见 `docs/research-web-docker.md`。以下为本轮真实执行的命令形式：

```sh
./rwb-docker release r1a create --source ee2461d662b4b13125162936808d410da2e8d768 --reuse-dsh-image sha256:1c94c017574f163689bdb12122cd917008688c638e382b43b611238e9575a33b
./rwb-docker release r1a verify
./rwb-docker release r1a import
./rwb-docker stage candidate replace-image --image sha256:38b9d12fdcb007e0d935db7b0de47654d87789f1214f822dd41f40a8b04e10b0
./rwb-docker stage candidate up
./rwb-docker release r1a accept --instance candidate
./rwb-docker stage candidate stop
./rwb-docker release r1a deploy-plan > "$HOME/.local/share/rwb-docker/plans/r1a-promotion.json"
./rwb-docker release r1a apply --plan /ledger/plans/r1a-promotion.json
./rwb-docker release r1a apply --plan /ledger/plans/r1a-promotion.json
./rwb-docker release r1a rollback-plan > "$HOME/.local/share/rwb-docker/plans/r1a-rollback.json"
./rwb-docker release r1a apply --plan /ledger/plans/r1a-rollback.json
./rwb-docker release r1a rollback-plan --recovery > "$HOME/.local/share/rwb-docker/plans/interruption-recovery.json"
./rwb-docker release r1a apply --plan /ledger/plans/interruption-recovery.json
./rwb-docker prod g2b-rehearsal stop
```

ID 为一次性不可变命名；已存在时 create 拒绝覆盖。新重放需新 ID、完整冻结 SHA，并先确认
stage 回执期限，按管理器验证所有权。不要直接删已有 release、五卷或业务维护标记。
故障重放使用管理根日志中的 `run-fixture.sh`，或者在同样的 256MiB/CPU0.5/PIDs64、
只读管理员镜像与 Socket 边界中显式执行 repo 夹具；只加载 `/ledger/releases/r1a/control/release.py`，
只操作固定演练目标。`interrupt` 等待 begin 回执后只终止该管理员控制器，随后必须显式 recovery。
普通 dev/应用仍没有 Socket。故障夹具不构成日常生产操作入口。

## 最小检查和证据

合并后的 Docker 内 Python 闭包：335 PASS / 3 SKIP / 1 dependency deprecation warning，332.74s。
包含 manager/release/maintenance/model credentials/full API/container supervisor/runtime launch；
跳过项保留原测试原因。Docker 内 JavaScript 必需闭包加模型契约 135 PASS；背景任务闭包此前 76 PASS，
没有把未改变的 G0/G1/G2A 全套重跑。Ruff/Black/isort 和发布/维护/client mypy 通过。
完整 changed set 约束最初发现三个 UI 文档/复核缺口，已修正并重新通过，不把旧失败写成 PASS。
py_file_index、文档治理、架构 source/rendered/visual receipts 已实际核验；最终 CI 尚待最终提交。

原始回执留在 `/Users/leon/.local/share/rwb-docker/logs/g2b/`，包括
`r1a-promotion.json`、`r1a-repeat-apply.json`、`r1a-rollback.json`、
`r1a-retention.json`、`r0d-rollback-retention.json`、`volume-identity-proof.json`、
`actual-candidate-failure.json`、`interruption-kill-proof.json`、`interrupted-repeat.log`、
`interruption-recovery.json`、`r2-stage-accept.json`、`r2-incompatible-plan.log`、
`actual-refusals.json`、`final-resource-snapshot.json`、
`final-python-closure.log`、`final-js-docker.log`、
`final-static-green.log`、`final-constraints-fixed.json`。
管理器/控制器日志只记录稳定分类，制品/receipt 与业务卷分离，秘密不上传 CI。

初期真实失败保留：格式源路径错误、非 root 公共源码目录模式、daemon ID/Config 混淆，均修复。
一次非本任务触发的 Docker EOF 中断发生在晋级事务前，旧接受版本未改变；只修正 Engine
默认 DNS `null`/`[]` 等价投影，自定义 DNS 仍拒绝。未主动重启 Desktop、调整 VM 或停止外部 probe。

收尾：builder、stage、prod/g2b-rehearsal 停止，全部数据与归档保留；dev/g2b 恢复，
挂载本任务 worktree、3GiB/CPU2/PIDs256，无 Socket。外部 probe 保持原 ID 与
480MiB/CPU1/PIDs128，持续运行。实际 VM 8319238144 bytes，不自动扩容或重启。
原有 dev 工具镜像继续用于受管工作区；新正式应用制品 R2 使用合入后的 Web 锁构建。

## 下一阶段入口

先审阅并解决 PR96/G2B 依赖，再由对应平台接手 exact SHA 原生/CI。新的凭据格式链需独立
初始化的测试目标或明确兼容证据，不能自动迁移旧接受实例。GHCR `./rwb-docker release ID publish --confirm-publish`
仍需独立明确授权和认证条件；本轮没有远端产品推拉证据。
多人、公网 TLS/认证、Linux 研究沙箱、完整备份恢复及日常生产迁移继续未实施/未验。
