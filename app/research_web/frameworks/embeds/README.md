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

- `app/research_web/main.py`：`app.mount("/frameworks-embed", StaticFiles(directory=..., html=True))`，并为该前缀下发允许同源 iframe 的 CSP（`frame-ancestors 'self'`，仅允许本站资源）。
- `app/research_web/frameworks/registry.py`：`_register_embedded` 仅注册九个静态框架；Gold／Dollar 保留原生 store，`framework.display.url` 指向同源路径。
- `app/research_web/ui/frameworks/embedded.mjs`：详情页 iframe 渲染。

## 当前运行边界

Gold／Dollar 核心入口使用本站原生快照与采集链，不读取历史导入 JSON；旧文件仅作来源留档。宿主读取一次快照并向同源 iframe 发送，确认 revision 后允许原生 Bot。新标签页进入宿主详情。回测、策略与模型拟合明确为尚未接入。

其余九套页面保留原静态交互，外层标记 2026-10-14 导入快照，没有实时采集或框架 Bot。导入日期不是各指标观测日期；原页面的定时更新文字不是本站更新能力证明。静态 coverage=0，仅说明本站尚未认证实时数据覆盖。

资源清单和字段映射见本任务报告；原始源码分支保留。运行时无需访问来源项目本机目录，不引入 CDN 或独立服务。

## 资产清单

每行 SHA-256 绑定该目录全部文件的路径、大小与文件哈希清单。旧 Gold／Dollar 导入文件作来源留档，核心入口不读取它们。

| slug | 文件数 | 字节数 | 清单 SHA-256 |
| --- | ---: | ---: | --- |
| ai-economy | 5 | 458516 | f29356dff1cac26c3b28b78121a4df22a1cfb7966b8497748be641fa432d76bf |
| ainvest | 304 | 2277635 | 4abe58c6adbc120f0173d9221ce39442cb94734cdd9132c2418aed4b5e23029b |
| bond-framework | 3 | 1547871 | 7162d66993d6de3e49adc2a38357f9c048c3563647cb8b28facaa2cb7aeebc9a |
| dollar | 18 | 14254463 | de21a8cb27b8127accf792f3cb73e6772a5736764b959e2941608a360d5095f7 |
| elnino | 8 | 3127345 | 050fdd755b15dc523a5a80befaa5fcbabf9e12981b3561d6d94ce2c498303987 |
| fund-track-selection | 3 | 353045 | b030a274dbbcff520867d8f4b405bae8750809a4cea5b285a04745cc7d086747 |
| gold | 30 | 16835958 | 6dd03e277cb498689f78acd049eb50cea12f765d566f22dba396940e5d9ec39f |
| gold-cycle | 3 | 1646759 | 1ae4a22239d8c33237462e02fdac0e436c7cdcb4afbb026f6852490cf7af2c3d |
| inference-chips-42 | 3 | 822561 | 0c9d8ba9207e5362ca14a6a231e619569f778c413edf02e39556ba60e3a611e5 |
| memory-chips-60 | 6 | 1117259 | e19e0ad98f9de3e45358a37bce845e019d94ed3cae273877abdf932b2f48b3b4 |
| model-hardware-chain | 16 | 136170 | 8450b71bb6f4107355d01d1af41c03995c1f36f53eefeb7c96d7119e552f1093 |

### Gold 配置模块的样例边界

Gold 核心入口由宿主原生快照与受控桥接驱动；配置区块目前尚无原生采集/计算链。fixture、missing 和缺少真实来源元数据的配置区块显示“尚未接入”，不渲染旧相关性/情景/配置说明；Bot 采用相同剔除规则。历史和严格快照 API 保留旧区块身份，不加载 vendored JSON 作当前结果，不增加外部资源或 CSP 权限。
