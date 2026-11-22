# 按实际结构变化选择模块文档

宿主：Mac mini／macOS arm64。任务：既有离线文档检查器的局部修复，不改产品运行时、API、依赖或部署。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"本次仅按既有结构评审决定区分模块文档的适用范围，不新增评审字段、映射结构、服务、API或图形证据机制。已有有效unchanged说明且更新对应模块文档时不再要求机械修改全部映射文档；结构变化继续使用原全部文档与受影响图检查。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"本次沿既有Checks范围选择增加文档检查器的明确窄选分支，仅调整原步骤内的测试选择及无Python结果时的证据条件。作业、runner、依赖、权限、时限、原retention和完整分支、Project Constraints及Mac Bootstrap均保持，不新增工作流、运行节点或评审机制。","diagrams":[]} -->

原检查器在读取结构决定前，无条件要求命中模块的所有映射文档都发生修改，因此已说明结构未变并更新实际模块合同的小修仍被无关文档挡住。现复用原 `architecture-review`：有效 `unchanged` 决定加至少一份该模块文档即可满足文档更新要求；缺结构说明、没有任何模块文档、`changed` 结构的完整文档及受影响图要求保持。源码映射、API 清单、图形证据、README 和其他检查保持。

验证与复用：

- 三项新回归在原实现精确 RED 为 1 FAIL／2 PASS；修后与五项直接相邻回归合计 **8/8 PASS**、0 FAIL、0 SKIP，约0.49秒。覆盖一份相关文档足够、没有文档仍拒、结构变化仍需完整图文，以及原模块归属和有效结构说明检查。
- 独立 TypeScript／JavaScript 审查 **APPROVE，0 P1/P2**，复核八项回归及语法／diff 检查通过；审查原件为任务 Scratch 中的 `primary-settings-fix/proportional-doc-review.json`。
- 本次独立交付基线为 `45b02c0600f3bb27b4d14be2d2376dd9b9251258`。先核新旧基线的两个原文件相同，再转入已审代码；检查器与测试分别保持 Git blob `b6c2497d566a019ac02fadbf7e07688d0c88eed4`、`9f4c234754a87732139999ba7b218696cbfede2c`。两份文档仅局部更新相应规则，未整份覆盖新主线文档。

源码及回归字节相同，因此复用上述有效结果，不再次运行381／188项或八项回归。最终候选的文档治理、项目约束及必要 CI 由独立交付接续，当前未标为通过；本次不包含 UI 入口、操作员或其他任务改动。

现有 Checks 对这两个检查器文件仍会运行无关的长时 Web 回归。现沿原 `Choose contract test scope` 增加 `architecture_only`：必须命中检查器或对应 JS 测试，其余仅允许相关 Markdown、该工作流及直接范围测试；产品源码、没有有效差异、fetch／diff 失败均保持完整范围。窄选时明确不执行 Python 测试，只运行原架构检查器 JS 模块，编辑引擎及不存在的 pytest 证据处理不执行；原 retention-only 和完整分支不变，未新增作业、依赖、runner、权限或时限，Project Constraints 和 Mac Bootstrap 保持。

CI 范围新增两项回归在原工作流实际 **2 FAIL**；修后与六项直接相邻检查合计 **8/8 PASS**、0 FAIL、0 SKIP，约0.52秒。实际执行工作流内嵌 Python 的六种差异场景，并用受限命令替身执行原 Bash 分支，确认只选择 owner Node 命令、不进入旧 SHA fetch／Python 批次；这不冒充远端 owner 测试或完整 Python 已执行。Psych YAML 解析、除六个指定 run／if 字段外的工作流结构深等比较、六段 Bash 语法、两段 Python AST、JS 语法和 diff 检查均通过。先前0 P1/P2独评仅覆盖检查器与其回归；新增CI范围由Root另行独立复核，正式候选CI仍待运行。

最终受管候选的两个直接 Node 模块实际执行为182项：181项通过、1项旧证据上传条件字符串断言未同步。将该断言更新为明确包含 architecture_only 排除和原 stage-safe-evidence success 条件后，仅复跑该失败用例并通过；未重跑其余181项。文档治理、Python索引和8文件项目约束检查通过。既有源码与工作流四个已审blob保持，测试期望更新另由最终评审确认。
