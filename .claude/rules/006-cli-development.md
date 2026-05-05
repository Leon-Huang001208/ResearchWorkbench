---
name: CLI Development Standards
description: AlphaFoundry CLI 开发规范 - Click 命令开发规范
---

# CLI 开发规范

## 概述

AlphaFoundry 使用 Click 构建命令行工具，入口点为 `app/cli/main.py`。

---

## CLI 结构

### 目录结构

```
app/cli/
├── main.py              # 主入口
└── commands/
    ├── __init__.py
    ├── analyze.py       # 资产分析命令
    ├── scenario.py      # 情景分析命令
    ├── ingest.py        # 数据摄入命令
    ├── review.py        # 审核命令
    ├── signal.py        # 信号管理命令
    └── backtest.py      # 回测命令
```

### 主入口 (main.py)

```python
import click
from core.observability import get_logger
from app.cli.commands import analyze, scenario, ingest, review, signal, backtest

logger = get_logger(__name__)

@click.group()
@click.version_option(version="0.1.0")
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              default='INFO', help='日志级别')
@click.option('--log-file', type=click.Path(), help='日志文件路径')
def cli(log_level, log_file):
    """AlphaFoundry - 本地优先、可企业化的买方投研情报系统"""
    if log_file:
        # 配置日志文件
        pass

# 注册子命令
cli.add_command(analyze.analyze)
cli.add_command(scenario.scenario)
cli.add_command(ingest.ingest)
cli.add_command(review.review)
cli.add_command(signal.signal)
cli.add_command(backtest.backtest)

if __name__ == '__main__':
    cli()
```

---

## 命令开发规范

### 基本命令结构

```python
import click
from core.observability import get_logger
from core.services import AssetAnalysisService

logger = get_logger(__name__)

@click.group()
def analyze():
    """资产分析相关命令"""
    pass

@analyze.command(name='asset')
@click.option('--asset', required=True, help='资产标识符，如 600000.SH')
@click.option('--output', '-o', type=click.Path(), help='输出文件路径')
@click.option('--as-of', help='指定分析时间，ISO 格式')
@click.option('--use-mock/--no-mock', default=True, help='使用模拟数据')
def asset_analysis(asset, output, as_of, use_mock):
    """生成资产分析快照
    
    示例:
        af analyze asset --asset 600000.SH --output report.md
    """
    logger.info(f"Starting asset analysis for {asset}")
    
    try:
        service = AssetAnalysisService(use_mock=use_mock)
        snapshot = service.generate_snapshot(asset, as_of=as_of)
        
        if output:
            # 输出到文件
            if output.endswith('.md'):
                export_to_markdown(snapshot, output)
            elif output.endswith('.docx'):
                export_to_docx(snapshot, output)
            click.echo(f"Report saved to {output}")
        else:
            # 输出到终端
            click.echo(f"Analysis complete for {asset}")
            click.echo(f"PE TTM: {snapshot.valuation.get('pe_ttm', 'N/A')}")
            
        logger.info(f"Asset analysis completed for {asset}")
        
    except Exception as e:
        logger.error(f"Asset analysis failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
```

### 命令分组约定

- 使用 `@click.group()` 定义命令组
- 组名使用名词（如 `analyze`, `signal`, `review`）
- 子命令使用动词（如 `create`, `list`, `approve`, `reject`）

**示例**：
```
af signal create    # 创建信号
af signal list      # 列出信号
af signal validate  # 验证信号
af signal promote   # 升级信号
```

---

## 参数和选项设计

### 必需参数

使用 `required=True` 标记必需参数：

```python
@click.option('--asset', required=True, help='资产标识符')
```

### 选项类型

```python
# 字符串
@click.option('--thesis', help='信号论点')

# 路径
@click.option('--output', '-o', type=click.Path(), help='输出文件')

# 选择列表
@click.option('--status', type=click.Choice(['draft', 'review', 'approved']), 
              default='draft', help='信号状态')

# 布尔值开关
@click.option('--use-mock/--no-mock', default=True, help='使用模拟数据')

# 数字
@click.option('--score', type=float, help='信号评分')

# 多次使用
@click.option('--subject', '-s', multiple=True, help='相关标的')
```

### 帮助文档

- 所有命令和选项必须有 `help` 参数
- 命令 docstring 包含使用示例

---

## 退出代码约定

| 代码 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 参数错误 |
| 3 | 数据验证失败 |

```python
import click

if not is_valid_asset_id(asset):
    click.echo(f"Invalid asset ID: {asset}", err=True)
    raise click.Abort(code=2)
```

---

## 控制台输出约定

### 使用 click.echo

```python
# 正常输出
click.echo("Operation completed successfully")

# 错误输出
click.echo(f"Error: {e}", err=True)

# 格式化输出
click.echo()
click.echo("=" * 60)
click.echo("  Analysis Report")
click.echo("=" * 60)
```

### 进度显示

对于长时间运行的操作：

```python
import click

with click.progressbar(range(100), label="Processing...") as bar:
    for i in bar:
        # 处理
        pass
```

---

## CLI 命令检查清单

- [ ] 命令有清晰的 docstring 和 help
- [ ] 所有选项有 help 说明
- [ ] 使用适当的类型注解
- [ ] 包含使用示例
- [ ] 错误处理完善
- [ ] 使用 logger 记录操作
- [ ] 在 main.py 中正确注册
- [ ] 更新 CLI_GUIDE.md 文档

