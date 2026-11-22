# FinGPT 来源报告 CI 范围修正

本轮为 macOS 上的 CI 配置修复，不执行 Linux 产品验收、生产操作或模型调用。
PR #314 的 `86c71603531419cae4e5850ca7333741ab22197b` 对 `20d77196a3195ea1effe93b643f9a8c3f79ce990`
进入原完整 Research Web 矩阵；Checks `45064106251` 在45分钟上限取消。取消后的 worker 日志仍在变化，
原 stager 拒绝其身份并未发布产物，无法据此断言具体失败用例。旧记录不改判为通过。

修正只复用既有 scope selector 和分区入口：Fed／QA 明确入口作为必要条件，其余产品、测试及登记图文路径
使用本批精确名单。真实 base/head 无法取得、未知路径、混入其他产品时均回退原完整范围。
测试冻结本次实际 PR 差异作为回归输入，不要求浅检出的 CI 拥有任意历史提交。

选中的 Python 范围覆盖36个完整模块：共享 Host/API、DataHub、Discovery／RSS、原 Bot／Automation、
FinGPT worker／格式／费用准入、来源读取与质量、报告 SDK／渲染／工作流、档案原文、原件方法边界，
以及两个维护模块与资源登记。另保留原 Bot Native Skill 准入单例及 FinGPT legacy、分区执行器、
安全证据单元测试。未修改断言或运行结果。未知范围继续执行完整矩阵。

原完整 Node 和编辑引擎步骤、固定 DSH、三个历史维护源对象、证据阶段、作业／runner／并发、
45分钟上限、Project Constraints 和同候选 Mac 干净安装保持；无新依赖、工作流或平台 dispatch。

相关新增两项测试先实际失败：scope 字段不存在、原全矩阵未包含所需来源合同。
测试脚本最初有一处 `g2b` 标识替换的数字匹配错误，先更正测试脚本后才记录上述 RED。
固定 Node 24 的完整 `actions_quota_governance.test.mjs` 为31 passed、零失败（2.028s），
包含本批真实差异、逐项产品路径、未知与取 diff 失败回退，以及原 pack／upgrade／G2B／retention
选择回归。执行分支使用真实工作流 shell 与本机记录 stub，核对36个完整模块、准入单例、三个单元模块、
三历史对象及完整 Node 分支均保留。另将本工作树对 `20d77196` 的实际79项差异交给实际 selector，
只得到 `fingpt_source_only=true`，其余 scope 均为 false。未运行 pytest，原任务仅有另一个取消修复批次。
日志为 `logs/fingpt-ci-scope-{red,green}.txt` 及 `logs/fingpt-ci-scope-actual.json`。

首次返修的工作流在 `45070244792` 启动时被平台拒绝，未创建 job：Python contracts 的解码 `run`
为23,332字符，超过平台21,000上限。本机31项检查与当时评审漏掉此平台限制，不能当作工作流有效的证据。
本次将该 FinGPT 分支的固定命令逐字提取为 `scripts/run_fingpt_source_ci.sh`，只保留原选择和固定调用。
脚本不接受选例参数，使用原环境、三个对象、插件、私有根和完整测试名单，错误通过 `set -euo pipefail` 传播。

新增两项回归先 RED（超长23,332和固定脚本缺失），修后完整 Actions quota 模块33 passed、零失败（最终2.003s）。
使用共享环境中已安装的 PyYAML 另行解码核对所有六个 step：scope 15,585、依赖安装5,667、Python contracts
20,387、JavaScript contracts 1,704、编辑引擎130、证据阶段148字符，均不超过21,000。
机械比较确认脚本去除 shebang／`set -euo pipefail` 头后与 `cd13116f` 的原分支命令逐字一致；
将固定调用换回原分支、移除新脚本名单和两个精确事件触发路径后，整个 workflow 与该基线逐字一致。
两个事件路径仅保证以后单独修改该脚本也进入既有 Checks job，不扩大 Mac 或其它平台触发。
回归还检查展开的两个
Python命令、36模块顺序、Bot准入、三个unit、Git完整参数／对象、插件和根路径。
日志为 `logs/fingpt-ci-expression-{red,green}.txt`、`logs/fingpt-ci-expression-lengths.json`。
本次未运行 pytest、远端发布、模型或生产操作；下一候选仍须由原任务正常返修并取得自己的CI结果。

随后 `45075094329` 的 Web 5365 case 全通过（45 skip），三个原 unit 模块在 collection 因缺少
SQLAlchemy 中止。`test_fingpt_legacy_cutover.py` 经 `fingpt.py` 导入 `runtime_workflows.py:14`，
需要既有 `requirements/research-test.in` 已声明的 `sqlalchemy>=2,<3`；原 CI 仅消费 Web 锁及 `dev`，
遗漏该获准的共享测试声明，不能将 Web 通过记作整个 Checks 通过。

本次只在原 test-tools 提取处合并该声明文件的非空、非整行注释 spec，复用原正则并对相同 spec 去重。
未修改任何 requirements、生产锁或业务代码。实际提取的 dev 九项加 shared test 八项合并为十项，
相对原 CI 唯一增加项是来自该文件的 SQLAlchemy；Web 锁字节和全部 constraints 逐字保持。
原 legacy HTTP 断言、根包 `--no-deps`、SDK/runtime pins、scope、作业与时限保持。

新增两项检查先 RED，分别命中 SQLAlchemy 被遗漏、缺失声明仍能成功；修后固定 Node 24 完整模块
35 passed、零失败（2.023s），覆盖重复 spec、缺失／空／非法文件拒绝、Web 原哈希和约束、根包无依赖安装。
共享环境已装 PyYAML 核对六个解码 `run` 长度分别为15,585、5,925、20,387、1,704、130、148，
均在21,000内；旧安装以外的所有 step 与 job 配置和基线 `7f23b58c` 相同。
证据为 `logs/fingpt-ci-test-closure-{red,green}.txt` 与 `logs/fingpt-ci-test-closure-proof.json`。
本子任务未运行 pytest、安装包、远端操作、模型或生产操作；三个 unit 的后续真实验证由主任务接续。

Product-Progress: not-required — 本次只调整已有持续集成执行范围，不改变产品入口、业务行为或已完成状态。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"复用既有Checks范围和分区入口，按已有test-only声明补齐工具闭包，没有新增运行服务、接口或交付节点。","diagrams":[]} -->
