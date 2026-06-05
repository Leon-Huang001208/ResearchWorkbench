"""Role-specific SOP definitions for cognitive Agents."""
from __future__ import annotations

from cognitive_agents.contracts import AgentRole, AgentSOP


_SOPS: dict[AgentRole, AgentSOP] = {
    "macro": AgentSOP(
        agent_role="macro",
        objective="判断宏观环境、政策、流动性和风险偏好是否支持当前事件或标的逻辑。",
        focus_areas=[
            "政策方向与监管态度",
            "利率、汇率、信用、流动性",
            "宏观周期与市场风险偏好",
            "主题所处市场 regime",
        ],
        required_evidence_kinds=["official", "catalyst", "structured", "media"],
        analysis_steps=[
            "识别事件对应的宏观变量和政策变量。",
            "判断这些变量对目标标的是顺风、逆风还是中性。",
            "检查市场是否已经交易该宏观逻辑。",
            "给出宏观维度的证伪条件。",
        ],
        output_expectations=[
            "明确宏观维度 view 和 confidence。",
            "只引用证据包中的 evidence_refs。",
            "列出需要继续跟踪的宏观数据或政策信号。",
        ],
        red_flags=[
            "政策文本与市场解读不一致。",
            "宏观逻辑已经充分交易且拥挤。",
            "流动性或汇率环境与多头逻辑冲突。",
        ],
    ),
    "fundamental": AgentSOP(
        agent_role="fundamental",
        objective="判断事件或主题是否能转化为收入、利润、现金流、估值或预期修正。",
        focus_areas=[
            "收入增长与订单可见度",
            "毛利率、净利率、ROE、现金流",
            "估值分位和一致预期",
            "公告事实与研报解释是否一致",
        ],
        required_evidence_kinds=["official", "research", "structured", "meeting"],
        analysis_steps=[
            "区分官方事实、研究观点和未经验证的市场传闻。",
            "判断影响路径是否能落到财务科目或估值假设。",
            "检查当前估值和预期是否已经反映该逻辑。",
            "列出基本面证伪条件。",
        ],
        output_expectations=[
            "说明核心 thesis 对哪一项基本面指标产生影响。",
            "给出关键假设和证伪触发条件。",
            "标记仍缺失的财务或公告证据。",
        ],
        red_flags=[
            "只有故事没有财务落点。",
            "一致预期已充分上修。",
            "会议纪要或公众号观点缺少官方证据支撑。",
        ],
    ),
    "technical": AgentSOP(
        agent_role="technical",
        objective="判断价格、成交、波动和相对强弱是否确认或否定事件逻辑。",
        focus_areas=[
            "趋势结构与关键价位",
            "成交量、换手率、波动率",
            "相对行业或指数强弱",
            "拥挤度、涨跌停、停牌和可交易性",
        ],
        required_evidence_kinds=["market_reaction", "structured", "catalyst"],
        analysis_steps=[
            "检查事件窗口内价格和成交是否确认。",
            "判断短期是否存在追高、拥挤或流动性风险。",
            "比较标的相对行业和基准的强弱。",
            "给出技术面证伪条件和下一步观察位。",
        ],
        output_expectations=[
            "明确技术面是否支持交易执行。",
            "列出关键价格/成交/波动观察点。",
            "指出不可交易或交易质量下降的条件。",
        ],
        red_flags=[
            "涨停一字板导致不可买入。",
            "放量滞涨或高位长上影。",
            "相对强弱落后于行业扩散。",
        ],
    ),
}


def get_agent_sop(role: AgentRole) -> AgentSOP:
    """Return the SOP for a role, or a conservative generic SOP."""
    return _SOPS.get(
        role,
        AgentSOP(
            agent_role=role,
            objective="基于统一证据包输出可审计的结构化观点。",
            focus_areas=["证据质量", "逻辑链条", "风险与证伪条件"],
            required_evidence_kinds=["other"],
            analysis_steps=[
                "读取证据包。",
                "区分事实、观点和推断。",
                "输出结构化观点和下一步检查项。",
            ],
            output_expectations=[
                "引用证据包中的 evidence_refs。",
                "说明关键假设、风险和证伪条件。",
            ],
            red_flags=["证据不足", "推断链条过长"],
        ),
    )
