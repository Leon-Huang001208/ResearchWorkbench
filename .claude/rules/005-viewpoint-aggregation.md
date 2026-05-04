---
path: "wikis/*/wiki/entities/**/*.md"
---

# 强制规则：观点必须按时间分组显示

## 要求

所有 Wiki 实体页面中的"观点汇总"部分，**必须按时间分组显示观点**（最新在最前）。

## 格式规范

### 正确格式（按时间分组）

```markdown
## 观点汇总

### 看多

#### 2026-04-21（最新）

##### [[机构名称]]

**来源：[[来源页面]]**
- 观点一
- 观点二
- 观点三

#### 2026-04-19

##### [[机构名称]]

**来源：[[来源页面]]**
- 观点一

### 看空

#### 2026-04-20

##### [[机构名称]]

**来源：[[来源页面]]**
- 观点一
```

### 错误格式（按机构分组）

❌ **不要使用这种格式：**
```markdown
## 观点汇总

### 看多

#### [[机构名称]]

**来源：[[来源页面]]（YYYY-MM-DD）**

- 观点一
- 观点二
```

## 使用工具转换

如果遇到旧格式的页面，使用观点聚合工具进行转换：

```bash
# 转换单个文件
python scripts/reaggregate_viewpoints.py --file "wikis/global-market/wiki/entities/..."

# 转换整个目录
python scripts/reaggregate_viewpoints.py --dir "wikis/global-market/wiki/entities/..."

# 转换所有实体页面
python scripts/reaggregate_viewpoints.py --all --wiki global-market
```

## 检查清单

在写入或修改观点汇总部分时：

- [ ] 观点按时间倒序排列（最新在最前）
- [ ] 第一个日期标注"（最新）"
- [ ] 日期层级使用 `#### YYYY-MM-DD`
- [ ] 机构层级使用 `##### [[机构名称]]`
- [ ] 来源标注使用 `**来源：[[来源页面]]**` 格式
- [ ] 使用 `reaggregate_viewpoints.py` 工具进行格式转换
