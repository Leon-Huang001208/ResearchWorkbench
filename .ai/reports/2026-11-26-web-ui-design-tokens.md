# Web UI 设计尺度与裸值预算

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只建立样式尺度与防漂移预算，所有替换值与改动前渲染值完全相同，未改变任何页面的视觉或交互。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"新增一份 token 样式表并前置于既有组件样式表，模块划分、路由与渲染时序不变。","diagrams":[]} -->

## 问题

用户反馈"调不动风格、加了功能不知道间距该给多少、新加的页面不遵守既有规则"。实测确认这是尺度缺失：

| 指标 | 改前 |
| --- | --- |
| 不同 px 值 | **214 种** |
| 裸 px 声明 | 6506 处（不含 0/1/2/3px 结构值） |
| CSS 变量定义 | 只有 30 个 |
| 硬编码颜色 | 352 处 |
| spacing / 字号 scale | **不存在** |

同一条视觉规则（12px 间距、8px 圆角）散落在数百处独立数字里，改一处不影响其余，
所以任何风格调整都无法收敛。

## 实现

- `tokens.css`：建立 spacing（4px 基）、字号（9–32px 实际步长）、圆角、行高、
  字重、动效与层级尺度。所有数值取自界面已在用的值，**不产生视觉变化**。
- `index.html`：`tokens.css` 前置于 `styles.css`，确保组件样式能消费尺度。
- `scripts/check_ui_tokens.mjs`：裸 px 预算门。现有 23 个样式表按当前数量登记
  （`ui/.token-debt.json`），预算只允许下降；新建样式表出现裸 px 直接失败。
- 试点迁移 `conversation-menus.css`，裸 px 6506 → 6502，并同步收紧预算。
- `research_web_tokens.test.mjs`：锁住 token 存在性、加载顺序与预算不超。

## 验证

真实浏览器（Chrome、本机 loopback）确认 `--space-2`→8px、`--radius-md`→8px、
`--text-sm`→12px 正确解析，`body` 字号仍为 16px，**控制台 0 错误**。

离线：`research_web_tokens` 2 项、`research_web_appearance`+`research_web_ui` 62 项通过。
`check_ui_tokens` PASS（6502/6502）。

## 未验证

未做逐页像素级视觉回归；替换值与原值逐项等价，但未逐页截图比对。
颜色 token 化（352 处硬编码）与 `app.mjs`（3923 行）拆分不在本次范围。
