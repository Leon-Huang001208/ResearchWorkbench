# Web 静态资源投递：gzip 与 CSS 变量修复

宿主为 Mac mini 本机 macOS，类型为 Research Web 性能修复。本次只改静态资源投递层
与样式词表，不改 API 契约、账号链、数据平面或常驻服务。

Product-Progress: not-required — 本次只压缩传输体积并修正失效的样式变量，未新增或改变任何用户可见的功能、页面结构或交互流程。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"仅在主应用挂载 GZip 响应压缩中间件，路由、Host 边界、账号链与前后端契约均不变。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"只压缩既有静态资源传输并对齐已失效的样式 token；模块划分、路由、渲染时序与组件边界不变。","diagrams":[]} -->

## 发现

现役 UI 入口是 `app/research_web/ui/`（`main.py:88`），不是 `app/web/templates/`。
基线实测：首屏模块图 104 个文件、1841KB 原始，全部明文传输。

## 实现

- `main.py`：新增 Starlette `GZipMiddleware`。Starlette 1.6 已默认排除
  `text/event-stream`，实时 SSE 不受影响。
- `aihot.css`：由外部模块移植而来，用的是那套模块的 `--ink`/`--bg`，本仓词表为
  `--text`/`--canvas`，导致正文继承不到颜色、代码块无背景。改为本仓 token。
- `styles.css`／`appearance.css`：`--red`、`--success`、`--ink` 未定义，分别改指
  `--danger`、`--green`、`--text`。
- `appearance.css`：补 `--accent` 与 `--font-mono` 别名，避免逐一改动 18 处引用。
- `test_static_delivery.py`：锁住 gzip 生效且实测收缩过半，以及任何 `var()` 引用
  不得既未定义又无 fallback。

## 验证

五份最大首屏资源实测：501KB → 116KB（23%）。

离线：`test_static_delivery.py` 4 项通过；`test_api.py` 完整 229 项批次一次 exit 0，
另有一次被中断不计入通过；定向子集 2 项通过。`node --test` 的 `research_web_ui` 52 项、
`research_web_appearance`+`research_web_asset_chart` 82 项通过。`black`／`ruff`／
`isort`／`mypy` 无问题。

## 未验证

未做真实浏览器 LCP/FCP 测量，gzip 收益按传输字节计算。未更新常驻服务。
