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
DSH 源码固定 `c919b2a460753859665db3f60143d525fb9140cf`；CLI 版本为 `0.1.3-alpha.2`。该 Fork 运行分支基于官方最新架构提供原生 `session/delete`，Workbench 兼容桥通过 Typert Gateway 的斜杠命名 RPC、Remote mux 和浏览器会话认证接入；启动器仍记录实际源码提交与构建闭包哈希。
管理器默认使用固定源码中已构建的 DSH CLI；启动失败会回收本次新建进程并保留日志，不会接管占用端口的外部进程。
不带 `--research-tools` 可启动禁工具聊天模式；无法完成沙箱启动检查时不要开放脚本。

Fork 维护约定：`Leon-Huang001208/deepseek-harness` 的 `master` 只用
`git merge --ff-only upstream/master` 跟踪官方仓库，官方 `upstream` 禁止推送；产品补丁保留在
`workbench-runtime`，定期合入 Fork `master` 并完成 DSH 与 Workbench 全量回归后才能推送。每次
`workbench-runtime` 提交变化，都必须同步本文件、启动器与能力目录的固定 SHA、私有运行副本和
`build-lock.json`。若官方提供等价永久删除能力，应移除重复补丁，只保留必要的 Workbench 兼容桥。

## Windows 本机集成验证

本机集成诊断由 `.github/workflows/research-web-windows-verify.yml` 在原生
`windows-2022` runner 上验证。作业运行本机集成 API、探测生命周期与页面契约，实际启动回环服务、
调用专用状态接口并完成一次探测，再上传仅含平台、汇总及 Wind/iFinD 非秘密状态的证据。

Research Web 启动时读取的产品索引、能力种子与 Report Workflow 目录显式使用 UTF-8，避免 Windows
默认代码页把中文能力文档误判为不可读。该作业覆盖整个 `app/research_web/` 变更范围，确保
启动依赖变化也会触发原生 Windows 验证；DataHub 的全量平台回归由独立测试负责。

GitHub runner 未预装厂商软件时，结果只证明 Windows 检测链路和服务可运行，不证明
Office、Wind 或 iFinD 已登录或可调用。

Windows 不支持 POSIX 的目录描述符标志；服务启动所需的 DataHub 私有控制文件因此使用专用
路径回退，并在读写前拒绝符号链接/重解析点、越界目录、非普通文件、硬链接和超限内容。
DataHub 会话快照与连接配置写入的完整 Windows 兼容性不在本机集成专项结论内。

DSH 认证控制文件由 Web 客户端和服务管理器共用的安全读取器处理。所有平台均限制文件大小、
拒绝非普通文件、硬链接、符号链接、Windows 重解析点和打开前后的身份变化；macOS/Linux 继续
要求 group/other 无权限，Windows 不使用无 ACL 语义的 POSIX mode 投影做误判。
服务管理器的数据、状态与日志目录同样只在 POSIX 检查 group/other mode 位；目录类型、符号链接
和 Windows 重解析点检查仍在所有平台生效。

## 数据与模块

- `client.py`：允许列表 RPC、关联 ID 检查、双下行通道和历史分页。HTTP 超时只限制受理，不限制任务时长。
- `service.py`：会话归属、事件归一、状态恢复、幂等提交、原生子Agent取消、审批与问题响应。
- `store.py`：原子本地 JSON 索引（单 Web worker），不保存模型正文；文件使用不跟随符号链接的目录描述符打开。
- `main.py`：回环 Web API、安全来源边界、上传与隔离预览；无旧业务启动钩子。
- `local_integrations/`：无副作用的主机软件发现、安全状态投影和幂等探测任务；不启动厂商软件，不返回本机路径或秘密。
- `local_integrations/verifiers.py`：用户显式触发的 macOS Office/Wind 真实验证；在可终止子进程和受管验证目录中执行，发现探测仍保持无副作用。成功结果才写入可调用状态，授权、登录、超时和公式失败均保持独立状态。
- `ui/`：正式五页与原生模块，详见 [UI 文档](research-web-ui.md)。
- `runtime/`：专属 DSH composition、工具白名单与每轮执行上限。
- `skills/`：市场解读、资料解读、公司研究、行业研究、基金评价和因子库研究六类原生 SKILL.md、脚本与模板；禁止扫描用户其他全局 Skill。
- `resources/`：实际 PDF 页码抽取、Office/HTML/Markdown 文件生成与重开检查。
- `datahub/`：固定来源、分页、私有原始响应、会话不可变资料、校验读取与缓存；见 [DataHub](research-web-datahub.md)。
- `runtime/public-data.mjs`：启动时只注册已有可调用来源的 `datahub_*` 工具，并通过可信会话身份与认证回环 DataHub 自动桥接、联动取消，不再重复上游解析或逐次确认；见 [公开数据工具](research-web-public-data.md)。

数据根默认 `~/.research-workbench/research-web`（可通过 `RESEARCH_DATA_HOME` 指定）。其下：

```text
index.json                   # 归属、默认模型和幂等受理收据
connections/mysql.json       # 当前用户 MySQL 非秘密配置；密码不在此文件
runtime/home/                # 专属DSH历史与凭据
runtime/work/                # 干净启动目录，无.env
runtime/*-lock.json           # 本地源码/构建锁
sessions/<uuid>/inputs/      # 上传资料，只读给研究脚本
sessions/<uuid>/resources/   # 审核过的辅助脚本和模板，只读
sessions/<uuid>/outputs/     # 真正生成的文件
```

MySQL 密码由服务名 `ResearchWorkbench.DataHub`、账户键 `mysql:default:password` 保存到操作系统凭据库；凭据库不可用时闭合失败，不降级到环境变量或明文文件。模型 API Key 仍由专属 DSH 管理，两类秘密不共享命名空间。

iFinD `http_api` 探测沿用数据源页保存的非秘密 Base URL 和系统凭据库账号，执行登录、`/health` 检查并关闭会话；Token 仅存在于内存，不写入连接状态或日志。未配置账号继续显示待配置。

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
Windows 本机集成专项冒烟使用一次性、无真实权限的回环认证元数据构造 DSH 客户端，仅验证 Web 服务生命周期、平台投影和探测端点；不据此宣称 DSH、Office、Wind 或 iFinD 已连接。

## 原生协议与产品细节

- Session 提交只等待受理；`events.mux` 与 `events.host` 同时连接。完整内容从原生日志分页读取，事件重连清除投影基线但不重新提交。
- DSH 重启后先用 `session.models` 恢复记录中的 preset，再查询 `skill.list`；不会创建替代会话或重复发送。
- 会话删除分两阶段：首次删除只在产品索引写入 `deleted_at`，从正常列表隐藏并保留 30 天；期间可从“已删除”恢复。用户主动永久删除、服务启动或在线保留期任务发现到期时，会调用 DSH `session.delete` 级联删除原生会话日志；只有响应明确包含根会话 ID 后，才删除 Workbench 的会话目录、附件、数据集、产物、私有 DataHub 调用/快照目录与索引记录。只读能力快照会在产品根目录内以不跟随符号链接的方式恢复目录写权限后清理；任一清理失败会保留不可恢复流程的墓碑供幂等重试，不把产品隐藏误报为永久删除。
- 子 Agent 活动来自 `subagent.list/history` 的父子归属接口；每个子 Agent 展示最近100条消息的投影，`history_truncated` 明确说明更早内容未加载，1秒缓存减少重复读取。
- 父回合结束但子 Agent 仍运行时，详情和历史保持运行状态；停止调用原生父会话取消及直接子 Agent interrupt，不把受理当作已停止。
- 父 Agent 已离线的 `session-not-found` 不阻断原生父子归属下的子任务取消；其他错误仍明确报告。原生后台子 Agent 审批策略为 `never`：当前 Runtime 已暴露的 DataHub callable 工具由父 Agent 自动取数，子 Agent 复用父 Agent 已取得的同一数据集；只有 DataHub 以外仍需审批的工具沿用原策略，由父 Agent 取得结果后交给子 Agent 分析。
- 子 Agent 展示原生用量、错误和已结束回合累计耗时；工具耗时来自原生事件时间戳。未提供时不填零。截断历史时提示统计不完整。内部任务标记只在 Web 展示层隐藏，本会话原生日志保留完整契约。
- 模型配置、创建及发送共用单进程锁；配置完成才发布产品默认模型，运行中的原生会话不被热切换。
- 图片附件转换为原生 image content（单张8MiB、合计16MiB），DSH负责媒体校验和模型兼容性；其他文件作为只读inputs路径交给研究工具。上传30MiB上限不表示模型能接收等大图片。
- 本地索引不保存聊天正文；消息可选 `expected_formats`，通过幂等收据和提交前 outputs 哈希绑定独立文件交付检查。DOCX/XLSX/HTML/Markdown/PNG 实际解析仅在严格沙箱内执行；详情 `delivery` 与原生执行状态分开，不能仅凭回合 completed 判定报告交付。接口、默认格式、串行归属和限制见 [文件交付检查](research-web-delivery.md)。

## 验收与保留限制

- 本机集成 v0 只完成本机服务、Office/Wind/iFinD 本机事实、浏览器应用和未完成闭环的安全诊断。文件夹同步、浏览器扩展配对、本地 MCP 授权及 Office 真实调用仍明确显示待配置或待验证；WindPy 与 iFinD HTTP/SDK 的数据调用继续由 DataHub 判断，不在本机页伪装为可用。

- 原生 `web_search` 已有真实模型证据；财联社电报、基金净值及其批准/拒绝/等待中取消则是旧 DataHub 逐次审批机制下的历史证据。当前 DataHub 已替换为启动时仅暴露 callable 工具并自动取数；仍不开放任意网页 fetch、MCP 或自动依赖安装。
- 早期基金示例只有20条单页数据；后续DataHub批次已完成2025净值13页243条、基本资料16项、分红25条、披露持仓220条，并由两个真实子Agent共用快照产出文件。见[DataHub验收](../.ai/reports/2026-09-02-datahub-acceptance.md)。仍缺基准序列、复权总回报、合同/定期报告原文及完整持仓，不能据此宣称完整基金尽调。文件格式验证不替代数据与结论复核。
- 已验证真实无效模型报错并恢复、同键不重发、父与子脚本停止。BFF 中断后的审批/草稿恢复是旧 DataHub 逐次审批机制下的历史证据；当前已替换为 callable 工具自动取数，不再出现 DataHub 审批提示。未模拟提供方生成到一半时的任意故障类型；真实图片模型识别仍未覆盖。
- 本轮仍是本机回环单人 Web；浏览器交互与 MySQL Keyring 已在 macOS 本机验证，Windows/Linux 的 Web 服务凭据库后端仍需对应操作系统 CI 验证。MySQL 引入 PyMySQL 与 keyring，不新增第三方 MCP；桌面 sidecar、Tauri 安装包及安装级烟测不在本次范围内。
- 早期固定Python启动探针 PID 38291 留在macOS内核 `UE` 状态；SIGKILL后未确认回收，临时目录 `/private/tmp/rwb-dsh-sandbox-probe.frLuyJ` 保留。它不是模型脚本；旧实验profile快照不完整，不能保证其权限/句柄状态。当前有效runner的全部取消测试已正常回收。
- 未涉及桌面应用适配、市场首页/主题/自选、旧系统数据删除。
