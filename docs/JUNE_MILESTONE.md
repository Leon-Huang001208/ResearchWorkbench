# June 里程碑：事件、断言与多情景

**完成日期**: 2026-05-03

## 概述

完成六月里程碑的所有功能，包括知识层、推理引擎、情景生成、审核队列和数据摄入流程。

## 新增功能

### 1. 知识层 (Knowledge Layer)

#### 实体解析 (Entity Resolution)
- 支持中英文实体识别
- Canonical ID 生成器
- 实体别名管理
- 支持股票代码、公司名称、概念等实体类型

**文件**:
- `knowledge_layer/entity_resolution/types.py` - 类型定义
- `knowledge_layer/entity_resolution/canonicalizer.py` - Canonical ID 生成
- `knowledge_layer/entity_resolution/resolver.py` - 实体解析器
- `knowledge_layer/entity_resolution/alias_manager.py` - 别名管理

#### 断言提取 (Assertion Extraction)
- 从文本中提取事实断言
- 支持主语、谓语、宾语三元组结构
- 置信度评估
- 质量门机制（自动批准或标记为待审核）

**文件**:
- `knowledge_layer/assertions/prompts.py` - LLM 提示模板
- `knowledge_layer/assertions/extractor.py` - 断言提取器
- `knowledge_layer/assertions/validator.py` - 断言验证器

#### 事件提取 (Event Extraction)
- 从文本中提取标准事件
- 支持多种事件类型（财报、并购、分红、政策变化等）
- 影响方向分析（正向、负向、混合、未知）
- 质量门机制

**文件**:
- `knowledge_layer/events/types.py` - 类型定义
- `knowledge_layer/events/extractor.py` - 事件提取器
- `knowledge_layer/events/quality_gate.py` - 事件质量门

#### 向量检索 (Vector Retrieval)
- 基于 pgvector 的向量存储接口
- 混合搜索（向量相似度 + 关键词匹配）
- 支持元数据过滤
- 内存版本供测试和开发使用

**文件**:
- `knowledge_layer/retrieval/vector_store.py` - 向量存储接口
- `knowledge_layer/retrieval/hybrid_search.py` - 混合搜索器

### 2. 推理引擎 (Reasoning Engine)

#### 状态与流程
- 完整的推理状态定义
- 基于 LangGraph 风格的状态机实现
- 多节点协作流程

**文件**:
- `reasoning/state.py` - 推理状态定义
- `reasoning/graph.py` - 推理引擎主入口

#### 核心节点
1. **Task Router** - 任务路由，判断请求类型
2. **Evidence Collector** - 证据收集，检索相关文档和断言
3. **Hypothesis Builder** - 假设生成，创建 3-4 个情景
4. **Skeptic** - 反证审查，验证假设合理性
5. **Probability Calibrator** - 概率校准，确保概率和接近 1
6. **Trace Writer** - 推理追踪，记录完整推理过程

**文件**:
- `reasoning/router/task_router.py`
- `reasoning/evidence/collector.py`
- `reasoning/scenarios/builder.py`
- `reasoning/skeptic/reviewer.py`
- `reasoning/scenarios/calibrator.py`
- `reasoning/traces/writer.py`

### 3. 情景服务 (Scenario Service)

- 封装推理引擎，提供友好的 API
- 生成专题研究报告
- 支持输出到 Markdown 文件

**文件**:
- `core/services/scenario_service.py`

### 4. 审核服务 (Review Service)

- 列出待审核的断言和事件
- 支持批准、拒绝操作
- 审核统计信息

**文件**:
- `core/services/review_service.py`

### 5. 摄入服务 (Ingest Service)

- 文档摄入流程
- 自动提取断言和事件
- 质量门检查
- 索引到向量存储

**文件**:
- `core/services/ingest_service.py`

### 6. 新增 CLI 命令

#### Scenario 命令
```bash
# 生成多情景分析
af scenario --topic "人工智能产业发展"

# 输出到文件
af scenario --topic "美联储政策" --output report.md
```

**文件**: `app/cli/commands/scenario.py`

#### Ingest 命令
```bash
# 摄入文档
af ingest --file report.pdf --source-type report --source-name "券商研报"
```

**文件**: `app/cli/commands/ingest.py`

#### Review 命令
```bash
# 列出待审核项目
af review list

# 批准断言
af review approve <assertion_id>

# 拒绝断言
af review reject <assertion_id>

# 查看统计
af review stats
```

**文件**: `app/cli/commands/review.py`

## 使用示例

### 情景生成示例

```python
from core.services.scenario_service import ScenarioService

service = ScenarioService()

# 生成情景集合
scenario_set = service.generate_scenario_set(
    topic="人工智能产业发展对股票市场的影响"
)

print(f"生成了 {len(scenario_set.hypotheses)} 个情景")
for hypothesis in scenario_set.hypotheses:
    print(f"{hypothesis.title} (概率: {hypothesis.probability:.0%})")

# 生成完整报告
report = service.generate_thesis_report(
    topic="人工智能产业发展对股票市场的影响",
    output_path=Path("scenario_report.md")
)
```

### 文档摄入示例

```python
from core.services.ingest_service import IngestService

service = IngestService()

# 摄入文本
result = service.ingest_text(
    text="贵州茅台2026年一季度财报显示，净利润同比增长28%",
    source_type="report",
    source_name="财报",
    title="贵州茅台2026一季报"
)

print(f"提取了 {result['assertions_extracted']} 个断言")
print(f"提取了 {result['events_extracted']} 个事件")
```

### 向量检索示例

```python
from knowledge_layer.retrieval import InMemoryVectorStore, HybridSearcher

# 创建索引
store = InMemoryVectorStore()
searcher = HybridSearcher(store)

# 索引文档
searcher.index_document(
    doc_id="doc1",
    text="贵州茅台发布财报，净利润同比增长28%",
    metadata={"source": "财报"}
)

# 搜索
results = searcher.search("茅台财报", top_k=5)
for result in results:
    print(f"{result['doc_id']}: {result['score']:.2f}")
```

## 测试

### 运行测试脚本

```bash
# 运行简化版测试
python examples/test_simple.py
```

### 预期输出

```
============================================================
AlphaFoundry 六月里程碑 - 功能测试（简化版）
============================================================
============================================================
测试实体解析
============================================================
输入文本: 贵州茅台（600519.SH）发布财报，净利润同比增长28%

生成规范ID: equity:cn:sse:600519

✓ 实体解析测试完成

============================================================
测试向量检索
============================================================
索引文档: doc1 - 贵州茅台发布财报，净利润同比增长28%...
索引文档: doc2 - 腾讯控股公布业绩，云业务收入增长强劲...
索引文档: doc3 - 美联储加息，影响全球资产定价...
索引文档: doc4 - 人工智能技术突破，推动科技股上涨...

搜索查询: 茅台财报

找到 3 个结果:
  - doc1 (分数: 0.78) - 贵州茅台发布财报，净利润同比增长28%...
  - doc4 (分数: 0.57) - 人工智能技术突破，推动科技股上涨...
  - doc2 (分数: 0.51) - 腾讯控股公布业绩，云业务收入强劲...

✓ 向量检索测试完成

============================================================
测试情景生成
============================================================
问题: 人工智能产业发展对股票市场的影响

生成 3 个情景假设:

  - 基准情景 - 按预期发展 (概率: 50%)
    假设: 当前趋势继续, 无重大意外事件

  - 乐观情景 - 超预期表现 (概率: 25%)
    假设: 数据超预期, 政策利好

  - 悲观情景 - 不及预期 (概率: 25%)
    假设: 数据不及预期, 外部负面冲击

残余不确定性: 7 项

✓ 情景生成测试完成

============================================================
测试完成: 3 通过, 0 失败
============================================================
```

## 架构改进

### 模块依赖关系

```
app/cli
  ↓
core/services (ScenarioService, IngestService, ReviewService)
  ↓
├─ reasoning (推理引擎)
├─ knowledge_layer (知识层)
├─ core/contracts (数据契约)
└─ reporting (报告生成)
```

### 数据流程

```
文档摄入 → 实体解析 → 断言提取 → 事件提取 → 向量索引
                                           ↓
情景生成 ← 证据检索 ← 推理引擎 ← 用户查询
   ↓
报告输出
```

## 后续工作 (七月里程碑)

- Signal Lab（特征工程、标签系统、信号评分）
- vectorbt 和 Backtrader 集成
- Shadowing workflow
- 团队权限、监控、灰度发布
- Web Workbench v1
