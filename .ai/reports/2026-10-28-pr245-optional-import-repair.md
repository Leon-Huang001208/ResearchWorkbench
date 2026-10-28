# PR245 repair2：Web 测试环境与根包历史依赖隔离

宿主 macOS；任务为 Web CI 安装修复，基线 `bff0600e9a474b09b8d73d5966c07488416c5260`。
只修改原 Checks 安装步骤、近处治理回归与文档，不修改产品导入策略、运行指纹、
`requirements/web.lock`、pack 投影、测试列表、job、runner、timeout 或其他平台门。

## 原失败与最小复现

完整原件位于 controller `logs/pr245-bff-ci/checks-40659261189.log`，原 job
`122717872128`：197 failed／7088 passed／101 skipped／373 errors，133 subtests，834.52秒。
七个冻结分发的哈希安装与实装 metadata 均已通过，不能再归因为 rpds/idna 版本漂移。
原 editable `.[dev]` 解析根 pyproject 历史依赖：
langgraph→langchain-core→jsonpatch→jsonpointer 3.6。

569处直接失败具有相同链：真实 `jsonschema._format` 保留未锁模块引用，
`_references` 拒绝 `unbound referenced dependency module`，继而
`pack_import_policy_unverified`→`pack_runtime_unverified`。另一浏览器后端
subprocess 的断言失败亦回到同一 Catalog 初始化链；没有发现另一独立产品根因。

未安装包、未联网，使用已有 release Python 的 fresh `-I -B` 实测：

- clean 环境真实 `runtime_identity()` 返回 `research_pack_runtime_v3`。
- 显式 synthetic `jsonpointer.py` 只提供该 optional 所需类，真实 jsonschema
  自行导入它；exception trace 精确记录 module=`jsonschema._format`、
  value=`jsonpointer` 和 synthetic 文件路径，得到与 CI 同一拒绝链。
- 同一 clean identity 在 fresh Native helper 中安装原 guard 后真实导入 jsonschema 成功。
- 仅使 synthetic optional 可发现而尚未导入，Native 在安装 guard 时就以
  `unbound optional dependency available` 拒绝，`jsonpointer_loaded=false`。

这两种拒绝都是原合同的正确边界。不能允许 Host 未锁引用、扩大 absent、伪造身份或
放松 Native 来容忍混入环境；clean Web 通过不认证用户额外安装 SDK 后兼容。
原件和反例见 controller `logs/pr245-optional-import-repair/` 的
`reproduce.py`、`clean.log`、`synthetic-jsonpointer.log`、`native-clean.log`、
`native-optional-present.log`；没有把 synthetic 声称为真实已安装 jsonpointer 3.6。

## 最小更改

复用 `scripts/setup_web.py` 已有 Web 锁／根分发 `--no-deps` 安装边界，以及 Mac
Bootstrap 从 pyproject dev 声明提取工具的既有做法。原锁准备仍实际校验 whole SHA、
七项版本、三个 renderer/workbook 条目和哈希矩阵；生成的哈希安装文件改为未变全锁原字节，
纯 constraints 覆盖全锁并保留平台 marker。dev 清单只从现有声明读取和校验，
根项目 editable 使用 `--no-deps --no-build-isolation`，不解析其历史运行栈。

原七项 metadata 核验之后，新增同一步实际 Host runtime_identity 和 fresh `-I` Native
helper／jsonschema 导入／idn-hostname 校验，任一失败先终止，随后才运行原完整 Python
闭包。准备、metadata、Host／Native 准入均记录明确失败日志。Native 子进程错误原文
进入安装日志，不以只有版本相同认证可执行闭包。

## 验证与限制

`RWB_TEST_PYTHON` 为现有 release Python；固定 Node24.19，显式固定 DSH 两个环境变量。
所有临时根为 controller 日志下不透明 owned 目录，含 task/uid/pid/device/inode/argv/
candidate；Node TMPDIR 在外部 owned 子目录。每组执行后归档、独立实际恢复逐文件 SHA
相等、复查 inode/lsof 后仅删除本组临时根。没有访问旧50根、常驻、Docker、秘密或外盘。

首次 `node --test tests/javascript/actions_quota_governance.test.mjs`：23 passed、0skip，
1.851秒。真实执行原六种锁拒绝、dev解析六种正反例、clean与Host/Native optional
污染三种准入，以及七项逐一 metadata 漂移；完整日志/恢复回执为
`logs/pr245-optional-import-repair/focused.{log,json}`。

最终按真实执行环境拆开：stdlib-only 锁／dev／metadata治理留在原文件，真实 runtime
准入三矩阵移到 `research_web_ci_admission.test.mjs`，由既有 Checks JS 通配符执行。
Project Constraints 不因此获得隐式产品依赖或安装步骤。两文件联跑23 passed、0skip，
1.374秒；`final-split.{log,json}`。治理单独用同解释器 `-I -S` 标准库包装器执行，
不加载任何site-packages，22 passed、0skip；`portable-stdlib.{log,json}`。

Project Constraints、文档治理、研究架构和 git diff --check 全部通过；YAML解析、原shell
全部 `bash -n` 及三段实际Python heredoc AST解析通过，见 `integrity-final.json`。
初次完整性曾明确提示缺少verification-workflow两份模块文档及结构决定，保留原失败
`integrity.json` 后补齐文档／unchanged结构依据，没有放宽规则或修改checker。
根 README 无新增用户功能、入口或配置，结构／模型／运行策略保持，故无需改动。

完整 Python 闭包、独立
SPEC/QUALITY、后继原三CI与Mac干净安装由 controller 接续，当前未执行层级保持 NOT_RUN。
没有在本机 pip 安装或模拟新CI安装成功；原 bff Mac 七项225.022秒通过只是旧候选事实。
没有远端操作、重跑旧run、dispatch、合并、常驻部署或模型调用。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只修原Checks步骤的Web锁与测试工具安装边界，复用既有产品安装合同并增加真实导入前置核验；无新增workflow/job/runner/timeout，原三门与各平台归属保持，既有验收流程图仍准确。","diagrams":[]} -->
