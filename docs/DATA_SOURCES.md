# 数据源配置指南

AlphaFoundry支持多数据源，按优先级自动切换。

## 支持的数据源

| 优先级 | 数据源 | 状态 | 安装方式 | 说明 |
|--------|--------|------|----------|------|
| 1 | AKShare | ✅ 默认 | `pip install akshare` | 开源免费，推荐首选 |
| 2 | Tushare | ⚡️ 可选 | `pip install tushare` | 数据全面，需token |
| 3 | BaoStock | ⚡️ 可选 | `pip install baostock` | 证券专业数据 |
| 4 | 本地缓存 | ✅ 兜底 | 内置 | 预填充的历史数据 |

## 快速设置

### 方式一：仅使用AKShare（推荐新手）

```bash
pip install akshare
```

AKShare已包含在项目依赖中，开箱即用。

### 方式二：安装全部数据源

```bash
# 安装Tushare
pip install tushare

# 安装BaoStock
pip install baostock
```

### 方式三：配置Tushare Token（可选）

如需使用Tushare的高级数据，获取token：

1. 访问 https://tushare.pro/register 注册
2. 获取你的token
3. 设置环境变量或配置文件

```python
import tushare as ts
ts.set_token('your_token_here')
```

## 本地缓存设置

预填充历史数据（即使在线源不可用也能运行）：

```bash
python scripts/setup_price_cache.py
```

这会为以下股票创建真实历史模式数据：
- 600519.SH (贵州茅台)
- 000001.SZ (平安银行)
- 002594.SZ (比亚迪)
- 601012.SH (隆基绿能)
- 000300.SH (沪深300)

## 数据获取流程

系统自动按以下顺序尝试：

```
请求数据
    ↓
AKShare可用? → 是 → 获取 → 缓存到本地
    ↓ 否
Tushare可用? → 是 → 获取 → 缓存到本地
    ↓ 否
BaoStock可用? → 是 → 获取 → 缓存到本地
    ↓ 否
本地缓存有数据? → 是 → 返回缓存
    ↓ 否
返回空
```

## 验证数据源

```bash
# 测试数据源连接
python scripts/test_akshare.py

# 查看当前缓存数据
python scripts/view_db.py
```

## 数据源对比

| 特性 | AKShare | Tushare | BaoStock |
|------|---------|---------|----------|
| 免费 | ✅ | ✅ (基础) | ✅ |
| 需注册 | ❌ | ✅ | ❌ |
| A股数据 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| 港股数据 | ✅ | ✅ | ❌ |
| 财务数据 | ✅ | ✅ | ✅ |
| 实时行情 | ✅ | ✅ | ✅ |
| 安装难度 | 简单 | 中等 | 简单 |
| 推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

## 故障排查

### AKShare连接失败
```
症状: Connection aborted, Remote end closed
原因: AKShare数据源不稳定
解决: 自动降级到本地缓存，无需手动处理
```

### Tushare Token无效
```
症状: 提示需要token
解决: 免费注册获取，或只使用AKShare
```

### 本地缓存为空
```
解决: 运行 python scripts/setup_price_cache.py
```

## 扩展其他数据源

如需添加QStock、东方财富等数据源，参考：

- `data_layer/adapters/multi_source_adapter.py`
- `data_layer/adapters/akshare_adapter.py`

PR欢迎！

## PDF 转换

AlphaFoundry 支持将 PDF 研报自动转换为 Markdown/文本，支持三种策略自动降级：

| 优先级 | 策略 | 质量 | 依赖 | 描述 |
|--------|------|------|------|------|
| 1 (最高) | MinerU | 最高 | `mineru[all]` + `magic-pdf` CLI | opendatalab/mineru, 保留表格结构和文档布局 |
| 2 | MarkItDown | 高 | `markitdown[pdf]` | microsoft/markitdown, Markdown 转换 + 特征检测 |
| 3 (始终可用) | Raw Text | 基线 | `pdfplumber` | 纯文本提取, 内置页面标记 |

### 安装

```bash
# 基础安装 (pdfplumber only, always works)
pip install -e .

# 安装 MarkItDown 支持
pip install -e ".[pdf]"

# 安装完整 PDF 转换支持 (包括 MinerU)
pip install -e ".[pdf-full]"
```

### Admin API

| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/admin/pdf/convert` | 触发指定 PDF 转换 |
| GET | `/api/admin/pdf/stats` | 获取转换统计 |
| GET | `/api/admin/pdf/pending` | 列出待转换的 PDF |
| POST | `/api/admin/pdf/retry` | 重试失败的转换 |

详见 `docs/modules/pdf_conversion_pipeline.md`。
