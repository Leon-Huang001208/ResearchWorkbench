# 数据源连接操作：收敛四个分支

宿主为 Mac mini 本机 macOS，类型为 Research Web 前端可维护性改造。

Product-Progress: not-required — 本次只把连接管理相关分支移入独立模块，行为与界面均未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"四个分支仍由同一 click 监听器触发，实现移入同目录模块；部署、依赖方向、路由与渲染时序不变。","diagrams":[]} -->

## 问题

`app.mjs` 的 click 监听器里，移除数据源、切换自动检测许可、执行探测、验证授权
四个分支共 55 行，各自重复同一形状：解析来源标签 → 确认风险方向 → 走共享 action
包装器 → 刷新目录与详情 → 给出稳定提示。

## 实现

- 新增 `source-connections.mjs`，导出 `sourceLabel`、`sharedImpactNote` 与
  `createSourceConnections({...})`。
- 四个方法：`remove`、`setConsent`、`probe`、`verifyAuth`。
- 复用 `connections.mjs` 既有的 `confirmAutoProbeConsent`——启用与停用**都需要确认**，
  这是原有行为，未改。
- `connectionProbeBusy` 与 `selectedConnectionConfiguration` 有了单一归属，
  不再散落在分支里手工置位。
- `app.mjs` 该四处由 55 行降为 19 行；文件 3886 → 3868。

## 一个需要说明的测试改动

既有测试 `research_web_ui.test.mjs` 通过**读取 app.mjs 源码文本**来断言
`current.health === 'healthy'` 与知丘共享提示存在。逻辑移走后该断言失效。

处理方式不是删断言，而是把断言的**对象**改到新模块，并额外断言 dispatcher 仍在调用
`sourceConnections.probe(`——这样既保住原意，也验证了委托关系成立。

## 验证

真实浏览器：`source-connections.mjs` 200 加载，107 个模块全部成功，
**0 个 404、控制台 0 错误**，`#app` 正常填充，28 个导航项可见。

离线：新增 12 项通过，覆盖标签回退、知丘共享提示仅对该来源生效、
删除后清空选择并刷新三份目录、取消确认不触网、同意取反当前值、
探测健康与不健康两种提示、无有效任务 id 时失败而非空轮询、
授权交换与数据权限的措辞区分、失败时释放 busy 并记录稳定码。
既有 175 项通过。`check_ui_tokens` 预算未变。

## 未验证与后续

未对真实 Wind／知丘等来源执行删除或探测（会改动本机凭据与外部调用，需单独授权）。
`connectionGroup`、`localIntegrationsProbe` 等分支仍在监听器内，可继续按同样模式处理。
