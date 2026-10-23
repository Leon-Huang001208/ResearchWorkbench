/** Personal MCP credential and fixed evaluation controls. Never retain token values. */
import { escapeHTML as e } from './markdown.mjs';

export function renderMCPCredentials(state, component) {
  if (!component?.credential_support) return '';
  const disabled = state.busy ? 'disabled' : '';
  const candidate = state.mcpCandidate;
  const preview = state.mcpEvaluationPreview;
  const session = state.approvalSessionId || '';
  return `<section aria-label="个人数据连接"><h4>小创个人数据连接</h4>
    <p class="muted">凭据仅存于当前账户的系统凭据库；不会回显。此连接尚未通过内容准入，返回内容作为待核验线索。研究与收费调用默认关闭。</p>
    <button class="button" type="button" data-plugin-action="mcp-credential-status" ${disabled}>读取凭据状态</button>
    <p role="status">${state.mcpCredential?.configured === true ? '已配置' : state.mcpCredential?.configured === false ? '未配置' : '尚未读取凭据状态'}</p>
    <form data-plugin-credential><label>新的访问令牌 <input type="password" name="token" autocomplete="new-password" required ${disabled}></label><button class="button" type="submit" ${disabled}>保存个人凭据</button></form>
    <button class="button danger-outline" type="button" data-plugin-action="mcp-credential-delete" ${disabled}>删除个人凭据</button>
    <hr><h4>固定样本评估</h4><p class="muted">贵州茅台、宁德时代、中芯国际；产业链、机构调研、一致预期、预测调整、预告超预期、风险标签。18 次调用，最高 54 子弹。产业链仅代表当前关系，不能冒充历史数据。</p>
    <form data-plugin-evaluation-preview><label>评估截止日期 <input type="date" name="cutoff" value="${e(state.mcpEvaluationCutoff || '')}" required ${disabled}></label><button class="button" type="submit" ${disabled}>生成固定调用清单</button></form>
    ${candidate ? `<p class="muted">${e(candidate.status)} · 正式报告准入：未通过</p>` : ''}
    ${preview ? `<p>清单 ${e(preview.cutoff)} · ${preview.calls} 次 · 最高 ${preview.max_credits} 子弹</p><table><thead><tr><th>标的</th><th>查询</th><th>固定参数</th><th>上限</th><th>执行</th></tr></thead><tbody>${preview.entries.map(item => `<tr><td>${e(item.subject)}</td><td>${e(item.query)}<br><code>${e(item.tool_name)}</code></td><td><code>${e(JSON.stringify(item.arguments))}</code></td><td>${item.credits}</td><td>${state.mcpBudget ? `<button class="button" type="button" data-plugin-action="mcp-evaluation-call" data-entry="${e(item.subject + ':' + item.query)}" ${disabled}>执行此查询</button>` : '需先明确授权'}</td></tr>`).join('')}</tbody></table><p class="muted">工具与参数已绑定当前审批的 schema。授权不会执行调用；真实评估须再显式启动，不能自动重试未知结果。</p><form data-plugin-evaluation-authorize><label>授权会话 <select name="session_id" required ${disabled}><option value="">选择当前账户的研究会话</option>${(state.sessions || []).map(item => `<option value="${e(item.id)}" ${item.id === session ? 'selected' : ''}>${e(item.title || item.id)}</option>`).join('')}</select></label><label><input type="checkbox" name="confirmed" required ${disabled}> 我授权此清单最多 ${preview.max_credits} 子弹；未知受理继续占用额度，取消不推定退款。</label><button class="button" type="submit" ${disabled}>授权这份固定清单</button></form>` : ''}
    ${state.mcpBudget ? `<p role="status">固定预算已记录；每次点击仅执行清单中的一项，重复点击只恢复原调用。授权编号 <code>${e(state.mcpBudget.id)}</code></p>` : ''}
  </section>`;
}
