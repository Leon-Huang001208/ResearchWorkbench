"""
分类体系服务 - Issue #44

提供行业、主题、事件类型等分类体系，支持：
- 层级化行业分类
- 主题关键词匹配
- 实体识别辅助
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from core.observability import get_logger

logger = get_logger(__name__)


class IndustryLevel(str, Enum):
    """行业层级"""

    LEVEL_1 = "level_1"  # 一级行业
    LEVEL_2 = "level_2"  # 二级行业
    LEVEL_3 = "level_3"  # 三级行业


@dataclass
class IndustryNode:
    """行业节点"""

    id: str
    name: str
    level: IndustryLevel
    parent_id: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)


@dataclass
class ThemeNode:
    """主题节点"""

    id: str
    name: str
    keywords: List[str] = field(default_factory=list)
    related_industries: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    """分类结果"""

    primary_industry: Optional[str] = None
    secondary_industries: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)


class TaxonomyService:
    """分类体系服务"""

    def __init__(self):
        self.industries: Dict[str, IndustryNode] = {}
        self.themes: Dict[str, ThemeNode] = {}
        self._init_taxonomy()

    def _init_taxonomy(self):
        """初始化分类体系"""
        self._init_industries()
        self._init_themes()
        logger.info("Taxonomy initialized")

    def _init_industries(self):
        """初始化行业分类"""
        # 一级行业
        level_1_industries = [
            IndustryNode(
                id="tech",
                name="科技",
                level=IndustryLevel.LEVEL_1,
                keywords=["科技", "互联网", "软件", "IT", "信息"],
            ),
            IndustryNode(
                id="finance",
                name="金融",
                level=IndustryLevel.LEVEL_1,
                keywords=["金融", "银行", "证券", "保险", "基金", "期货"],
            ),
            IndustryNode(
                id="consumer",
                name="消费",
                level=IndustryLevel.LEVEL_1,
                keywords=["消费", "零售", "食品", "饮料", "白酒", "啤酒", "农业"],
            ),
            IndustryNode(
                id="pharma",
                name="医药生物",
                level=IndustryLevel.LEVEL_1,
                keywords=["医药", "生物", "医疗", "健康", "创新药", "CRO", "医疗器械"],
            ),
            IndustryNode(
                id="manufacturing",
                name="制造",
                level=IndustryLevel.LEVEL_1,
                keywords=["制造", "机械", "设备", "军工", "汽车"],
            ),
            IndustryNode(
                id="energy",
                name="能源",
                level=IndustryLevel.LEVEL_1,
                keywords=["能源", "石油", "煤炭", "电力", "新能源", "光伏", "风电"],
            ),
            IndustryNode(
                id="material",
                name="材料",
                level=IndustryLevel.LEVEL_1,
                keywords=["材料", "化工", "有色", "钢铁", "建材"],
            ),
            IndustryNode(
                id="infrastructure",
                name="基础设施",
                level=IndustryLevel.LEVEL_1,
                keywords=["基建", "建筑", "房地产", "交通", "运输"],
            ),
            IndustryNode(
                id="tmt",
                name="传媒通信",
                level=IndustryLevel.LEVEL_1,
                keywords=["传媒", "通信", "电信", "游戏", "出版"],
            ),
        ]

        # 二级行业
        level_2_industries = [
            # 科技下的二级
            IndustryNode(
                id="semiconductor",
                name="半导体",
                level=IndustryLevel.LEVEL_2,
                parent_id="tech",
                keywords=["半导体", "芯片", "集成电路", "晶圆", "光刻", "EDA", "CPU", "GPU"],
            ),
            IndustryNode(
                id="ai",
                name="人工智能",
                level=IndustryLevel.LEVEL_2,
                parent_id="tech",
                keywords=["AI", "人工智能", "大模型", "GPT", "生成式", "算力", "GPU", "光模块"],
            ),
            IndustryNode(
                id="software",
                name="软件服务",
                level=IndustryLevel.LEVEL_2,
                parent_id="tech",
                keywords=["软件", "SaaS", "云计算", "大数据", "云服务"],
            ),
            # 消费下的二级
            IndustryNode(
                id="food_beverage",
                name="食品饮料",
                level=IndustryLevel.LEVEL_2,
                parent_id="consumer",
                keywords=["食品", "饮料", "白酒", "啤酒", "乳业", "调味品"],
            ),
            IndustryNode(
                id="retail",
                name="零售",
                level=IndustryLevel.LEVEL_2,
                parent_id="consumer",
                keywords=["零售", "电商", "超市", "百货"],
            ),
            # 能源下的二级
            IndustryNode(
                id="new_energy",
                name="新能源",
                level=IndustryLevel.LEVEL_2,
                parent_id="energy",
                keywords=["新能源", "光伏", "风电", "储能", "锂电", "电池"],
            ),
            # 制造下的二级
            IndustryNode(
                id="auto",
                name="汽车",
                level=IndustryLevel.LEVEL_2,
                parent_id="manufacturing",
                keywords=["汽车", "整车", "零部件", "新能源汽车", "特斯拉", "比亚迪"],
            ),
            IndustryNode(
                id="military",
                name="军工",
                level=IndustryLevel.LEVEL_2,
                parent_id="manufacturing",
                keywords=["军工", "航空", "航天", "船舶", "兵器"],
            ),
        ]

        # 三级行业
        level_3_industries = [
            IndustryNode(
                id="photovoltaic",
                name="光伏",
                level=IndustryLevel.LEVEL_3,
                parent_id="new_energy",
                keywords=["光伏", "硅片", "电池片", "组件", "逆变器", "HJT", "TOPCon"],
            ),
            IndustryNode(
                id="wind_power",
                name="风电",
                level=IndustryLevel.LEVEL_3,
                parent_id="new_energy",
                keywords=["风电", "风机", "叶片", "塔筒"],
            ),
            IndustryNode(
                id="lithium_battery",
                name="锂电池",
                level=IndustryLevel.LEVEL_3,
                parent_id="new_energy",
                keywords=["锂电", "锂电池", "动力电池", "正极", "负极", "隔膜", "电解液", "宁德时代"],
            ),
        ]

        # 添加到字典
        for industry in level_1_industries + level_2_industries + level_3_industries:
            self.industries[industry.id] = industry

        # 构建父子关系
        for industry in self.industries.values():
            if industry.parent_id and industry.parent_id in self.industries:
                parent = self.industries[industry.parent_id]
                parent.children.append(industry.id)

    def _init_themes(self):
        """初始化主题分类"""
        themes = [
            ThemeNode(
                id="ai_investment",
                name="AI投资",
                keywords=["AI", "人工智能", "大模型", "ChatGPT", "GPT", "生成式"],
                related_industries=["tech", "ai", "semiconductor"],
            ),
            ThemeNode(
                id="policy_stimulus",
                name="政策刺激",
                keywords=["政策", "刺激", "宽松", "降准", "降息", "利好"],
                related_industries=["finance"],
            ),
            ThemeNode(
                id="supply_chain",
                name="供应链",
                keywords=["供应链", "自主可控", "国产替代", "卡脖子"],
                related_industries=["tech", "semiconductor"],
            ),
            ThemeNode(
                id="esg",
                name="ESG",
                keywords=["ESG", "碳中和", "碳达峰", "环保", "绿色"],
                related_industries=["energy", "new_energy"],
            ),
            ThemeNode(
                id="earnings",
                name="业绩",
                keywords=["业绩", "财报", "年报", "季报", "净利润", "增长"],
                related_industries=[],
            ),
            ThemeNode(
                id="merger",
                name="并购重组",
                keywords=["并购", "重组", "收购", "合并"],
                related_industries=[],
            ),
            ThemeNode(
                id="price_change",
                name="价格变动",
                keywords=["涨价", "提价", "降价", "价格"],
                related_industries=["material", "energy", "consumer"],
            ),
        ]

        for theme in themes:
            self.themes[theme.id] = theme

    def classify(self, text: str, title: Optional[str] = None) -> ClassificationResult:
        """
        分类文本

        Args:
            text: 文本内容
            title: 标题（可选，权重更高）

        Returns:
            分类结果
        """
        result = ClassificationResult()

        # 合并标题和内容，标题权重更高
        search_text = text
        if title:
            search_text = (title + " ") * 3 + text

        search_text_lower = search_text.lower()

        # 匹配行业
        industry_scores: Dict[str, int] = {}
        for industry_id, industry in self.industries.items():
            score = 0
            for keyword in industry.keywords:
                if keyword in search_text:
                    score += 2
                if keyword.lower() in search_text_lower:
                    score += 1
            for alias in industry.aliases:
                if alias in search_text:
                    score += 1
            if score > 0:
                industry_scores[industry_id] = score

        # 确定一级行业
        level_1_scores = {
            k: v
            for k, v in industry_scores.items()
            if self.industries[k].level == IndustryLevel.LEVEL_1
        }

        if level_1_scores:
            sorted_level_1 = sorted(level_1_scores.items(), key=lambda x: x[1], reverse=True)
            result.primary_industry = sorted_level_1[0][0]
            result.confidence_scores[f"industry:{result.primary_industry}"] = min(
                sorted_level_1[0][1] / 10, 1.0
            )

            # 二级行业
            for ind_id, score in sorted_level_1[1:]:
                if score > 0:
                    result.secondary_industries.append(ind_id)
                    result.confidence_scores[f"industry:{ind_id}"] = min(score / 10, 1.0)

            # 查找该一级行业下的二级行业
            if result.primary_industry:
                primary = self.industries[result.primary_industry]
                for child_id in primary.children:
                    if child_id in industry_scores:
                        if child_id not in result.secondary_industries:
                            result.secondary_industries.append(child_id)
                        result.confidence_scores[f"industry:{child_id}"] = min(
                            industry_scores[child_id] / 10, 1.0
                        )

        # 匹配主题
        theme_scores: Dict[str, int] = {}
        for theme_id, theme in self.themes.items():
            score = 0
            for keyword in theme.keywords:
                if keyword in search_text:
                    score += 2
                if keyword.lower() in search_text_lower:
                    score += 1
            if score > 0:
                theme_scores[theme_id] = score

        sorted_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)
        for theme_id, score in sorted_themes:
            result.themes.append(theme_id)
            result.confidence_scores[f"theme:{theme_id}"] = min(score / 8, 1.0)

        return result

    def get_industry_hierarchy(self, industry_id: str) -> List[IndustryNode]:
        """
        获取行业层级路径

        Args:
            industry_id: 行业ID

        Returns:
            从根到该行业的路径
        """
        path: List[IndustryNode] = []
        current_id: Optional[str] = industry_id

        while current_id and current_id in self.industries:
            current = self.industries[current_id]
            path.insert(0, current)
            current_id = current.parent_id

        return path

    def get_industry_keywords(self, industry_id: str) -> Set[str]:
        """获取行业的所有关键词（包括所有子行业）"""
        keywords: Set[str] = set()

        if industry_id not in self.industries:
            return keywords

        industry = self.industries[industry_id]
        keywords.update(industry.keywords)

        for child_id in industry.children:
            keywords.update(self.get_industry_keywords(child_id))

        return keywords

    def list_level_1_industries(self) -> List[IndustryNode]:
        """列出所有一级行业"""
        return [ind for ind in self.industries.values() if ind.level == IndustryLevel.LEVEL_1]

    def list_child_industries(self, parent_id: str) -> List[IndustryNode]:
        """列出子行业"""
        if parent_id not in self.industries:
            return []
        parent = self.industries[parent_id]
        return [self.industries[cid] for cid in parent.children if cid in self.industries]

    def get_theme(self, theme_id: str) -> Optional[ThemeNode]:
        """获取主题"""
        return self.themes.get(theme_id)

    def list_themes(self) -> List[ThemeNode]:
        """列出所有主题"""
        return list(self.themes.values())
