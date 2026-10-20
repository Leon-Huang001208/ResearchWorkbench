# Claw 空态与逐题回答修复

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"复用现有views、questionnaire、app产品壳与原生消息投影，仅修复空态条件、点击区域和焦点，无后端、框架或执行结构改变。","diagrams":[]} -->

- 宿主：macOS arm64；任务：Web 功能修复；不涉及桌面产品。
- 基线：e43088817a68501e42b603f786227811ee4d0c83。
- 分支：codex/claw-empty-question-20261020-claw-empty-question。
- 状态：本地回归已执行；远端候选 CI 与独立评审由受管交付回执记录，本文不预先认证合并或部署。

## 复现与根因

`research_web_questionnaire.test.mjs` 增加消息为空、待回答问题无 seq 的回归，修改前实际失败：旧 renderer 在消息流为空时无条件加入菱形与“尚无消息”，再追加未定位问题卡。空态应由整个会话状态决定。

选项 label 原来只负责选中；独立按钮才调用下一题。现统一单选整行选择并继续，箭头为装饰；多选保持原生选择并显式继续，最后一题显式提交。

## 变更与契约

- Claw 欢迎页：浅灰终端图标、居中标题、靠下原有编辑器，案例折叠到“查看示例”。
- 欢迎页排除消息、问题、历史、授权、活动、子会话、运行、发送、停止、错误及交付回执；FinGPT 空态不变。
- 原生 radio/checkbox、表单身份、问题 ID、提交 payload、草稿隔离保持；单选方向键选择，Enter/空格确认，翻页焦点到题目。
- 连续指针点击保护；手动翻页重置保护，返回可立即重选；末题无隐式提交。
- 沿 core.create/send → /sessions/:id/messages → service 的 session.prompt → projection user/message → views 消息流核对。81 项协议测试与 2 项发送 API 测试通过，未证实首条原生消息丢失；没有增加消息猜测或修改 DSH 协议。
- 业务文档：docs/research-web-ui.md；无依赖、安装器、锁、数据库或常驻服务改动。

## 已执行验证

- `node --test tests/javascript/research_web_questionnaire.test.mjs`：修改前新增回归 FAIL；修复后 PASS。
- `node --test tests/javascript/research_web*.test.mjs`：692 项，690 PASS、2 SKIPPED、0 FAIL；早期夹具兼容失败已修复并重跑。
- 加入项目规定的文档、额度及跨平台合同测试：721项，719 PASS、2 SKIPPED；集成后README复核摘要长度校验曾FAIL，补全摘要后重验。两项SKIPPED为需固定DSH Loader/业务schema环境的既有条件测试，不视为通过。
- `node tests/e2e/research_web_codex_navigation.mjs --focus-claw-welcome`：6 组 PASS，覆盖浅/深主题与 390/1440、未开始/活动空快照、案例无提交、两模式整行文字/描述/空白、双击、返回重选、多选保留、键盘和显式末题提交。
- `node tests/e2e/research_web_codex_navigation.mjs --focus-forward`：两模式 × 两宽度 4 组 PASS。
- `node tests/e2e/research_web_codex_navigation.mjs`：完整既有浏览器矩阵 PASS。
- 现有测试环境的 Python：`PYTHONDONTWRITEBYTECODE=1 /Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/ai-news-live-deploy-20261019/.venv/bin/python -m pytest tests/research_web/test_protocol.py --confcutdir=tests/research_web -q`：81 PASS。
- 同一现有解释器执行 `-m pytest tests/research_web/test_api.py --confcutdir=tests/research_web -k 'create_submit_duplicate_never_replays or ordinary_task_receives_truthful_capability_and_data_readiness' -q`：2 PASS、200 deselected。
- `node scripts/check_documentation_governance.mjs --project .` 与 `scripts/generate_py_file_index.py --check`：PASS。
- 主 checkout 的 `.venv` 与 Homebrew Python 缺 pytest，首次尝试明确失败；没有安装，复用现有已配环境完成上述测试。

## 证据与边界

日志：logs/claw-empty-question/；浏览器回执及截图：logs/codex-navigation-browser/。截图含隔离测试会话和可能保留的例文草稿，不是线上会话。浏览器仅访问随机 loopback 端口，外部请求拒绝，不调用模型、不连接常驻服务。

候选 SHA、完整 changed set 路由、实际 CI checkout、评审、PR 与资源收尾以本任务受管交付回执和 logs 内验证产物为准。Windows/Linux 原生未执行；Ubuntu 仓库 CI 不冒充平台原生验收。常驻服务未部署；真实历史截图会话未读取，消息丢失原因没有实证。
