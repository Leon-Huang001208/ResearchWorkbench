/** Host-global final veto; no arbitrary shell, filesystem, URL or MCP tools. */
export const inject = ['tools'];

export const RESEARCH_TOOLS = new Set([
  'af_run_script', 'af_public_data',
  'datahub_search_assets', 'datahub_get_trading_calendar', 'datahub_get_market_bars',
  'datahub_get_market_snapshot', 'datahub_get_index_data', 'datahub_get_financials',
  'datahub_get_market_activity', 'datahub_get_factor_macro', 'datahub_get_fund_data',
  'datahub_search_news', 'datahub_search_announcements', 'datahub_search_research', 'datahub_search_web',
  'skill', 'web_search', 'subagent', 'report', 'send_message', 'interrupt_agent', 'list_agents',
]);

export function apply(ctx, config = {}) {
  const calls = new WeakMap();
  ctx.tools.guard((execution) => {
    if (config.enabled === true && RESEARCH_TOOLS.has(execution.name) && execution.agent) {
      const turn = execution.agent.session.events.findLast((event) => event.type === 'turn/start')?.data.turn;
      let budget = calls.get(execution.agent);
      if (!budget || budget.turn !== turn) { budget = { turn, calls: 0, children: 0 }; calls.set(execution.agent, budget); }
      budget.calls++;
      if (execution.name === 'subagent') budget.children++;
      if (budget.calls <= 48 && budget.children <= 4) return undefined;
      ctx.logger.warn('AlphaFoundry denied tool budget overflow');
      return 'Research tool budget exhausted. Report partial findings and missing work.';
    }
    ctx.logger.warn('AlphaFoundry rejected disabled tool: %s', execution.name);
    return 'AlphaFoundry: this tool is not authorized. Do not attempt shell, arbitrary URL, MCP or host-file access.';
  });
}
