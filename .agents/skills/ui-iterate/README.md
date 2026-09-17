# UI 迭代

## 触发场景

在既有 `app/research_web/ui/` 或兼容 `app/web/` 原生元素上调整视觉或交互状态，同时需要维持外部可见输入与 DOM 表面时使用。

## 使用方式

阅读同目录 [SKILL.md](SKILL.md) 后执行；先确认目标路由属于当前 Research Web 还是旧兼容工作台，再锁定属性、参数、`data-*`、事件、ARIA、selector 与外部样式契约。Recommended Stack 只代表未来方向，禁止据此框架迁移；未经用户明确授权，不引入 Next.js、React、Vite、Storybook、shadcn 或 Tailwind，也不重构原生 Web。仓库通用规则以根 `AGENTS.md` 为准。

## 交付物

最小变更、状态矩阵、实际验证证据，以及逐项未验证状态和原因。
