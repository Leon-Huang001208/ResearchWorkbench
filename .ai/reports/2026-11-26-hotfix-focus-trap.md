# 紧急修复：master 上 trapTabFocus 未定义

宿主为 Mac mini 本机 macOS。这是对已合并代码的修复，不是新功能。

Product-Progress: not-required — 本次只补回被漏掉的一个模块文件与导入语句，恢复既有行为，无用户可见变化。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"补回 focus-trap.mjs 及其导入，恢复 #357 已声明的调用关系；无新增模块层级或运行拓扑。","diagrams":[]} -->

## 问题

PR #357 把发现抽屉的手写 Tab 焦点陷阱改为调用 `trapTabFocus`，但该函数所在的
`focus-trap.mjs` 属于另一个未合并的 PR（#354）。合并顺序导致 master 出现：

    app.mjs:1939  trapTabFocus(event, root.querySelector('.d-drawer'));

该标识符既无定义也无导入。浏览器实际表现：键盘事件走到该分支时抛
`ReferenceError`，发现抽屉的 Tab 行为失效。首屏仍能渲染，所以冒烟检查不会暴露它。

## 修复

- 补回 `app/research_web/ui/focus-trap.mjs`（与 #354 内容一致）。
- 在 `app.mjs` 补 `import { trapTabFocus } from './focus-trap.mjs';`。
- 补回对应单元测试。

## 验证

真实浏览器：`focus-trap.mjs` 以 200 加载，111 个模块全部成功，
**0 个 404、控制台 0 错误**，`#app` 正常填充，28 个导航项可见。

离线：`research_web_focus_trap` + `research_web_ui` 共 62 项通过。

## 过程反思

我在合并 #357 时只确认了它自己的 CI 通过，没有确认它依赖的文件是否已在 master。
同一批工作的多个 PR 存在依赖关系时，应先合并被依赖的 PR，或在同一个 PR 内完成；
本次按后者补救。
