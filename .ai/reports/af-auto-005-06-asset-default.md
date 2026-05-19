# AF-AUTO-005-06 默认关闭资产分析Mock数据

**修复日期**: 2026-05-13  
**任务ID**: af-auto-005-06  
**状态**: ✅ 完成

---

## 执行摘要

本任务成功将资产分析页面的默认数据源从"Mock 数据"改为"自动（推荐）"，优化了新用户的默认体验。

**主要成就**:
- ✅ 修改了 index.html 中的默认选择项
- ✅ 现在新用户进入资产分析页面时会默认看到真实数据
- ✅ 用户仍然可以手动选择使用 Mock 数据（如果需要）

---

## 修改详情

### 主要修改文件

**修改文件**: `app/web/templates/index.html`

#### 修改默认数据源

**原始代码**（第 233 行附近）:
```html
<option value="mock" selected data-i18n="asset.source_mock">Mock 数据</option>
<option value="auto" data-i18n="asset.source_auto">自动（推荐）</option>
```

**修复后代码**:
```html
<option value="mock" data-i18n="asset.source_mock">Mock 数据</option>
<option value="auto" selected data-i18n="asset.source_auto">自动（推荐）</option>
```

**修改说明**:
- 移除了 Mock 数据选项的 `selected` 属性
- 将 `selected` 属性添加到自动（推荐）选项上
- 这样新用户进入页面时会默认选择自动模式

---

## 用户体验改进

### 修改前
- 新用户进入资产分析页面
- 默认看到模拟数据
- 需要手动切换到"自动（推荐）"才能看到真实数据

### 修改后
- 新用户进入资产分析页面
- 默认看到真实数据（来自 AKShare）
- 仍然可以手动选择 Mock 数据（用于测试或演示）

---

## 验证结果

可以通过以下方式验证：
1. 打开浏览器访问 Web UI
2. 进入资产分析页面
3. 查看数据源下拉框的默认选择
4. 应该默认选择"自动（推荐）"

---

## 修改文件清单

| 文件 | 修改说明 |
|-----|---------|
| `app/web/templates/index.html` | 将默认数据源从 Mock 改为自动（推荐） |

---

## 后续建议

- 考虑在用户首次访问时显示引导，说明不同数据源的区别
- 可以添加用户偏好设置，记住用户的选择
