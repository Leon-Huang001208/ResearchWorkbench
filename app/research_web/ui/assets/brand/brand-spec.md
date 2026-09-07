# Research Workbench 图案资产与视觉基线

- 原始资产：[用户原图](source-logo.png)，211×239；SHA256 `bcb4aaff2e6c11912389148f11886412c624f585252806887dc057d94c6e78b6`。该文件只作保留和可复核的来源，绝不修改或重新编码。
- 正式渲染资产：[透明派生图案](brand-mark.png)，从原图固定裁切 x=51、y=22、108×120 区域而来；输出为 108×120 RGBA PNG。白色与近白色底已转为透明，边缘去除白色杂边；中英文商标文字不显示，也不重绘图案。
- Light 直接显示派生资产的蓝色非透明像素；Dark 使用 `brightness(0) invert(1)` 显示白色非透明像素。两种主题都没有矩形底板、混合模式、边框或徽章。
- 正式引用：shell.mjs 的 `<img src="/static/assets/brand/brand-mark.png">`，以 108×120 固有尺寸声明；appearance.css 将其直接填满 27×30 CSS 显示视口。
- 布局：已批准的独立 codex-research-v2 样品；正式截图在 outputs/research-web-appearance/live/。数据保持真实，不复制样品占位。
- 字体：系统字体/PingFang；16px 正文、32px 首页标题、4/8px 间距、8/10/16px 圆角。Light 白/暖灰，Dark 暖炭黑；语义变量见 appearance.css。
- 产品仍名为 Research Workbench；不声明与原图机构存在授权关系。无新增外部图片、字体或网络依赖。
