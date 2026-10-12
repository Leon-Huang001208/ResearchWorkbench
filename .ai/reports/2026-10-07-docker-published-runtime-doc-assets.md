# Docker 发布运行资产 doc/docs 修复

- 宿主 macOS；任务 Web 打包功能修复；本平台本地源码验收，不执行 Docker、安装、服务或远端动作。
- 基线 `99c4365ad39c6974eb9125aa94dd2ede23e0ff69`。主任务的未跟踪验收/plan/receipt 不属此提交。
- 根因：第三方包已发布 `dist/doc` 运行实现，被 EXCLUDED 任意层级目录剪枝和最终过滤双重删除。
- 修复：共用 `_excluded` 判断，只有明确无歧义发布目录的子树内允许 doc/docs；包顶层 doc/docs 和硬开发目录仍排除。第三方 tarball 其他资产选择合同不变。
- metadata 含 glob/negative/越界/绝对/非字符串/根目录时不建立例外；不引入新解释器/依赖/扫描器或 yaml 白名单。
- RED 命令：固定 Node PATH、当前 PYTHONPATH、批准的 Python，`python -m pytest --confcutdir=tests/research_web tests/research_web/test_staged_runtime.py -k declared_runtime_document -q`。原树 Node require 成功，派生树 MODULE_NOT_FOUND；运行资产越界负例因被错误遗漏而未拒绝。4 failed、58 deselected，exit 1，pytest 0.42 秒，工具计时 0.60412175 秒；`red.log`。
- 初次 GREEN：同环境整个 staged-runtime 文件 `-q`，62 PASS，exit 0，pytest 1.76 秒、工具计时 1.895050875 秒；`green.log`。
- 证据目录 `/private/tmp/rwb-published-doc-checks.x5Sd0s/`；Node `/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`；Python `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`。
- structure unchanged；既有根 alias 安全负例全部保留；没有源文件增删/公开符号变化，架构 inventory 不变。
- 真实新镜像、生命周期、CI、formatter/lint/mypy 均 NOT_RUN；既往镜像构建不证明本补丁或生命周期。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Preserve explicitly published runtime doc assets within the existing staged package selection; no services, public APIs, dependencies, data formats or lifecycle changes.","diagrams":[]} -->

## 最终本地门

全部八路径 planner 加 `--signal validation_failure`：exit 0，L4→L4，工具计时 0.033692667 秒；保留 unknown_impact_boundary。`plan.json` 的三个 Linux CI gate 均 NOT_RUN，不计作 macOS 证据；mergeReady=false、releaseReady=false。主任务负责总 plan/receipt。

以下 Node/Python 命令使用上方固定解释器和 Node。异步命令没有完整工具墙钟时长时标 unknown，Node/pytest 自报时长按其实际合计使用。

| 实际命令 | 结果 | 时长来源 | 证据 |
| --- | --- | --- | --- |
| `node scripts/check_documentation_governance.mjs --project .` | exit 0 | 工具 0.233717584 s | governance.log |
| `python scripts/generate_py_file_index.py --check` | exit 0，现有索引一致 | unknown | index.log |
| `node --test tests/javascript/research_web_architecture.test.mjs` | 63 PASS / exit 0 | Node 3033.229417 ms | architecture.log |
| `node --test tests/javascript/docker_runtime_contract.test.mjs` | 13 PASS / exit 0 | Node 218.273458 ms，工具 0.264151542 s | docker-contract.log |
| `node .agents/project-constraints.mjs --project .` 加完整八路径参数 | exit 0，violations=[] | 工具 0.238512833 s | constraints.log |
| `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs` | 91 PASS / exit 0 | Node 3032.14075 ms 为合计，非单门 | full-governance.log |
| `python -m pytest --confcutdir=tests/research_web tests/research_web/test_staged_runtime.py tests/research_web/test_container_supervisor.py tests/research_web/test_runtime_launch.py tests/research_web/test_docker_packaging.py tests/research_web/test_doc_sync.py -q` | 211 PASS / exit 0 | pytest 27.22 s 为五模块合计，非单门 | python-closure.log |
| `python -m pytest --confcutdir=tests/research_web tests/research_web/test_staged_runtime.py -q` | 最终 71 PASS / exit 0 | pytest 1.53 s，工具 1.674547875 s | green-final.log |
| 完整八路径 Constraints 再核对 | exit 0 | 工具 0.018693875 s | constraints-final.log |
| 受管 manifest 11 文件逐项 SHA-256 | exit 0 | unknown | 工具输出 |
| `git diff --check` | exit 0 | unknown | 工具输出 |

211 项闭包之后补齐“dist 加根目录声明”保守拒绝，最终 staged 71 项含该新增负例；相关其他模块未改，不把旧 211 计成 212。前轮 TypeScript 普通/scoped root alias 及所有安全负例保留。顶层 doc/docs、任意层级 tests/fixtures/.git/.github/bench/cache/coverage、README、test suffix 与未选 dev 包有断言。实际 Node 原树和派生树均需成功加载运行代码，runtime JSON 资产越界失败关闭。

README 公开入口和部署结构未改变，复核 unchanged；现有 README receipt 不属 Docker staging source prefix。既有 Python 文件索引和架构 inventory 无文件/公开符号增删，检查通过，不制造索引 diff。

格式/类型工具未安装，因此 ruff/black/isort/mypy NOT_RUN，不安装。真实 Docker 重建/启动/Doctor、模型旅程和跨模式持久性须由主任务继续实测；本补丁只有本地源码修复与可审查提交证据。
