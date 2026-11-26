# Web UI 语义色角色与颜色预算

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造（承接 #347 的设计尺度）。

Product-Progress: not-required — 本次只把既有色值收编为语义 token，替换值与原值逐项相同，未改变任何页面的视觉或交互。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在既有 tokens.css 内增加语义色角色，并替换样式表里的等价字面值；模块划分、路由与渲染不变。","diagrams":[]} -->

## 问题

#347 建立了间距与字号尺度，颜色仍是 170 处裸字面值（130 个唯一色），
其中涨跌色 `#d94747` / `#1f9d70` 各重复 3 次，浅蓝底 `#f9fbfe` / `#f8fbff`
几乎相同却各写各的。改主题时无法收敛。

统计时排除了两类**不是**问题的写法：`:root` 中的 token 定义本身，
以及 `var(--line, #343430)` 这类带 fallback 的正常消费。

## 实现

- `tokens.css` 新增语义色角色：状态（success/warning/danger/info 及各自
  bg / line）、涨跌方向（`--color-up` / `--color-down` 及 soft）、
  表面层级（elevated / sunken / overlay / well / wash / wash-strong /
  selected-wash 及对应边框）、焦点环，以及三档阴影。
- **涨跌方向与状态色刻意分离**：`--color-up` 不引用 `--color-danger`，
  这样"A 股红涨"与"危险"可以各自调整，不会互相绑架。
- `styles.css` 迁移涨跌色 6 处、表面色 7 类共 6 处，裸色 170 → 158。
- `check_ui_tokens.mjs` 扩展为同时检查裸 px 与裸色，两套预算均只减不增。
- `research_web_tokens.test.mjs` 增加语义角色存在性与颜色预算断言。

## 验证

真实浏览器（Chrome / 本机 loopback）：`--color-up`→`#d94747`、
`--color-down`→`#1f9d70`、`--color-well`→`#f9fbfe` 正确解析，
值与改动前逐项相同，**控制台 0 错误**。

离线：`research_web_tokens` 4 项通过；`research_web_appearance` +
`research_web_ui` + `research_web_asset_chart` 134 项通过。
`check_ui_tokens` PASS（px 6502/6502，colour 158/158）。

## 未验证

未做逐页像素截图比对（替换值逐项等价）。剩余 158 处裸色分布在
`styles.css`(120)、`appearance.css`(19) 等，多数为一次性深浅变体，
需要按语义归并后继续迁移；`app.mjs`（3923 行）拆分仍未开始。
