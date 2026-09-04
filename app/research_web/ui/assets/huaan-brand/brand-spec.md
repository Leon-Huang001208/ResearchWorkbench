# AlphaFoundry 图案资产与视觉基线

- 资产：[用户原图](source-logo.png)，211×239；SHA256 `bcb4aaff2e6c11912389148f11886412c624f585252806887dc057d94c6e78b6`。
- 仅显示图案：原图 x51/y22、108×120 区域，以 27×30 CSS 视口显示；中英文商标文字不显示，不重绘。
- Light 保留原蓝色；Dark 使用灰度、反色、亮度和 screen 混合显示白色图案，无底板。此规则以用户后续确认优先。
- 正式引用：shell.mjs 的 `<img src="/static/assets/huaan-brand/source-logo.png">`，appearance.css 管理裁切与两种模式。
- 布局：已批准的独立 codex-research-v2 样品；正式截图在 outputs/research-web-appearance/live/。数据保持真实，不复制样品占位。
- 字体：系统字体/PingFang；16px 正文、32px 首页标题、4/8px 间距、8/10/16px 圆角。Light 白/暖灰，Dark 暖炭黑；语义变量见 appearance.css。
- 产品仍名为 AlphaFoundry；不声明与原图机构存在授权关系。无新增外部图片、字体或网络依赖。
