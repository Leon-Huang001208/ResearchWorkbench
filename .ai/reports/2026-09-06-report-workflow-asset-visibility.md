# 报告 Workflow 与资产观察可见性修复

## 用户可见结果

- Claw 首页显示 4 个真实报告 Workflow：创业板50周报、华安ETF周报、华安ETF投资风向标、AI周报。
- 能力中心 Workflow 页可查看每个报告的发布版本、模板、Excel 底稿、Provider、报告区块、日程和历史产物。
- 顶栏搜索可检索报告 Workflow，并打开真实版本包详情，不再误走通用 Skill 选择逻辑。
- 资产观察作为主导航独立入口 `#/workbench/assets`，不再藏在研究台中。
- 资产页保留概览、行情、财务、交易事件、公告、新闻、研报、自选、笔记、提醒、来源口径及 FinGPT/Claw 交接；没有真实数据的区块明确显示不可用。

## 数据迁移证据

- 运行目录：`~/.research-workbench/research-web/report-workflows/`，当前约 107 MiB。
- 迁移来源：已管理的 `~/.research-workbench/research-web/report-projects/`。
- 4 个项目、34 个资源、323 个历史产物索引；第二次 apply 全部返回 `already_present`。
- 创业板50周报、华安ETF周报、华安ETF投资风向标为 enabled v1；AI 周报因资源不完整保持 `needs_attention`。
- 迁移不运行模板脚本，不跟随链接，不覆盖母版；历史文件只索引。

## 验证

- JavaScript：149 项，148 通过、1 项可选 DSH schema 跳过、0 失败。
- Python Research Web：400 通过、3 跳过，只有 Starlette 已知弃用警告。
- 浏览器：Claw 实际目录、创业板50周报详情和资产观察均已打开检查；console 无错误。
- 缺失行情不再被 JavaScript 转成 0；52 周高低等指标显示 `—` 并有回归测试。
- 截图：`output/playwright/claw-report-workflows-final.png`、`output/playwright/asset-observation-final.png`。
- Archify 图 02：showcase 9/9、0 error、0 warning；1440×900、1600×1000、1920×1080、2048×1320 均无溢出，已人工查看 1440 浅色和 2048 深色。

## 尚未宣称完成

- 本轮没有点击运行真实周报，避免未经确认消耗模型或触发 Excel 插件；因此没有宣称 Wind/iFinD 已登录或本次报告已生成。
- 资产页当前观察的 600519 中，财务区块有真实 AKShare 数据；行情、公告、研究资料等不可用状态仍需相应 Provider 数据接通，页面没有用示例值补齐。
- `report-projects` 后端兼容 API 暂时保留用于旧运行读取，新产品没有独立报告工作室入口；最终清理前需在已迁移历史读取完成后删除兼容层。
