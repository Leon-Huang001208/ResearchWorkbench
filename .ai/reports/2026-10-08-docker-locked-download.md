# Task 13 锁定 Docker 下载恢复实施计划与回执

> For agentic workers: use the existing subagent-driven-development workflow for the narrow repair, with spec and quality review. This is a Task 13 recovery step, not a new architecture.

**Goal:** 在不改变依赖和安全校验的条件下，对真实锁定 tarball 超时执行一次有依据的恢复验证。

**Architecture:** 仅 Docker DSH builder 的现有 pnpm install 命令增加网络并发与单请求期限参数。Native、镜像运行阶段、默认重试、registry、TLS、最低发布时间和签名策略保持；不添加全局配置、缓存系统或测试框架。

**Tech Stack:** 现有 Docker multi-stage build、固定 pnpm 11.7.0、Node 合同测试和公开 setup-web 入口。

## 已批准设计与已有失败

用户于 2026-10-08 确认并发 8、单请求期限 120 秒。此前当前源码镜像在 APT 和 1532 项供应链校验通过后，锁定 tarball 下载失败；约 301 秒是累计步骤时间，不是全局 300 秒期限。pnpm 的默认单请求期限为 60 秒、重试次数为 2。并发压力是待验证假设，不宣称已经证明其为唯一根因或已经修复。

原失败日志保留：`/private/tmp/rwb-macos-ports-live.3av1gO/merged-source-docker-install-direct-registry-29fc5dbb.log`。
当前修复基线：`9afdfc0c3309313c444391729930d4608f63a57a`。

## 最小实施步骤

1. 在 `tests/javascript/docker_runtime_contract.test.mjs` 添加最近回归，读取现有规范化 Docker instructions，严格断言安装命令为：

   ```text
   RUN corepack pnpm@11.7.0 install --frozen-lockfile --network-concurrency=8 --fetch-timeout=120000 && corepack pnpm@11.7.0 run build
   ```

   用既有 Node 执行 `node --test tests/javascript/docker_runtime_contract.test.mjs`；先观察新断言缺少参数而失败，保留日志，不修改原失败证据。
2. 仅修改 `Dockerfile` 的该 RUN 指令：

   ```dockerfile
   RUN corepack pnpm@11.7.0 install --frozen-lockfile --network-concurrency=8 --fetch-timeout=120000 \
       && corepack pnpm@11.7.0 run build
   ```

   不新增 ENV/ARG 或修改锁文件；原 `&&` 的错误传播和现有构建日志保留。
3. 重跑同一合同模块，沿既有 planner 获取完整 changed set 的最小闭包；同步安装文档的下载故障说明，不把参数调整或合同 PASS 写成真实安装 PASS。
4. 规格及质量审查通过后本地提交，更新隔离测试 checkout 到该真实提交；以任务专属 HOME、正常公开 `./setup-web.sh --runtime docker --no-start` 入口进行一次有依据的 fresh 构建。
5. 构建成功才执行 Docker 生命周期、真实共享数据/模式切换及权限检查。相同网络原因再次失败且无新处置依据时停止重复构建，继续整理独立证据；不得放宽安全策略。

## 验收与交付边界

完整基线保留当前 master `b0ed27b75aa915346f6cf1f1db984623dfe25f14` 和原 goal `4d6a4eff6c64ef1580b0e86552d5c47391ff6dd7`。旧 22 门、Native 实测与 exact 9af macOS CI 仅按实际输入亲和性复用，不能写成新 HEAD 重跑。

修复提交后的实际命令、RED/GREEN、审查、镜像来源与后续回执另追加。此计划不是执行成功记录。fresh Docker、当前切换及受管发布/清理在取得真实证据前仍未完成；Windows/Linux 交接不改为 PASS。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅限制既有DSH构建安装命令的下载并发与单请求期限；不改变部署、依赖、认证、数据或平台边界。","diagrams":[]} -->

## 2026-10-08 隔离源码实施记录（未提交）

宿主 macOS；任务类型为既有构建命令修复。本子任务只执行源码合同与允许的静态/Node 门；真实 Docker 构建、Native/模式切换、CI 和发布由主任务继续，不能从本节推断安装成功。

实施工作树为 `/Users/leon/.codex/worktrees/rwb-task14-local-integration/dual-runtime-task14-20261008-c1-integration`，HEAD 保持 `9afdfc0c3309313c444391729930d4608f63a57a`。父源码工作树 `dual-runtime-task14-20261008-c1` 的只读 HEAD 为 `9d2e912996a8e685b7d497549003096632d60fba`，状态为空；两工作树不是同一 HEAD，不把父源码记录写成当前候选证据。没有修改父工作树或主 checkout。

仅实现以下变更：Dockerfile 唯一现有 DSH pnpm install RUN 增加批准的两个参数；最近 Node 合同使用既有 instructions 加空白规范化，严格断言完整 RUN 与原 `&& run build`；安装文档说明命令局部语义、默认重试和仍需真实验收。依赖、锁、ENV/ARG、Native 和 runtime 未修改。

实际 Node 为 `/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`（v24.19.0），以下命令中 `NODE` 仅代表该绝对路径，不代表修改 PATH 或新增 runtime。

| 命令 / 门 | 实际状态与证据 |
| --- | --- |
| `NODE --test tests/javascript/docker_runtime_contract.test.mjs`（实现前） | RED，exit 1，15 PASS / 1 FAIL；规范化后 actual 缺两个参数，expected 含参数。`logs/locked-download-repair/red-normalized.log`；初次未进一步规范化空白的失败亦保留在 `red.log`。 |
| 同一合同模块（唯一 RUN 修改后） | GREEN，exit 0，16/16 PASS，无 skip/todo，266.278 ms；`logs/locked-download-repair/green.log`。 |
| `NODE scripts/plan_verification.mjs --project .`，分别为四个 owned dirty 文件传 `--changed-file` | exit 0；4 文件，Docker packaging + documentation，L4，7 local + 3 CI 门；完整 `logs/locked-download-repair/plan.json`。 |
| `NODE scripts/check_documentation_governance.mjs --project .` | PASS，exit 0，582 files / 88 current，violations 空；`logs/locked-download-repair/documentation-governance.log`。 |
| `NODE .agents/project-constraints.mjs --project .`，同一完整四文件集合 | FAIL，exit 1；五个 `module_document_not_changed`，详见下文及 `logs/locked-download-repair/project-constraints-local.log`。 |
| `NODE --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs` | PASS，exit 0，104/104，无 skip/todo，5963.726 ms；`logs/locked-download-repair/research-web-verification-full.log`。包含 planner 单独 architecture 门的同一模块，无需重复执行。 |
| 同四文件 planner 加 `--signal validation_failure` | exit 0，L4 及闭包不变；原失败不删除，完整 `logs/locked-download-repair/plan-after-validation-failure.json`。 |
| `git diff --check` | PASS，exit 0；`logs/locked-download-repair/diff-check.log`。 |

Project Constraints 的真实阻塞：`scripts/check_research_architecture.mjs` 对命中的 dual-runtime group 无条件要求其全部模块文档出现在完整 changed set；`structure=unchanged` 只影响图源要求，不能豁免文档。四文件所有权外缺少 `docs/architecture/research-web/01-system.md`、`02-research-runtime.md`、`03-data-files.md`、`05-security-validation.md` 和 `docs/research-web-platform-support.md`。本子任务不扩大文件范围、不修改 gate、也不传入虚假的 changed set；主任务需明确接手这些真实文档同步后重验。

planner 的 `research-web-container-runtime`、`python-file-index` 为 NOT_RUN（本子任务限定 static/Node），三个 CI 门 `project-constraints`、`research-web-checks`、`research-web-docker` 为 NOT_RUN。本地补丁实现完成，整体验收 BLOCKED、mergeReady=false、releaseReady=false；不创建完成回执，不机械重复旧 22 门，不将旧 exact 9af CI 认证为未提交补丁。真实网络根因和当前 tarball 下载成功仍未知。下一步为规格/质量审查与主任务完成缺失 closure；尚未提交或真实重建。

## 同日必要文档闭包补齐与最终源码冻结

主任务明确扩展所有权到上述五份必要文档；各文档仅补一段真实构建局部说明和安装指南链接，不修改拓扑、数据/凭据、公开合同或平台 PASS。初次四文件 FAIL 及重新规划证据均保留，下面是追加结果，不能覆盖历史过程。

完整九文件集合重新 planner（保留 `--signal validation_failure`）为 L4、7 local / 3 CI 门，日志 `logs/locked-download-repair/plan-nine-files.json`。同一九文件 `project-constraints` exit 0、violations 空（`project-constraints-nine-files.log`）；文档治理 exit 0、violations 空（`documentation-governance-nine-files.log`）。实际使用已存在的 `/private/tmp/rwb-macos-ports-live.3av1gO/checkout/.venv/bin/python scripts/generate_py_file_index.py --check`，exit 0，Verified（`python-file-index.log`），未安装任何依赖。

Docker 合同 16/16 与 full Node 104/104 是本次前节实际执行证据；此后仅改文档，没有修改其测试、Docker 源码或策略。主任务允许保留这些结果，不重复运行、也不写成九文件文档追加后的新执行。

`research-web-container-runtime` 保留现有来源亲和性证据，而非本次执行：既有 `logs/task14-c1-acceptance/current-master-gate-research-web-container-runtime.json` 指向父 feature worktree 的 `logs/task14-c1/planned-python-closure.log`（1524 PASS / 1 SKIP / 1 warning，387.04 秒；完整 V2 group 含两合同模块，不能将总数写成两个模块独立数量）。本次实际复核原日志 SHA-256 为 `53f2a2d165354f9c2b264887ae3b07962183eb1a1f5d2a7df3cbc6a0f5848f50`，匹配既有来源记录；supervisor、launch_runtime、staged_runtime 和两测试的当前字节均匹配 exact 9af 基线，V2 freeze 所列 supervisor/两测试/runtime_state/lifecycle_lock 的五项 SHA-256 亦匹配。相关测试和实现未读取 Dockerfile；本次只改变 build 网络参数，runtime 输入不变。证据分别在 `container-runtime-baseline-affinity.json`、`container-runtime-affinity.json`，`newExecutionClaim=false`；既有跳过项仍为 Windows 原生 fixture，不冒充 Mac 执行。

本地九文件静态闭包完成，首次文档门 FAIL 已通过实际同步解决；三个 CI 门、真实新镜像下载/构建和生命周期仍 NOT_RUN，本子任务不创建最终平台完成回执或提升 mergeReady/releaseReady。未提交；等待规格与质量审查，随后由主任务安排授权提交和真实恢复验证。最终 `git diff --check` 与九文件 SHA-256 冻结记录于 `logs/locked-download-repair/source-freeze-nine-files.sha256`；报告哈希在完成本节后计算。
