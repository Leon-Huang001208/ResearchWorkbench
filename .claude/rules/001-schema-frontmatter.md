---
name: Schema Frontmatter 强制约束
description: 所有 Wiki 页面必须包含 SCHEMA.md 中定义的 YAML Frontmatter
---

# 强制规则：Wiki 页面必须包含 YAML Frontmatter

## 适用范围

当你在 `wiki/` 目录下创建或修改任何 `.md` 文件时，必须遵守此规则。

## 要求

**所有 Wiki 页面必须在文件开头包含 YAML Frontmatter**，格式参考 `.claude/SCHEMA.md` 中的定义。

### 最小必需 Frontmatter

```markdown
---
title: "页面标题"
date: YYYY-MM-DD
---
```

### 根据页面类型的不同，还应包含相应字段

#### 来源摘要页 (`wiki/sources/`)
```markdown
---
title: "机构名称：标题"
date: YYYY-MM-DD
source_type: [pdf|webpage|cls|zq|cnstock|json|manual]
source_path: raw/pdfs/filename.pdf
tags: [tag1, tag2]
---
```

#### 个股实体页 (`wiki/entities/个股/`)
```markdown
---
title: "股票名称"
ticker: "600000.SH"
sector: "行业"
first_seen: YYYY-MM-DD
last_updated: YYYY-MM-DD
source_count: 0
---
```

## 检查清单

在写入任何 Wiki 页面之前，请确认：

- [ ] 文件以 `---` 开头
- [ ] 包含 `title` 字段
- [ ] 包含 `date` 字段（格式：YYYY-MM-DD）
- [ ] Frontmatter 以 `---` 结束
- [ ] Frontmatter 之后有空行
- [ ] 页面类型对应的特定字段已包含（如适用）

## 违反处理

如果发现 Wiki 页面缺少 Frontmatter，立即停止操作并：
1. 先读取 `.claude/SCHEMA.md` 了解完整规范
2. 为页面添加正确的 Frontmatter
3. 然后再继续后续操作
