# 正式 Research Web 外观合入与 v2 保真校正

## 结果与边界

- 日期：2026-09-03；侧对话用户明确批准合入，目标 `codex/dsh-web-v1`，基线 `30748f7`。主仓库未覆盖、未进行分支切换或远端发布。
- 正式入口：http://127.0.0.1:8088/#/fingpt 。使用已有服务，不重启 Web/DSH，不改模型配置、审批、数据或历史。
- 采用已批准 codex-research-v2 样品结构，而非仅替换主题：左对齐首页、800px 编辑区、单行桌面输入工具栏、四列快捷入口、单一256px导航、三列紧凑能力卡。
- Logo 用用户原图裁切图案；Light 蓝，Dark 白，无机构文字或底板。支持 Light/Dark/System，偏好只存浏览器。
- 数据、版本、来源与错误仍是真实状态；不复制样品的预览说明、虚拟会话、固定产物或占位工具。

## 源码—证据映射

| 源码 | 改动 | 测试/文档 |
| --- | --- | --- |
| ui/index.html、theme.js、appearance.css | 主题预加载、隔离偏好、样品布局与响应式 | appearance.test.mjs；浏览器外观检查；research-web-appearance.md |
| ui/assets/huaan-brand/source-logo.png、brand-spec.md | 原始品牌图案与呈现规则 | 原字节SHA256、两种主题截图与CSS断言 |
| ui/shell.mjs、icons.mjs | 新研究/搜索/标题、线性图标、主题与面板 | ui_layout、capabilities_ui、appearance测试及真实只读页面 |
| ui/app.mjs、composer.mjs、capabilities.mjs | 首页/输入栏/紧凑卡片组合，保留选择器与控制器 | 同上；实际弹层、编辑器、历史面板操作 |
| docs/research-web-ui.md、research-web-appearance.md、CHANGELOG.md | 当前实现与样品差异说明 | 文档同步与架构一致性门禁 |
| docs/architecture/research-web/{README.md,architecture-map.json,review-record.md} | 入口、源码—测试映射、拓扑不变理由 | check_research_architecture.mjs |

测试文件：tests/javascript/research_web_appearance.test.mjs、research_web_ui_layout.test.mjs、research_web_capabilities_ui.test.mjs；tests/e2e/research_web_appearance.mjs。源码路径前缀为 app/research_web/。

## 实际验证

1. `DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`：最后一轮128通过、0失败、0跳过，1967.668916ms（终端使用pipefail与tail仅缩短输出）。
2. `node tests/e2e/research_web_appearance.mjs --live`：31检查通过、27截图、7420ms；真实静态文件与只读API，0浏览器异常、0非GET/HEAD请求。1440/1600/1920/820/390、两种主题，覆盖五页面、能力详情、未保存Workflow编辑器、全局搜索/Escape、格式选择、完整能力选择器、侧栏折叠及真实会话活动/资料/文件。
3. `node --check` 分别检查 app.mjs、shell.mjs、composer.mjs、capabilities.mjs、icons.mjs、theme.js：通过。`git diff --check`：通过。
4. `node scripts/check_research_architecture.mjs --project . --base 30748f7`：零违规。
5. `python scripts/check_doc_sync.py --project . --base 30748f7`（使用现有venv）：退出0，Research Web架构门禁通过；旧Python-only检查无相关源码。
6. `node .agents/project-constraints.mjs --project .` 携带上述20项实际源码/测试/文档的 `--changed-file`：零违规。
7. Harness：最终硬门结果由同任务 task-7ac1c94b 的验证事件记录，不以文档声明替代门禁。

## 保真基线与人工检查

原样品截图：outputs/research-web-appearance/prototype-light-fingpt.png。最终正式截图及JSON：outputs/research-web-appearance/live/；日志 logs/research-web-appearance-live.json。

1440×1000样品：标题起点(448,214)；编辑器(448,317.1875,800,162)；四卡y=534.6875、高94。正式Light/Dark新增几何断言均在2px内。只证明这些关键布局，不宣称所有文字、实时数据和像素完全一致。

人工实际查看：样品浅色、正式浅色FinGPT/能力中心、深色FinGPT/能力中心、390手机、Workflow编辑器等。主内容层级、品牌图案、输入和卡片密度已对齐。正式动态数据与样品占位不同是必要差异。

## 失败与修复记录

- 初次合入仅套用主题仍保留旧Hero与长卡片：用户反馈后按v2重组，并先新增失败的结构断言。
- 格式弹层CSS误影响能力编辑器同名class，引发手机溢出：收窄为 `.composer .format-options` 后原条件重验通过。
- 折叠按钮跨层叠上下文被设置入口遮挡：移至同一导航footer后真实点击通过。
- 旧测试假定英文装饰标题、所有子节点不得aria-hidden、折叠按钮固定在二级栏：改为检验实际目录、aside可访问性及当前footer入口；未放宽运行/文件测试。
- 曾执行无DSH_SOURCE_ROOT的一轮为127通过/1跳过；最终有该变量的128通过覆盖原生schema。
- 首次 `project-constraints --help` 不受支持；读取CLI参数后以实际changed-file列表运行通过。一次大型CHANGELOG全文件补丁因读取截断被拒绝，未覆盖文件；改用小范围上下文补丁。
- failure.png为修复前调试留档，不是最终效果；最终JSON明确枚举27张有效截图。

## 未验证与保留项

- 未重新发送模型任务、取数、上传、批准/拒绝或停止任务；真实模型与沙箱全旅程沿用既有基线，不能将本轮只读UI检查说成新模型验收。
- 未运行Python全套（无Python改动）、屏幕阅读器、Safari/Firefox或桌面/Windows验证。八张架构图拓扑未改变，未重画图或伪造图形检查回执。
- 未改原型、未发布/推送。未触碰原有未跟踪 outputs/research-web-ui-acceptance/pdf-live/dsh-report.pdf。
