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

**原始输出摘录 / 执行上下文：** 输入为上列场景；基线代理被禁止读取项目技能，GREEN 代理只读取最终 `ui-iterate/SKILL.md`，二者均为纯文本且未运行命令。基线关键句为“无法准确获知项目既有的 Button 约定、设计 token、测试命令、视觉基线、目标浏览器与‘danger’语义细节”；GREEN 关键句为“最终优先级……必须由当前组件和测试契约确认；本演练不臆定具体实现”。该输入可用同一场景文本和相同只读限制复现。

### Bug：`bugfix-minimal`

- 场景：`A focused report-project request returns the wrong template after a recent change. Find the smallest root cause and fix it without refactoring unrelated code.`
- RED（无项目技能）：基线代理实际先提出最小复现、最窄根因和回归测试，没有出现预期的“大重构或未先复现”缺口。可观察缺口是没有项目级失败命令、最近变更证据或实际测试输出，故其建议不能证明修复已经完成。
- GREEN（仅提供最终 `bugfix-minimal/SKILL.md`）：代理明确拒绝在 RED 复现完成前进入 GREEN；它要求在编辑前确认最近回归测试因该故障失败，沿请求解析到模板回退追踪最窄根因，只改根因与必要测试，随后以目标和相邻测试的实际输出作为完成条件。
- 结论：基线未暴露预期缺口；GREEN 仅证明技能显式强制 RED 门槛，未证明相对于基线的改善。演练没有找到或修复真实模板问题。

**原始输出摘录 / 执行上下文：** 输入为上列模板选择回归场景；基线代理未读取项目技能，GREEN 代理只读取最终 `bugfix-minimal/SKILL.md`，均未执行命令或修改文件。基线关键句为“我会先把‘focused report-project’请求、期望模板与实际模板固化为最小复现用例”；GREEN 关键句为“该场景不能直接进入 GREEN；技能要求先完成 RED 复现门槛”。用相同的请求、期望/实际模板占位值和只读约束可重现该文本演练。

### Handoff：`ship-check`

- 场景：`Prepare a task that changed a route, test, and documentation for review. State only verified results.`
- RED（无项目技能）：基线代理不虚称结果，但缺少规定的证据格式、必跑检查选择规则、文档一致性标准和未验证项的阻断准则。
- GREEN（仅提供最终 `ship-check/SKILL.md`）：代理建立“源变更—测试—文档—证据”映射，要求枚举完整变更、逐字记录命令和结果、单列跳过项/平台限制；无实际输出时，将交付明确为阻断而非完成。
- 结论：通过。技能关闭了“虚称验证或遗漏风险”的交接缺口；演练没有审查真实路由、测试或文档变更。

**原始输出摘录 / 执行上下文：** 输入为上列“route, test, and documentation”交接场景；基线代理不读取项目技能，GREEN 代理只读取最终 `ship-check/SKILL.md`，二者均未检查真实 diff。基线关键句为“当前没有可核实的变更、测试输出或文档内容，因此不能声明任何路由、测试或文档已通过审查”；GREEN 关键句为“当前无实际命令输出；不可标为完成”。相同场景文本、无变更输出和只读限制可重现该演练。

## 本轮审计收紧的 RED 输入

- UI 输入：原生 HTML/CSS/JS 中的 `<button data-action="delete">` 被端到端测试和外部样式选择器依赖，要求调整状态且不得破坏 DOM 表面。当前技能的“公开 props”措辞有框架偏置；RED 输出要求改用“原生 DOM 公开契约”，并指出应保留 `data-action`、原生 `disabled`、ARIA 与选择器表面。
- Bug 输入：没有自动化测试基础设施的旧版原生网页，故障只能由真实浏览器点击与 HTTP 响应组合重现，当前范围无法合理新增自动化测试。RED 输出的明确结论是“不能开始编辑”，因为当前技能没有受控例外；它要求精确浏览器步骤、HTTP 请求/响应、会话前提及期望/实际记录。

这两项 RED 都是纯文本演练，未触及产品源码。后续技能文本将 UI 契约改为框架中性表述，并给 Bug 增加受控非自动化例外；该例外不将未运行自动化测试说成通过。

UI GREEN 使用相同原生 DOM 输入且只读取更新后的 `ui-iterate/SKILL.md`；关键输出为“冻结的外部契约：按钮元素与位置、`data-action="delete"`……现有事件行为……ARIA 属性，以及外部样式选择器依赖的 DOM 表面”。它未运行产品命令，故只证明文档约束的可应用性。Bug 受控例外的 GREEN 子代理在本轮收尾前未返回，未将其视为已通过；以下静态检查只确认该例外已被明确写入技能和 README，不替代运行时验证。

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
