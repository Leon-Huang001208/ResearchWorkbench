# Wiki Framework Schema（框架基础模板）

This document defines the **base schema** for the Wiki Framework.

Each Wiki instance should define its own schema in `wikis/{name}/.claude/SCHEMA.md` to extend or override this base schema.

---

## Core Principles（所有Wiki共享）

1. **The wiki is persistent, compounding knowledge** - every new source should update existing pages, not just add new ones
2. **Cross-reference everything** - use [[WikiLinks]] liberally to connect related concepts
3. **Keep the index current** - update `index.md` on every ingest
4. **Log everything** - append to `log.md` for every operation
5. **Raw sources are immutable** - never modify files in `raw/`, only read from them

---

## Base Directory Structure（框架推荐结构）

```
wiki/
├── index.md          # Master index (you maintain this)
├── log.md            # Chronological log (you append to this)
├── entities/         # Entities
├── topics/           # Topic synthesis pages
└── sources/          # Source summary pages (one per source)
```

---

## Required Page Types（框架要求的页面类型）

### 1. Source Summary Page (`wiki/sources/`)

**Filename format**: `YYYY-MM-DD-{source}-{title}.md`

**Minimum Frontmatter**:

```markdown
---
title: "页面标题"
date: YYYY-MM-DD
source_type: [pdf|webpage|manual|...]
---
```

### 2. Index Page (`wiki/index.md`)

**Purpose**: Master index of all pages in the wiki.

**Minimum Content**:

```markdown
# {Wiki Name} 索引

> 最后更新: YYYY-MM-DD

## 统计概览

- 来源页面: N
- 实体页面: N
- 主题页面: N

## 分类索引

### 来源

- [[来源页面1]]
- [[来源页面2]]
```

### 3. Log Page (`wiki/log.md`)

**Purpose**: Chronological log of all operations.

**Minimum Entry Format**:

```markdown
## [YYYY-MM-DD HH:MM] {operation} | {summary}

- 操作: {operation}
- 结果: {brief description}
```

---

## Base Conventions（所有Wiki共享）

- **Dates**: Use `YYYY-MM-DD` format everywhere
- **WikiLinks**: Use `[[Page Name]]` format, match exact filenames
- **Frontmatter**: All pages must have YAML frontmatter with at least `title` and `date`

---

## See Also

- For **global-market** Wiki specific schema, see: [wikis/global-market/.claude/SCHEMA.md](../../wikis/global-market/.claude/SCHEMA.md)
- For creating a new Wiki instance, refer to the [Framework Guide](../docs/FRAMEWORK-GUIDE.md)
