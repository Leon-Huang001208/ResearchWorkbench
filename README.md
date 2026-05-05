
# AlphaFoundry

本地优先、可企业化的买方投研情报系统。

## 概述

AlphaFoundry 是一个面向基金研究员工作流的 AI 产业情报与 Alpha 发现系统。系统采用模块化单体架构，使用 PostgreSQL + pgvector 作为核心事实存储，Markdown/Wiki 仅作为人类可读的投影层。

## 核心特性

- **资产分析卡**：对股票、ETF、指数、商品、外汇、债券、基金等资产形成标准化快照，覆盖财务、资金、量价、估值、股东、产业、事件、宏观八大维度
- **专题研究备忘录**：围绕产业链、政策变化、地缘冲突、供需错配、AI compute 等主题形成结构化研究
- **多情景市场分析报告**：对不确定性问题输出 3-4 个情景，每个情景包含概率、关键假设、触发条件、失效信号
- **候选信号与回测说明**：将研究观察转为 thesis，再转为 scored signal

---

## 快速开始

### 前置要求

- Python 3.11+

### 安装

```bash
cd ~/Desktop/Projects/AlphaFoundry

# 安装依赖
pip install -e ".[dev]"
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件（可选，模拟模式无需配置）
```

### 运行测试

```bash
# 基础功能测试
python examples/test_simple.py

# 信号实验室测试
python examples/test_signal_lab_simple.py
```

### 使用 CLI

```bash
# 资产分析
af analyze --asset 600000.SH

# 情景分析
af scenario --topic "人工智能产业发展对股票市场的影响"

# 更多命令请参考参考手册
```

---

## 项目结构

```
AlphaFoundry/
├── app/                    # 应用层（CLI、API、Web）
├── core/                   # 核心层（契约、接口、服务、网关）
├── data_layer/             # 数据层（适配器、解析器、仓储）
├── knowledge_layer/        # 知识层（实体、断言、事件、检索）
├── reasoning/              # 推理层（状态机、情景、证据）
├── reporting/              # 报告层（模板、合成、输出）
├── signal_lab/             # 信号实验室（特征、标签、回测）
├── storage/                # 存储层（迁移、Schema）
├── tests/                  # 测试
├── examples/               # 示例代码
└── docs/                   # 文档
```

---

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 语言 | Python 3.11+ |
| 数据验证 | Pydantic v2 |
| Web框架 | FastAPI |
| 数据库 | PostgreSQL 15+ |
| 向量扩展 | pgvector |
| ORM | SQLAlchemy 2.0 |
| 迁移 | Alembic |
| CLI | Click |
| 状态机 | LangGraph |
| 回测 | vectorbt, Backtrader |
| 日志 | structlog |

---

## 实施进度

- ✅ 第 1 个月：事实层与报告骨架
- ✅ 第 2 个月：事件、断言与多情景
- ✅ 第 3 个月：信号验证与团队工作台（核心功能完成）
- ⬜ Web Workbench v1

---

## 文档

- **[docs/REFERENCE.md](docs/REFERENCE.md)** - 完整参考手册（CLI、API、信号实验室）

---

## 开发指南

### 运行测试
```bash
pytest
```

### 代码格式化
```bash
black .
isort .
ruff check .
```

---

## 设计原则

1. **本地优先**：数据本地处理，保证数据安全
2. **模块化单体**：清晰的模块边界，可替换基础设施
3. **事实层**：PostgreSQL 作为单一事实源
4. **接口隔离**：数据源、模型后端、向量库等都通过接口隔离
5. **可审计**：所有操作都可追溯，支持审核流程
