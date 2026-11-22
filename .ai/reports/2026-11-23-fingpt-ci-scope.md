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
日志为 `logs/fingpt-ci-scope-{red,green}.txt` 及 `logs/fingpt-ci-scope-actual.json`；远端新候选 CI 尚未运行。

Product-Progress: not-required — 本次只调整已有持续集成执行范围，不改变产品入口、业务行为或已完成状态。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"仅在既有Checks范围选择与分区入口登记本批相关合同，没有新增运行服务、接口或交付节点。","diagrams":[]} -->
