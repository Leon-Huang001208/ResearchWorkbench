# frameworks/embeds — 内嵌研究项目静态资产

本目录收录并入本仓库的独立研究项目，全部由后端以同源静态文件方式挂载在
`/frameworks-embed/<slug>/`，前端框架中心（`#/frameworks`）通过 iframe 嵌入展示。
不依赖任何本地路径、外部 IP 或额外 dev server，随仓库部署即可公网使用。

## 目录清单

| slug | 来源项目 | 类型 | 说明 |
| --- | --- | --- | --- |
| gold | Goldar 黄金研究框架 | 静态前端 + 数据快照 | `index.html`、`app.js`、`styles.css`、`assets/` 与 `data/` 均在仓库中，资源使用相对路径 |
| dollar | Dollar 美元流动性研究框架 | Vite 构建产物 + JSON 快照 | `assets/` 与 `api/*.json` 均在仓库中，页面请求当前快照 |
| ainvest | AInvest AI 产业链雷达 | 静态 + vendored JSON API | 前端静态文件；原后端 `/api/*` 响应已离线抓取为 `api/*.json`（含 `api/node/<id>.json`、`api/topic/<id>.json`），`app.js` 的 `apiUrl` 已改为请求 `<path>.json` |
| memory-chips-60 | 存储芯片60年 | 纯静态 | echarts 已本地化为 `assets/echarts.min.js` |
| elnino | 厄尔尼诺 | 纯静态 | 自带本地 echarts |
| model-hardware-chain | 模型如何催化硬件产业链 | 纯静态 | 数据在 `data/` |
| inference-chips-42 | 推理芯片42年 | Vite 构建产物 | 见下方构建说明 |
| bond-framework | 债市分析框架 | Vite 构建产物 | 同上 |
| gold-cycle | 黄金大周期研究框架 | Vite 构建产物 | 同上 |
| fund-track-selection | 如何通过赛道选基金 | Vite 构建产物 | 同上 |
| ai-economy | AI如何改变经济与市场 | Vite 构建产物 | 仅前端（`npx vite build`，不含其 Hono 后端） |

## Vite 项目重建方式

1. 复制源码到构建目录，删除 vite.config.ts 中 `kimi-plugin-inspect-react` 的 import 与插件引用。
2. `vite.config.ts` 设置 `base: '/frameworks-embed/<slug>/'`。
3. `src/main.tsx` 的 `<BrowserRouter>` 改为 `<BrowserRouter basename={import.meta.env.BASE_URL}>`（否则子路径下路由不匹配、页面空白）。
4. 若 `package-lock.json` 的 resolved 指向不可达镜像（如 npm.mirrors.msh.team），批量替换为 `https://registry.npmjs.org`。
5. `npm ci && npm run build`（lockfile 过期时先移除 package.json 中残留依赖再 `npm install`），把 `dist/`（ai-economy 为 `dist/public/`）同步到本目录对应 slug。

## 服务端接线

- `app/research_web/main.py`：`app.mount("/frameworks-embed", StaticFiles(directory=..., html=True))`，并为该前缀下发允许同源 iframe 的 CSP（`frame-ancestors 'self'`，放开 jsdelivr / Google Fonts）。
- `app/research_web/frameworks/registry.py`：`_register_embedded` 注册 11 个内嵌框架元数据，`external_app.url` 指向同源路径。
- `app/research_web/ui/frameworks/embedded.mjs`：详情页 iframe 渲染。

## 当前运行边界

详情页直接加载看板，框架名称显示在产品顶栏；外层只保留返回与新标签页入口。
运行时无需访问来源项目的本机目录。卡片的覆盖率表示嵌入资产元数据，不代表实时数据覆盖率。

Goldar、Dollar 和 AInvest 当前保留导入时的数据快照。原项目的后台采集任务、
动态代理接口和模型评分任务未随静态资源迁入。Dollar 的 `api/refresh.json`
返回 `started: false`，不会启动新的采集；Goldar 的动态 Goldhub 接口也尚未迁入。
原页面中描述定时更新的文字来自来源项目，不作为本项目已经实现后台更新的证据。
后续接入采集必须使用本项目的服务端配置与仓库内实现，不能依赖开发机器路径。
