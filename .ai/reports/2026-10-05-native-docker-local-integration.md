# Native/Docker 本地集成记录（2026-10-05）

## 边界与来源

- App 受管工作树：`/Users/leon/.codex/worktrees/dual-runtime-integration/ResearchWorkbench`。
- 本地分支：`codex/native-docker-local-integration-20261005`。
- 合并父来源：feature `5788e46956eb25649dd2832ddd9b84ce54cef8a4` 与 master `d17459edeff5696d2a2641c4072c2d08e9ae84d0`；共同 base `4d6a4eff`。
- 仅解决已授权本地集成；原 feature 工作树、旧 Task 13 计划/回执/报告、全局 Harness、插件、受管共享运行时与 manifest 均未修改。
- 没有启动/停止用户服务、Docker build、依赖安装、push、PR、dispatch、部署或清理。临时测试进程和套接字由原测试夹具管理。
- 此报告不是 managed delivery receipt，也不声明完整 Goal 或远端验收完成。

## 冲突与语义集成

1. `service_manager.py` 保留 master 的生命周期排他锁、PID/精确 argv/启动时间/监听归属、恢复、活动研究保护与完整 Web ready。共享 `ProcessSpec` 和隔离 `runtime_state_root` 来自 feature；overlay 签名继续规范化系统 `/var` 路径。持久 PID 记录仍为 version 1；诊断投影为 schema 2，两者不得混淆。
2. Doctor 保留 master 的 `installation_ok/product_ready/model_ready` 和服务事实链，并添加 feature 的 `runtime_mode=native`。CLI `status --json` 输出安全 schema 2 服务事实，不输出日志路径；普通状态展示保留主线语义。
3. stdlib bootstrap 先选 Native/Docker，再验证 Native 环境归属及 CLI 可导入性。Docker 不受缺失/损坏 Native `.venv` 阻断；Native 坏环境只允许 master 的受限帮助/诊断，并增加安全 `status --json`。工作树公共 venv 按其所属根验证；不会借全局产品依赖绕过安装标记。
4. Windows launcher 保留 master 的公共 worktree 环境查找、精确错误分类与后备诊断，增加前置 Host Python 模式路由。这里只做接口与源码测试，未宣称原生 Windows 验收。
5. Native 模式切换桥不再自行解析旧 PID 和命令行子串，改为调用 master 服务事实链；stop 使用受锁保护的 manager.stop。日志读取也复用精确 PID 身份，并在输出前重新绑定状态内容和 inode。无有效 Native 环境但无 PID 记录且端口确实关闭时，只读 status 可证明未运行，允许 Docker 安装/启动继续；存在未知记录或端口时仍拒绝。
6. 容器完整页面探测通过 `ContainerHealth._text_request` 复用已有总 deadline；保留 authenticated DSH 和首页/静态模块检查，不依赖 Native PID 账本。实进程 fixture 增加主线要求的 Content-Type、health_check_passed、首页与模块响应。
7. setup 保留 Docker 事务和 master 环境标记校验；Node 严格版本解析与 CJPY 固定值消费同一 runtime JSON 事实源。
8. 自动合并的 verification policy 混入 v2 `execution` 项导致 v3 planner 拒绝。仅将新增 Docker catalogs/rules 对齐已合入的 v3 lane/gate/platforms/realMachine 结构；完整 L4、Docker Linux CI、Native macOS 及未知路径 fail-closed 均保留，未改框架算法或 manifest。
9. DEVELOPMENT_MAP、框架/协调器/Tabbit 文档保留两侧互补边界；README review 为 updated；Python 索引按最终源重新生成。架构 inventory 的自动合并新增源与测试通过现有校验。

## RED → GREEN 与失败保留

- 新增坏 Native 环境与 PID 重用桥接两项回归：初始 2 failed（0.30s），接入可信接口后 2 passed（3.73s）。初始受限执行因工作树日志写入权限失败，随后窄范围提权运行；权限错误不当作代码 RED。
- 容器总时限接口回归：1 failed（0.26s），旧继承路径绕过 `_request`；增加最小 adapter 后纳入最终通过闭包。
- 日志身份反例（PID reuse、argv substring）：2 failed（0.54s）；复用主线身份后日志闭包 21 passed（1.12s），见 `logs/integration-native-logs.log`。
- `logs/integration-core-first.log`：13 failed / 628 passed / 19.13s，包含旧 fixture 与真实 signature 接口差异。
- `logs/integration-core-second.log`：2 failed / 735 passed / 56.71s，剩余为旧 fake Git 环境假设及容器健康 fixture 不完整。
- `logs/integration-core-third.log`：10 failed / 862 passed / 98.33s；扩大 Docker 控制闭包暴露固定 18088/13081 被本机已有服务占用。改为动态临时端口，真实 socket 冲突断言保留，未停止现有服务。
- `logs/integration-docker-bridge.log`：197 passed / 15.14s。
- JS v3 初跑 75 passed / 1 failed，唯一差异是 Docker gate 的旧 external/generic 预期；改为 ci/merge/linux 后全部通过。

## 最终已执行验证

所有 pytest 使用原 feature 环境的解释器，但 `cwd` 与 `PYTHONPATH=$PWD` 指向本集成工作树；未加载原 feature 源作为测试目标。

```bash
PYTHONPATH=$PWD /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest \
  tests/research_web/test_service_manager.py tests/research_web/test_setup_web.py \
  tests/research_web/test_web_bootstrap.py tests/research_web/test_web_contract.py \
  tests/research_web/test_runtime_mode.py tests/research_web/test_cli_lazy.py \
  tests/research_web/test_container_supervisor.py tests/research_web/test_docker_runtime.py \
  tests/research_web/test_runtime_contract.py tests/research_web/test_runtime_launch.py \
  tests/research_web/test_staged_runtime.py tests/research_web/test_docker_packaging.py \
  --confcutdir=tests/research_web -q --tb=short
```

- **1062 passed / 77.00s**，`logs/integration-final-python.log`。
- `node --test tests/javascript/verification_policy.test.mjs tests/javascript/incremental_validation_skill.test.mjs tests/javascript/docker_runtime_contract.test.mjs`：**86 passed / 5.480s**，原始日志 `/private/tmp/rwb-policy-tests-green.log`。
- `node --test tests/javascript/research_web_architecture.test.mjs`：**63 passed / 2.806s**，`logs/integration-architecture.log`。
- `node scripts/check_documentation_governance.mjs --project .`：最终537 files，0 violations，`logs/integration-documentation-final.log`，包含本报告。
- `python scripts/generate_py_file_index.py`：重新生成成功；随后 `--check` 一致，合并 marker 消失，`git diff --check` 通过。
- AST 定义审计：service_manager 测试 182 个顶层定义，无重复；feature 新增 18 与 master 新增 119 全部保留。setup 测试 54 定义，无重复；feature 新增 15 与 master 新增 8 全部保留。完全同内容的品牌中性契约重复定义只保留一份，断言未削弱。
- `node scripts/plan_verification.mjs --project . --changed-file Dockerfile`：真实 v3 planner 返回 L4/full-delivery 与 generic/linux，无 desktop 门。此单路径诊断不冒充完整 changed-set 验收计划。

## 未验收与交接

- 完整 changed-set v3 plan/receipt、独立 review、Project Constraints 全 changed-set 检查与其他必需闭包由主代理继续。
- 当前指定测试环境没有 ruff、black、isort、mypy，PATH 也未找到这些工具；未安装，未宣称格式/类型检查通过。
- 未运行 Docker 镜像构建或 Native 真服务切换、GitHub macos-14 干净安装、条件 Docker 多架构 CI、Windows Native/真实 Windows 或 Docker Desktop 平台烟测。
- 批量冲突脚本、整文件测试重建及简化 Windows launcher 曾被自动审批拒绝；未绕过。最终采用逐处显式补丁、保留测试定义与完整 Windows 后备路径，并用真实回归验证。
