# Research Web 外观与主题

本页记录 2026-09-03 经用户确认的 Codex 风格正式 Web 外观，取代旧深蓝顶栏和双侧栏视觉方案。属于 **Redesign · Preserve**：改变布局和视觉，保留研究控制器、原生 DSH、路由、审批与下载契约。不引入原型脚本、演示目录或新的后端。

## 当前实现

| 模块 | 职责 |
| --- | --- |
| `app/research_web/ui/index.html` | 在样式加载前初始化主题；随后加载原组件样式和外观覆盖层 |
| `theme.js` | Light / Dark / System 偏好、本机系统变化、跨标签同步、存储失败降级 |
| `appearance.css` | 中性色语义变量、单列导航、研究画布、抽屉、数据目录网格/来源矩阵、可选研究面板与品牌符号呈现 |
| `shell.mjs` | 同一导航列中组合产品入口与会话区；保留设置入口与符号 Logo |
| `app.mjs` | 使用真实研究数据组合页面；仅打开时显示活动/资料/文件面板；重渲染同步主题控件 |
| `composer.mjs` / `capabilities.mjs` | 采用样品的紧凑入口、输入工具栏和三列能力卡；保留全部版本、输入与格式契约 |
| `icons.mjs` | 复用 v2 静态线性控件图标，未知名称安全回退；不解析外部 SVG |
| `core.mjs` / `views.mjs` | 继续维护原研究契约，不迁入设计原型的控制器或模拟数据 |

研究 API、存储和执行拓扑未变，架构图不需要虚构新的服务节点。主题是浏览器独立表现模块，不进入会话、Skill、DSH 或数据集。当前架构核对记录须识别本页和新增 `theme.js`、`appearance.css`。

## 布局和设计系统

- 桌面单列 256px 导航：顶部 AlphaFoundry、新研究和搜索，其下产品入口、真实运行任务/最近会话，底部仅保留设置。外观选择位于设置页；折叠后保留 72px 可操作导航。
- 能力中心数据页在宽屏使用五项汇总、三列目录卡和来源矩阵；中等窗口依次收为三列/两列，手机为两列汇总与单列卡片。就绪状态颜色只表示对应维度，不把“代码存在”装饰成“可调用”。
- ≤1050px 导航变为抽屉；活动/资料/文件是另一独立抽屉。桌面研究面板按需展开，默认不占用聊天宽度。
- FinGPT 和 Claw 首页使用最大 800px、左对齐的标题与编辑器（会话正文最大 820px）。附件、能力、输出格式与真实模型放在同一桌面工具栏，窄屏自然换行；首页四列入口、Claw 两列模板，能力中心三列紧凑卡片。能力入口继续来自 DSH 已保存目录。能力卡只带入草稿，不自动发起研究。
- 字体采用系统字体、PingFang；正文 16px、主标题 32px，4/8px 间距、8/10/16px 圆角。微交互 150ms，遵循减少动态效果偏好。
- Light：白色画布、暖灰侧栏、深色操作按钮；Dark：暖炭黑画布、浅色文字与操作按钮。错误、审批警告、成功分别保留语义颜色。

## 品牌资产（brand-spec）

资产为用户提供图片的原始字节，位置：`app/research_web/ui/assets/huaan-brand/source-logo.png`，SHA-256 `bcb4aaff2e6c11912389148f11886412c624f585252806887dc057d94c6e78b6`。

不重画、生成或修改源图。显示时裁切原图 x=51、y=22、宽108、高120的图案区域，排除“华安基金 / HUAAN FUNDS”文字。浅色模式保留原蓝色，深色模式使用 CSS 灰度、反色和亮度变换呈现白色图案；混合模式去除源图白底，不加白色底板、边框或徽章。AlphaFoundry 名称仍是产品名称，不声明与原图品牌的机构关系。

## 状态与安全

| 状态 | 语义 |
| --- | --- |
| 默认、hover、active | 由各主题语义变量控制，轻微底色变化 |
| focus | 清晰焦点环；原 skip link 和可访问标签保留 |
| disabled / loading | 保持控制器禁用行为；灰色且不被 hover 覆盖；不清空草稿 |
| danger / warning | 取消仍走原接口；审批说明、失败详情保持有色提示和可读正文 |
| 系统变化 | 仅 System 模式跟随；手动 Light/Dark 不被系统覆盖 |
| 浏览器存储失败 | 当次仍能切换；记录固定事件名，不因 localStorage 抛错阻断初始化 |
| 刷新 / 重渲染 | 刷新恢复外观偏好；SSE 页面重绘后控件同步当前偏好；切换不重启研究 |

唯一新持久浏览器值为 `alphafoundry.research.appearance.v1`，只允许 `light/dark/system`。不保存凭据、正文、用户文件或研究结果。前端日志仅固定事件名；验证程序将检查结果写入 `logs/research-web-appearance-*.json`。

## 验证入口

```bash
DSH_SOURCE_ROOT=/path/to/deepseek-harness node --test tests/javascript/research_web*.test.mjs
node --check app/research_web/ui/theme.js
node --check app/research_web/ui/app.mjs
node tests/e2e/research_web_appearance.mjs
node tests/e2e/research_web_appearance.mjs --live
```

浏览器检查需要本机已有 Playwright Core 和 Chrome，可通过 `PLAYWRIGHT_CORE_PATH`、`CHROME_PATH` 指定位置；不会安装依赖。默认模式仅将独立工作区静态文件覆盖到新建的测试浏览器，API 仍只读真实本地服务；`--live` 不覆盖静态文件，用于合入后验证正式 Web。所有非 GET/HEAD 及非本地请求被拒绝。不会触碰用户浏览器、提交模型请求、审批、停止任务或重启运行时。

## v2 样品还原核对

视觉基线为用户指定的 `codex-research-v2/index.html#fingpt`（本机 2026/09/03 的独立样品），不是 AlphaEngine 的旧双侧栏稿。第一轮仅替换配色仍保留了居中 Hero、大段卡片元数据和顶栏搜索，用户指出差异后已按样品重排。

在 1440×1000 下，样品标题起点 (448,214)、编辑器 (448,317.1875,800,162)、四卡起点 y=534.6875、高94px。正式页面新增几何回归，关键坐标/高度容差2px；这不是整页逐像素一致声明。实际会话、模型、能力名称/状态和审批不能复制预览占位内容。Dark Logo 以用户后续“白色图案”指令覆盖早期样品白底板。

浏览器修复回归记录：输出格式弹层样式必须限定 `.composer .format-options`，不得覆盖能力编辑器的同名常规字段；折叠按钮与设置入口同在导航 footer，避免不同层叠上下文遮住点击。

证据输出：`outputs/research-web-appearance/{isolated,live}/verification.json` 和同目录截图。实际结果在本轮 `.ai/reports/2026-09-03-research-web-appearance.md` 记录；这里的命令与状态要求不等同于已通过声明。
