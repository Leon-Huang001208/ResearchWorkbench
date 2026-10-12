# Docker root module alias 修复

- 宿主：macOS；任务：Web 打包功能修复；范围：本地源码合同。真实 Docker、CI、Windows/Linux 未执行。
- 基线：`9d0e7909d1fab51d4e9e86b56b30c4e906c447ab`。
- architecture-review: 内部资产派生修复；无新服务、端口、依赖、公开符号或文件 inventory；既有架构清单与生成索引保持不变。
- 根因：生产图已选 optional peer 实体，缺少根 node_modules 别名，固定 DSH 从虚拟 Profile anchor 搜索不能找到 peer。
- 修复：复用别名过滤与冲突验证，扫描根与 pnpm 私有 hoist；只保留既有、选中的内部目标相对别名。
- RED：固定 Node createRequire(anchor).resolve.paths 搜索原源码成功，派生树退出 7；2 failed / 44 deselected，pytest exit 1；工具计时 0.51932925 秒。
- GREEN 初次：46 passed / exit 0；工具计时 2.254989583 秒（含后续 rg 的合计，非单门耗时）。
- GREEN 安全用例完整：58 passed / exit 0；工具计时 2.660689917 秒，pytest 自报 2.42 秒。
- 验证解释器：`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`；PYTHONPATH 为当前隔离 worktree。
- Node：`/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`，置于 PATH 首位。
- RED/GREEN 命令：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_staged_runtime.py -k virtual_alias_anchor -q`（RED）；同一文件 `-q`（GREEN）。
- 保护：未改变 loader 验证、固定 DSH、Dockerfile、锁、CLI 或运行时状态。主任务旧报告与所有真实 Native/Docker side effects 不属本补丁。
- 后续本地门与 review package 记录见本报告补充；格式工具、真实镜像和 CI 不可由源码单测代替。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Only preserve existing root aliases to selected production packages in the existing staged image; no service, dependency, public API, data format or lifecycle change.","diagrams":[]} -->

## 本地验证补充

证据目录：`/private/tmp/rwb-root-alias-checks.MC930G/`。命令 PATH 固定上述 Node；Python 为上述已有解释器，无安装。

- 初始完整五路径 plan：L4，exit 0，工具时长不足以可信测量，耗时 unknown；`plan.json`。
- 初始 Constraints：exit 1，`constraints.log`；要求 dual-runtime 的三个其余模块文档和结构 marker 同步。保留失败，`plan-validation-failure.json` 由同一完整 changed set 加 `--signal validation_failure` 生成，exit 0，耗时 unknown。
- `node scripts/check_documentation_governance.mjs --project .`：exit 0，工具命令计时 0.291633542 秒，`governance.log`。
- `python scripts/generate_py_file_index.py --check`：exit 0，总时长 unknown（异步）；`index.log`。
- `node --test tests/javascript/research_web_architecture.test.mjs`：exit 0，总时长见日志或 unknown（异步）；`architecture.log`。
- `node --test tests/javascript/docker_runtime_contract.test.mjs`：exit 0，工具命令计时 0.300372084 秒；`docker-contract.log`。
- `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs`：91 PASS，exit 0，Node 自报 3142.873041 ms；`full-governance.log`。
- `python -m pytest --confcutdir=tests/research_web tests/research_web/test_staged_runtime.py tests/research_web/test_container_supervisor.py tests/research_web/test_runtime_launch.py tests/research_web/test_docker_packaging.py tests/research_web/test_doc_sync.py -q`：199 PASS，exit 0，pytest 自报 27.82 秒为五模块合计，不作为各 gate 时长；`python-closure.log`。
- `git diff --check`：exit 0，耗时 unknown。
- README review：公开入口、安装前提和部署拓扑均无变化；已有 README 不需改。Docker staging 不属于 README receipt source prefix，未改变现有 receipt。
- formatter/lint/mypy：NOT_RUN，未安装工具，不安装；真实修复镜像与 CI：NOT_RUN，由主任务负责。初始 plan 的 project-constraints/research-web-checks/research-web-docker 为 Linux CI 门，不能计为 macOS 证明，mergeReady=false、releaseReady=false。
- 最终八路径 `plan-final.json`：带 validation_failure，L4→L4，无新增本地 gate，保留 unknown_impact_boundary；exit 0、耗时 unknown。
- 最终完整八路径 Constraints：exit 0、violations=[]，工具计时 0.074103292 秒，`constraints-final.log`。最终文档治理 exit 0、工具计时 0.067226958 秒，`governance-final.log`。
- 单独架构测试 63 PASS，Node 自报 3143.636292 ms；Docker 静态合同 13 PASS，Node 自报 249.425333 ms（后者与命令工具计时为不同计时源）。
- 受管 manifest 的 11 个文件逐项 SHA-256 匹配：exit 0，耗时 unknown。最终报告新增只记录以上结果，未改变源码/接口/测试。
- 本补丁机器 receipt 汇总由主任务维护；本报告不是完成物理 Docker 或跨平台验收的 receipt。
