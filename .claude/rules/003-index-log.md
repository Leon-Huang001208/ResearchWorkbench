---
name: Index 和 Log 更新规范
description: 每次 Ingest 后必须更新 index.md 和 log.md
---

# Index 和 Log 更新规范

## 要求

每次执行 Ingest（摄入新来源）操作后，必须：

1. **更新 `wiki/index.md`** - 添加新页面到索引
2. **追加到 `wiki/log.md`** - 记录操作日志

## index.md 更新

使用 `python scripts/automation.py index` 命令自动生成索引。

## log.md 追加格式

```markdown
## [YYYY-MM-DD HH:MM] ingest | 来源标题

- 操作: ingest
- 文件: raw/pdfs/filename.pdf
- 更新页面:
  - 创建/更新: [[来源页面]]
  - 更新: [[个股A]]
  - 更新: [[概念B]]
```
