# RWB-AUTO-002-03: 增量抓取实现报告

## 概述

本报告描述了为财联社（CLS）、中国证券报（CNStock）和知丘（ZQ）实现的增量抓取功能。该功能允许爬虫在遇到之前已处理过的记录时停止，实现高效的增量更新。

## 实现的功能

### 1. 水位线追踪基础架构

在三个爬虫的状态管理器中都实现了统一的水位线接口：

```python
def set_watermark(self, key: str, item_id: str, extra: Optional[Dict[str, Any]] = None) -> None
def get_watermark(self, key: str) -> Optional[Dict[str, Any]]
def has_reached_watermark(self, key: str, item_id: str) -> bool
def clear_watermark(self, key: str) -> None
```

### 2. 配置项

添加了 `stop_on_known` 配置项（默认为 `True`），允许在遇到已知记录时停止抓取。

### 3. 水位线键格式

- **CLS**: `cls:{date}` - 按日期组织的水位线
- **CNStock**: `cnstock:{category}:{date}` - 按分类和日期组织的水位线
- **ZQ**: `zq:{doc_type}:{search_term}:{date}` - 按文档类型、搜索词和日期组织的水位线

## 各爬虫实现详情

### 财联社 (CLS)

**文件**: `data_layer/crawlers/cls/cls.py`

- 修改了 `_get_all_day_telegrams` 方法
- 在迭代电报列表时检测已知记录
- 遇到第一条已知记录时停止抓取
- 将第一条新记录的 ID 设置为水位线

### 中国证券报 (CNStock)

**文件**: `data_layer/crawlers/cnstock/cnstock.py`

- 修改了 `crawl_news_list` 方法
- 为每个频道单独追踪水位线
- 支持增量抓取，遇到已知新闻时停止
- 更新了 CLI 参数，添加 `--no-stop-on-known` 选项

### 知丘 (ZQ)

**文件**: 
- `data_layer/crawlers/zq/zhiqiu/base_fetcher.py`
- `data_layer/crawlers/zq/zhiqiu/processors/base.py`
- `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py`
- `data_layer/crawlers/zq/zhiqiu/processors/news_processor.py`
- `data_layer/crawlers/zq/zhiqiu/processors/meeting_processor.py`

- 更新了 `BaseProcessor` 接口，添加 `stop_on_known` 和 `watermark_key` 参数
- 所有三个处理器（ReportProcessor、NewsProcessor、MeetingProcessor）都实现了水位线逻辑
- 修改了 `_process_search_result` 方法以支持水位线

## 去重行为

1. **首次抓取**: 抓取所有可用记录，保存到状态文件，设置水位线
2. **后续抓取**: 从最新记录开始，遇到水位线记录时停止
3. **重复运行**: 不会产生重复数据，确保数据一致性
4. **水位线更新**: 每次成功抓取后更新水位线为最新记录

## 测试建议

建议测试以下场景：

1. 首次抓取 - 验证所有记录被抓取
2. 第二次抓取 - 验证遇到已知记录时及时停止
3. 清除状态重新抓取 - 验证恢复全量抓取
4. 禁用 `stop_on_known` - 验证可以继续全量抓取

## 后续任务

下一个任务是 RWB-AUTO-002-04: 强化反爬虫和重试策略。
