"""
研报生成服务
"""
import logging
from datetime import datetime
from typing import Dict
from core.utils.id_gen import generate_id
from core.services.asset_analysis_service import AssetAnalysisService
from core.observability import get_logger

logger = get_logger(__name__)

class ReportGenerator:
    """
    研报生成器，支持生成多种类型的资产研究报告
    """
    
    def __init__(self):
        self.asset_analysis_service = AssetAnalysisService()
        self.report_store = {}  # 临时存储生成的报告，生产环境替换为数据库
    
    async def generate(self, canonical_id: str, report_type: str, as_of: datetime) -> Dict:
        """
        生成研报
        """
        logger.info(f"Generating {report_type} report for {canonical_id}")
        
        # 获取资产分析数据
        snapshot = await self.asset_analysis_service.analyze(canonical_id, as_of)
        
        # 生成报告内容
        if report_type == "summary":
            content = self._generate_summary_report(snapshot)
        elif report_type == "valuation":
            content = self._generate_valuation_report(snapshot)
        else:
            content = self._generate_full_report(snapshot)
        
        report_id = generate_id("report")
        self.report_store[report_id] = content
        
        return {
            "report_id": report_id,
            "content": content
        }
    
    async def get_report_content(self, report_id: str) -> str:
        """
        获取报告内容
        """
        if report_id not in self.report_store:
            raise ValueError("Report not found")
        return self.report_store[report_id]
    
    def _generate_summary_report(self, snapshot) -> str:
        """生成摘要报告"""
        event_line = snapshot.event_impact[0] if snapshot.event_impact else '无近期重大事件'
        percentile = snapshot.valuation.get('historical_percentile_pe', 0.5)
        if percentile < 0.3:
            suggestion = '增持'
        elif percentile < 0.7:
            suggestion = '持有'
        else:
            suggestion = '观望'
        roe_val = snapshot.financial.get('roe', {}).get('ttm')
        roe_str = f"{roe_val * 100:.1f}%" if roe_val else "N/A"
        debt_ratio = snapshot.financial.get('debt_ratio')
        debt_str = f"{debt_ratio * 100:.1f}%" if debt_ratio else "N/A"
        return f"""# {snapshot.canonical_id} 投资摘要报告
生成时间：{snapshot.as_of.strftime('%Y-%m-%d %H:%M:%S')}

## 核心指标
- 收盘价：¥{snapshot.price_volume.get('close_price', 'N/A')}
- PE(TTM)：{snapshot.valuation.get('pe_ttm', 'N/A')}
- ROE(TTM)：{roe_str}
- 资产负债率：{debt_str}

## 近期事件
{event_line}

## 投资建议
当前估值处于历史{percentile * 100:.0f}分位，建议{suggestion}
"""
    
    def _generate_valuation_report(self, snapshot) -> str:
        """生成估值报告"""
        pe = snapshot.valuation.get('pe_ttm', 0)
        industry_pe = snapshot.industry.get('industry_pe', 0)
        if pe < industry_pe * 0.7:
            valuation_conclusion = "显著低估"
        elif pe < industry_pe * 1.3:
            valuation_conclusion = "合理"
        else:
            valuation_conclusion = "高估"
        close_price = snapshot.price_volume.get('close_price', 0)
        return f"""# {snapshot.canonical_id} 估值分析报告
生成时间：{snapshot.as_of.strftime('%Y-%m-%d %H:%M:%S')}

## 估值指标
| 指标 | 当前值 | 历史分位 | 行业平均 |
|------|--------|----------|----------|
| PE(TTM) | {snapshot.valuation.get('pe_ttm', 'N/A')} | {snapshot.valuation.get('historical_percentile_pe', 0) * 100:.0f}% | {snapshot.industry.get('industry_pe', 'N/A')} |
| PB | {snapshot.valuation.get('pb', 'N/A')} | - | {snapshot.industry.get('industry_pb', 'N/A')} |
| PS | {snapshot.valuation.get('ps', 'N/A')} | - | - |
| 股息率 | {snapshot.valuation.get('dividend_yield', 0) * 100:.2f}% | - | - |

## 价格区间
- 52周最高价：¥{snapshot.price_volume.get('high_52w', 'N/A')}
- 52周最低价：¥{snapshot.price_volume.get('low_52w', 'N/A')}
- 当前价：¥{snapshot.price_volume.get('close_price', 'N/A')}

## 估值结论
当前估值{valuation_conclusion}，合理估值区间：¥{close_price * 0.8:.1f} - ¥{close_price * 1.2:.1f}
"""
    
    def _generate_full_report(self, snapshot) -> str:
        """生成完整研报"""
        events_text = '\n'.join([f"- {event}" for event in snapshot.event_impact]) if snapshot.event_impact else '无近期重大事件'
        summary_part = self._generate_summary_report(snapshot).split('## 投资建议')[1]
        valuation_part = self._generate_valuation_report(snapshot).split('## 估值结论')[0]
        revenue = snapshot.financial.get('revenue', {}).get('ttm', 0) / 1e8
        revenue_yoy = snapshot.financial.get('revenue', {}).get('yoy', 0) * 100
        revenue_qoq = snapshot.financial.get('revenue', {}).get('qoq', 0) * 100
        net_profit = snapshot.financial.get('net_profit', {}).get('ttm', 0) / 1e8
        net_profit_yoy = snapshot.financial.get('net_profit', {}).get('yoy', 0) * 100
        net_profit_qoq = snapshot.financial.get('net_profit', {}).get('qoq', 0) * 100
        eps = snapshot.financial.get('eps', {}).get('ttm', 0)
        eps_yoy = snapshot.financial.get('eps', {}).get('yoy', 0) * 100
        eps_qoq = snapshot.financial.get('eps', {}).get('qoq', 0) * 100
        roe = snapshot.financial.get('roe', {}).get('ttm', 0) * 100
        roe_yoy = snapshot.financial.get('roe', {}).get('yoy', 0) * 100
        roe_qoq = snapshot.financial.get('roe', {}).get('qoq', 0) * 100
        main_inflow = snapshot.fund_flow.get('main_net_inflow', 0) / 1e8
        northbound = snapshot.fund_flow.get('northbound_holding', 0) * 100
        pledge_ratio = snapshot.fund_flow.get('pledge_ratio', 0) * 100
        return f"""# {snapshot.canonical_id} 完整投资研究报告
生成时间：{snapshot.as_of.strftime('%Y-%m-%d %H:%M:%S')}

## 一、基本信息
- 所属行业：{snapshot.industry.get('sw_level1', 'N/A')} -> {snapshot.industry.get('sw_level2', 'N/A')} -> {snapshot.industry.get('sw_level3', 'N/A')}
- 控股股东：{snapshot.shareholder.get('controlling_shareholder', 'N/A')}
- 机构持股比例：{snapshot.fund_flow.get('institutional_holding', 0) * 100:.1f}%

## 二、财务分析
| 指标 | TTM值 | 同比增长 | 环比增长 |
|------|-------|----------|----------|
| 营业收入 | ¥{revenue:.1f}亿 | {revenue_yoy:.1f}% | {revenue_qoq:.1f}% |
| 净利润 | ¥{net_profit:.1f}亿 | {net_profit_yoy:.1f}% | {net_profit_qoq:.1f}% |
| EPS | ¥{eps:.2f} | {eps_yoy:.1f}% | {eps_qoq:.1f}% |
| ROE | {roe:.1f}% | {roe_yoy:.1f}% | {roe_qoq:.1f}% |

## 三、估值分析
{valuation_part}

## 四、资金面分析
- 主力资金净流入：¥{main_inflow:.1f}亿
- 北向资金持股：{northbound:.1f}%
- 质押比例：{pledge_ratio:.1f}%

## 五、近期重大事件
{events_text}

## 六、投资建议
{summary_part}
"""
