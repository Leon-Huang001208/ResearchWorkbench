# Agent Workflow Foundation 测试报告

## 范围

本报告验证三个可复用流程技能的文件结构、元数据与压力场景行为：

- `ui-iterate`
- `bugfix-minimal`
- `ship-check`

验证仅演练流程；没有执行产品改动、真实故障修复、产品测试或浏览器操作。

## RED / GREEN 压力场景

### UI：`ui-iterate`

- 场景：`Refine the native Button states in app/web without changing public APIs; prove hover, disabled, loading, and danger behavior.`
- RED（无项目技能）：基线代理只能给出通用状态建议，明确无法得知现有 Button 约定、设计 token、测试命令、视觉基线、目标浏览器和 danger 语义；因此不能形成与仓库对齐的最小改动或可复现浏览器证据。
- GREEN（仅提供最终 `ui-iterate/SKILL.md`）：代理先要求阅读项目与前端规则、冻结公开 API/selector 边界，并列出 default、hover、disabled、loading、danger 及组合优先级；限定最小改动，要求实际测试与目标浏览器证据，且将任何未运行状态标为未验证。
- 结论：通过。技能关闭了“遗漏状态或浏览器证据”的缺口；演练本身没有验证真实 Button 行为。

### Bug：`bugfix-minimal`

- 场景：`A focused report-project request returns the wrong template after a recent change. Find the smallest root cause and fix it without refactoring unrelated code.`
- RED（无项目技能）：基线代理实际先提出最小复现、最窄根因和回归测试，没有出现预期的“大重构或未先复现”缺口。可观察缺口是没有项目级失败命令、最近变更证据或实际测试输出，故其建议不能证明修复已经完成。
- GREEN（仅提供最终 `bugfix-minimal/SKILL.md`）：代理明确拒绝在 RED 复现完成前进入 GREEN；它要求在编辑前确认最近回归测试因该故障失败，沿请求解析到模板回退追踪最窄根因，只改根因与必要测试，随后以目标和相邻测试的实际输出作为完成条件。
- 结论：通过。技能把“未证明的建议”收紧为先复现、最窄修复和证据分层；演练没有找到或修复真实模板问题。

### Handoff：`ship-check`

- 场景：`Prepare a task that changed a route, test, and documentation for review. State only verified results.`
- RED（无项目技能）：基线代理不虚称结果，但缺少规定的证据格式、必跑检查选择规则、文档一致性标准和未验证项的阻断准则。
- GREEN（仅提供最终 `ship-check/SKILL.md`）：代理建立“源变更—测试—文档—证据”映射，要求枚举完整变更、逐字记录命令和结果、单列跳过项/平台限制；无实际输出时，将交付明确为阻断而非完成。
- 结论：通过。技能关闭了“虚称验证或遗漏风险”的交接缺口；演练没有审查真实路由、测试或文档变更。

## 文件与静态验证

已执行以下结构检查；在文件暂存后，另对暂存 diff 执行空白检查：

```bash
for skill in ui-iterate bugfix-minimal ship-check; do
  test -f ".agents/skills/$skill/SKILL.md"
  test -f ".agents/skills/$skill/README.md"
  rg -q "^name: $skill$" ".agents/skills/$skill/SKILL.md"
  rg -q '^description: Use when ' ".agents/skills/$skill/SKILL.md"
  rg -q "SKILL.md" ".agents/skills/$skill/README.md"
done
git diff --check -- .agents/skills .ai/reports/test_report_agent_workflow_foundation.md
git diff --cached --check -- .agents/skills .ai/reports/test_report_agent_workflow_foundation.md
```

结果：通过（两项 diff 空白检查及结构检查均退出码 `0`，检查步骤均无输出）。三项技能均存在 `SKILL.md` 与 `README.md`；`name` 与目录名匹配，三条 `description` 均以 `Use when ` 开始，README 均链接 `SKILL.md`；暂存的目标 diff 无空白错误。

## 限制

- 压力测试代理均为纯文本流程演练，未触及产品源码，也没有宣称真实测试、浏览器或平台验证已经通过。
- 本次只新增技能与报告；桌面端、Windows 或产品行为没有发生改动，也没有相关平台验证需求。
