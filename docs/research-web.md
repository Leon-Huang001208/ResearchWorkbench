# DSH Web 实施记录

本轮以 Web → FastAPI → DSH 原生 RPC / 双 WebSocket 为唯一研究链路。
不加载旧数据库、研究运行器、知识处理和桌面生命周期。

## 实施顺序

1. 原生协议、归属索引、历史与 SSE；FinGPT 页面集成。
2. 专属运行实例、模型授权、严格文件访问约束与真实聊天验收。
3. 资料上传与生成文件；真实工具和产物验收。
4. 原生 Skill、Claw 子 Agent、异常与浏览器回归。

## 边界

- 用户现有 3080 只做协议验证，不修改配置、重启或复制其凭据。
- 新入口 `app.research_web.main:app`，仅回环地址运行。
- 产品索引只存会话归属、文件标识、幂等收据；历史正文来自 DSH。
- 连接中断不重发问题；未知受理结果要求先查看历史。
- 缺少安全工具运行环境时禁止调用工具，不把 cwd 当沙箱。
- 2026-09-02 已用专属 DeepSeek 模型完成真实聊天、PDF、公开数据文件、双子 Agent 报告和异常恢复旅程；证据见 [真实验收记录](research-web-acceptance.md)。这不代表任意题目的研究质量均已验证。

## 开发启动

安装项目命令后，使用项目级后台管理器启动；命令返回或终端关闭后，两个进程仍继续运行：

```bash
rwb web start
rwb web status
rwb web restart
rwb web stop
```

入口：`http://127.0.0.1:8088/#/fingpt`。3081 与 8088 的 PID、命令指纹和日志保存在 `~/.research-workbench/run/` 与 `logs/`；停止仅操作归属一致的进程，不触碰原有 3080。模型密钥只在设置页填写，不从 3080 或旧数据目录复制。
DSH 源码固定 `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`；CLI 版本为 `0.1.1-rc.2`，`host.describe` 当前协议实现报告 `0.0.1`。启动器记录实际本地源码/构建闭包哈希。
管理器默认使用固定源码中已构建的 DSH CLI；启动失败会回收本次新建进程并保留日志，不会接管占用端口的外部进程。
不带 `--research-tools` 可启动禁工具聊天模式；无法完成沙箱启动检查时不要开放脚本。

## 数据与模块

- `client.py`：允许列表 RPC、关联 ID 检查、双下行通道和历史分页。HTTP 超时只限制受理，不限制任务时长。
- `service.py`：会话归属、事件归一、状态恢复、幂等提交、原生子Agent取消、审批与问题响应。
- `store.py`：原子本地 JSON 索引（单 Web worker），不保存模型正文；文件使用不跟随符号链接的目录描述符打开。
- `main.py`：回环 Web API、安全来源边界、上传与隔离预览；无旧业务启动钩子。
- `ui/`：正式五页与原生模块，详见 [UI 文档](research-web-ui.md)。
- `runtime/`：专属 DSH composition、工具白名单与每轮执行上限。
- `skills/`：资料解读、公司研究、行业研究、基金评价四类原生 SKILL.md、脚本与模板；禁止扫描用户其他全局 Skill。
- `resources/`：实际 PDF 页码抽取、Office/HTML/Markdown 文件生成与重开检查。
- `datahub/`：固定来源、分页、私有原始响应、会话不可变资料、校验读取与缓存；见 [DataHub](research-web-datahub.md)。
- `runtime/public-data.mjs`：原生审批、可信会话身份、认证回环DataHub及取消薄桥接，不再重复上游解析；见 [公开数据工具](research-web-public-data.md)。

数据根默认 `~/.research-workbench/research-web`（可通过 `RESEARCH_DATA_HOME` 指定）。其下：

```text
index.json                   # 归属、默认模型和幂等受理收据
runtime/home/                # 专属DSH历史与凭据
runtime/work/                # 干净启动目录，无.env
runtime/*-lock.json           # 本地源码/构建锁
sessions/<uuid>/inputs/      # 上传资料，只读给研究脚本
sessions/<uuid>/resources/   # 审核过的辅助脚本和模板，只读
sessions/<uuid>/outputs/     # 真正生成的文件
```

不得使用多个 Uvicorn worker 并发写同一索引。研究正文只读 DSH 日志；浏览器断线不取消任务也不自动重提。

旧研究数据使用 `rwb migrate-research-data --dry-run` 先核对数量、大小和哈希，再执行复制。迁移保留会话、附件、能力版本、数据集、产物和原生会话索引；明确排除模型凭据、控制令牌、运行时 overlay、临时文件和日志。新目录验证通过后才可加 `--archive-source` 将旧目录移为只读备份，模型授权需在新设置页重新填写一次。

## 验证命令

```bash
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q
node --test tests/javascript/research_web*.test.mjs
python -m ruff check app/research_web tests/research_web
python -m black app/research_web tests/research_web --check
python -m isort app/research_web tests/research_web --check-only
python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
```

Skills 的同名独立脚本要逐文件执行 mypy，避免模块重名。真实模型验收单独记录，不以 MockTransport/TestClient 代替。
`DSH_SOURCE_ROOT` 只用于测试已存在的原生 JSON Schema 转换器；未设置时该项会跳过，不能据此宣称协议验证完整。

## 原生协议与产品细节

- Session 提交只等待受理；`events.mux` 与 `events.host` 同时连接。完整内容从原生日志分页读取，事件重连清除投影基线但不重新提交。
- DSH 重启后先用 `session.models` 恢复记录中的 preset，再查询 `skill.list`；不会创建替代会话或重复发送。
- 子 Agent 活动来自 `subagent.list/history` 的父子归属接口；每个子 Agent 展示最近100条消息的投影，`history_truncated` 明确说明更早内容未加载，1秒缓存减少重复读取。
- 父回合结束但子 Agent 仍运行时，详情和历史保持运行状态；停止调用原生父会话取消及直接子 Agent interrupt，不把受理当作已停止。
- 父 Agent 已离线的 `session-not-found` 不阻断原生父子归属下的子任务取消；其他错误仍明确报告。原生后台子 Agent 审批策略为 `never`，需审批的取数由父 Agent 完成，再传给子 Agent 分析，不修改原生策略。
- 子 Agent 展示原生用量、错误和已结束回合累计耗时；工具耗时来自原生事件时间戳。未提供时不填零。截断历史时提示统计不完整。内部任务标记只在 Web 展示层隐藏，本会话原生日志保留完整契约。
- 模型配置、创建及发送共用单进程锁；配置完成才发布产品默认模型，运行中的原生会话不被热切换。
- 图片附件转换为原生 image content（单张8MiB、合计16MiB），DSH负责媒体校验和模型兼容性；其他文件作为只读inputs路径交给研究工具。上传30MiB上限不表示模型能接收等大图片。
- 本地索引不保存聊天正文；消息可选 `expected_formats`，通过幂等收据和提交前 outputs 哈希绑定独立文件交付检查。DOCX/XLSX/HTML/Markdown/PNG 实际解析仅在严格沙箱内执行；详情 `delivery` 与原生执行状态分开，不能仅凭回合 completed 判定报告交付。接口、默认格式、串行归属和限制见 [文件交付检查](research-web-delivery.md)。

## 验收与保留限制

- 原生 `web_search`、财联社电报、基金净值及批准/拒绝/等待中取消已有真实模型证据；不开放任意网页 fetch、MCP 或自动依赖安装。
- 早期基金示例只有20条单页数据；后续DataHub批次已完成2025净值13页243条、基本资料16项、分红25条、披露持仓220条，并由两个真实子Agent共用快照产出文件。见[DataHub验收](../.ai/reports/2026-09-02-datahub-acceptance.md)。仍缺基准序列、复权总回报、合同/定期报告原文及完整持仓，不能据此宣称完整基金尽调。文件格式验证不替代数据与结论复核。
- 已验证真实无效模型报错并恢复、BFF 中断后审批/草稿恢复、同键不重发、父与子脚本停止。未模拟提供方生成到一半时的任意故障类型；真实图片模型识别仍未覆盖。
- 本轮仍是本机回环单人 Web；脚本隔离仅验证当前 macOS Seatbelt，未验证 Linux 部署。未新增任何依赖或第三方 MCP。
- 早期固定Python启动探针 PID 38291 留在macOS内核 `UE` 状态；SIGKILL后未确认回收，临时目录 `/private/tmp/rwb-dsh-sandbox-probe.frLuyJ` 保留。它不是模型脚本；旧实验profile快照不完整，不能保证其权限/句柄状态。当前有效runner的全部取消测试已正常回收。
- 未涉及桌面/Windows、市场首页/主题/自选、旧系统数据删除。
