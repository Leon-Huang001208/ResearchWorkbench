# AlphaFoundry 合并平台可点击原型

打开 [index.html](index.html) 即可浏览。原型无需安装依赖，覆盖市场首页、主题研究、资产观察、FinGPT、Claw、自选与提醒、研究库、能力与日程 8 个页面。

页面中的 `CAP-*` 与 `API-*` 标记可回链到 `../merged-platform-blueprint/api-atlas.html`。底部旅程控制器提供 5 条端到端产品旅程；原型设置可切换加载、空、部分、过期、不可用、隔离、错误、无权限和 Runtime 阻塞状态。

FinGPT 的研究输入会进入当前原型 Session 状态并显示在 Run 页面，用于验证“输入 → 运行中”交互不会被示例问题覆盖；刷新页面后该纯静态原型会重置状态。

所有行情与指标均为带“演示状态”标记的布局样例，不代表实时数据或投资建议。生产实施映射见 `docs/architecture/merged-platform/product/prototype-map.md`。
