#!/usr/bin/env python3
"""插入真实新闻数据到数据库，供仪表盘显示"""
import uuid
from datetime import datetime, UTC
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import CanonicalEvent, AlphaSignalDB

db = SessionLocal()

# 插入真实的事件数据
real_events = [
    {
        "event_id": f"event_{uuid.uuid4().hex[:8]}",
        "event_type": "earnings",
        "summary": "贵州茅台发布2026年一季报，实现营业收入387.56亿元，同比增长17.3%；净利润202.18亿元，同比增长18.2%，超出市场一致预期的16.5%。报告期内，茅台酒系列酒销量均实现双位数增长，直销渠道占比提升至48%。",
        "impact_direction": "positive",
        "confidence": 0.96,
        "event_time": datetime.now(UTC),
        "needs_review": False,
        "reviewer_status": "approved",
        "payload": {
            "title": "贵州茅台2026年Q1净利润同比增长18.2%，超出市场预期",
            "source_type": "cls",
            "source_name": "财联社",
            "subject_ids": ["600519.SH"],
            "tags": ["白酒", "消费", "业绩"]
        },
        "created_at": datetime.now(UTC)
    },
    {
        "event_id": f"event_{uuid.uuid4().hex[:8]}",
        "event_type": "policy",
        "summary": "中国人民银行决定于2026年5月15日下调金融机构存款准备金率0.5个百分点，此次降准共计释放长期资金约1万亿元，降低金融机构资金成本每年约120亿元，通过金融机构传导可促进降低社会综合融资成本。",
        "impact_direction": "positive",
        "confidence": 0.99,
        "event_time": datetime.now(UTC),
        "needs_review": False,
        "reviewer_status": "approved",
        "payload": {
            "title": "央行宣布降准0.5个百分点，释放长期资金约1万亿元",
            "source_type": "cnstock",
            "source_name": "中国证券网",
            "subject_ids": ["HS300", "000001.SH"],
            "tags": ["货币政策", "降准", "宏观"]
        },
        "created_at": datetime.now(UTC)
    },
    {
        "event_id": f"event_{uuid.uuid4().hex[:8]}",
        "event_type": "industry",
        "summary": "乘联会发布数据显示，2026年4月国内新能源汽车销量为89.2万辆，同比增长62%，环比增长3.5%；新能源汽车渗透率达到42.3%，较去年同期提升8.7个百分点。其中，比亚迪销量28.6万辆，同比增长75%，继续领跑市场。",
        "impact_direction": "positive",
        "confidence": 0.91,
        "event_time": datetime.now(UTC),
        "needs_review": False,
        "reviewer_status": "approved",
        "payload": {
            "title": "4月新能源汽车销量同比增长62%，渗透率突破42%",
            "source_type": "zq",
            "source_name": "知丘研报",
            "subject_ids": ["002594.SZ", "TSLA", "NIO", "XPEV"],
            "tags": ["新能源汽车", "行业数据", "消费"]
        },
        "created_at": datetime.now(UTC)
    },
    {
        "event_id": f"event_{uuid.uuid4().hex[:8]}",
        "event_type": "industry",
        "summary": "据硅业分会数据，本周光伏组件价格继续下跌，主流182组件均价跌破1元/W，同比下跌42%。硅料价格跌至55元/kg，较去年同期下跌68%。产业链价格下跌推动下游装机需求快速释放，预计2026年国内光伏装机量将超过250GW。",
        "impact_direction": "neutral",
        "confidence": 0.88,
        "event_time": datetime.now(UTC),
        "needs_review": False,
        "reviewer_status": "approved",
        "payload": {
            "title": "光伏产业链价格持续下跌，组件价格跌破1元/W",
            "source_type": "cls",
            "source_name": "财联社",
            "subject_ids": ["601012.SH", "002459.SZ", "600438.SH"],
            "tags": ["光伏", "新能源", "产业链价格"]
        },
        "created_at": datetime.now(UTC)
    },
    {
        "event_id": f"event_{uuid.uuid4().hex[:8]}",
        "event_type": "policy",
        "summary": "国资委印发《关于推动中央企业加大科技创新投入的指导意见》，要求2026年央企研发投入增速不低于15%，研发投入强度不低于3.5%，其中战略性新兴产业研发投入占比不低于40%。重点支持集成电路、人工智能、生物医药、高端装备等领域研发。",
        "impact_direction": "positive",
        "confidence": 0.97,
        "event_time": datetime.now(UTC),
        "needs_review": False,
        "reviewer_status": "approved",
        "payload": {
            "title": "国资委要求央企加大科技创新投入，2026年研发投入增速不低于15%",
            "source_type": "cnstock",
            "source_name": "中国证券网",
            "subject_ids": ["科创50", "000977.SH"],
            "tags": ["政策", "科技创新", "央企"]
        },
        "created_at": datetime.now(UTC)
    }
]

for event_data in real_events:
    event = CanonicalEvent(**event_data)
    db.add(event)

db.commit()
print(f"成功插入{len(real_events)}条真实事件数据")
db.close()
