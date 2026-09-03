# Research Web 能力包与版本

能力中心属于 `app/research_web/capabilities/`。产品保存草稿、不可变版本、来源和校验结果；
DSH 仍是唯一执行引擎，Workflow 编译为原生 SKILL.md 步骤模板，没有第二个运行器。
目录读取不依赖会话、在线 DSH 或模型调用。工具目录为当前研究 composition 的只读声明，
不表示运行实例在线、凭据已配置或某次取数已获批准。

## API（全部位于 `/api/research`）

| 方法与路径 | 输入 / 返回 |
| --- | --- |
| GET `/capabilities?kind=skill\|workflow` | `{items, publication_uncertain}`；不传 kind 返回全部 |
| GET `/capabilities/{id}` | 概览、`draft`、`checks`、当前版本 `steps` |
| POST `/capabilities` | `DraftInput`；201，创建手动草稿 |
| PATCH `/capabilities/{id}/draft` | 完整替换草稿的 `DraftInput`，不改变已启用版本 |
| POST `/capabilities/{id}/copy` | `{name,slug}`；201，内置/自建能力均可复制，脚本需重新审查 |
| POST `/capabilities/import` | multipart 单个 `file`：精确名 `SKILL.md` 或 `.zip`；201，返回草稿及检查 |
| POST `/capabilities/{id}/check` | `{valid,status,issues:[{code,message,path}],bindings,checked_at,executes_code:false}` |
| POST `/capabilities/{id}/publish` | 检查通过后新建整数版本并启用；不修改原版本 |
| POST `/capabilities/{id}/disable`、`/enable` | 停用/重新启用当前版本 |
| POST `/capabilities/{id}/rollback` | `{version:整数}`，显式切回已有版本，不创建或重写旧版本 |
| GET `/capabilities/{id}/versions` | `{items:[{version,native_name,metadata,published_at,sha256,current}]}` |
| GET `/capabilities/{id}/versions/{version}` | 原始指令、元数据、文件及步骤，`read_only:true` |
| GET `/capabilities/{id}/versions/{version}/export` | ZIP：原始 SKILL.md、capability.json、可选 workflow.json、资源 |
| GET `/tools` | 9 项真实研究 guard/注册声明；3 项 `selectable:true`，其余为内部控制 |
| GET `/workflows` | 同一能力目录中两项种子及用户 Workflow；没有平行目录 |
| POST `/capabilities/creation-sessions` | `{kind:"skill"\|"workflow",goal}`，201，真实创建会话并返回未发送的 `draft` |
| POST `/capabilities/from-artifact` | `{session_id,file_id}`，201，仅专用创建会话实际 outputs 产物导入为草稿 |

普通失败为 `{error:{code,message}}`；名称/slug 冲突、内置覆盖、活动回合和历史版本选择冲突
为 409；草稿不兼容为 422；压缩上传超过上限为 413；存储/发布异常为 503。
内置只能复制修改；允许停用/启用，不能编辑或再次覆盖发布。草稿编辑无需运行实例在线。
`status` 为 `draft/invalid/blocked_dependencies/enabled/disabled`；已发布能力编辑后仍保留
原 `enabled/disabled` 状态，`has_draft:true` 与 `checks.status` 表达未发布候选状态。

### 草稿契约

```json
{
  "kind": "skill",
  "metadata": {
    "name": "我的研究",
    "slug": "my-research",
    "description": "围绕上传资料开展可追溯研究",
    "category": "资料研究",
    "inputs": [{"name":"question","label":"研究问题","type":"text","required":true}],
    "scenarios": ["解读资料"],
    "default_formats": ["md"],
    "required_tools": ["af_run_script"],
    "dependencies": []
  },
  "instructions": "---\nname: my-research\ndescription: 有来源的研究\n---\n# 研究\n核对来源，列出缺失。",
  "files": [{"path":"templates/report.md","content":"# 报告"}],
  "steps": [],
  "reviewed_scripts": []
}
```

`inputs.type` 为 text/file/date/number。格式为 md/html/docx/xlsx/png。
文本文件用 `{path,content}`；图像等二进制用 `{path,base64}`。返回文件包含 size/sha256，
可读 UTF-8 用 content，其他用 base64。编辑接口不是 JSON Merge Patch，发送完整候选；
不要回传服务器生成的 `file_issues/import_issues`。前一原始上传仍保留在私有 originals。
`instructions` 必须是完整 SKILL.md；name 必须等于 metadata.slug，缺字段不补默认后宣称兼容。
ZIP 必须以包根 SKILL.md、capability.json 开始，不自动移动多层目录。
单独 SKILL.md 因缺产品中文元数据而形成 invalid 草稿，用户编辑后才能发布。

Workflow 的 kind 为 workflow，instructions 可空；steps 为有序
`{title,instruction,skill_id?:已启用Skill的产品ID,tools:[]}` 数组。
发布记录关联 Skill 的具体版本与 native_name；关联版本变化或停用后，显式选择该 Workflow
会被拒绝，须编辑重新发布。步骤是计划模板，不应由前端标记为已经执行。

### 会话与提交

已有 `POST /sessions/{sid}/messages` 增加 `capability_id`、`capability_version`（正整数）及
`tool_ids`（af_run_script/af_public_data/web_search，仅意图）。推荐客户端始终传选中的版本。
版本省略时首次受理绑定当时版本；同一幂等键重试使用原收据，不重新执行、不因后来停用而重发。
非当前版本需要先显式回滚；`skill_id` 保留兼容，四个内置 ID 不变。
显式 `expected_formats`（包括空数组）优先，否则用能力默认格式。

发送前在同一锁内验证状态、真实 `skill.list` 的 exact native_name、依赖和包哈希，
将启用目录资源复制为本会话只读快照；因为 DSH 也会自主挑选 Skill，所有已启用包均提供快照。
已存在快照不覆盖，跨会话不共享可变路径。收据记录用户选择 `capability` 及可用快照
`capability_catalog`；详情返回 capability/capability_history，不能将可用快照列表说成实际执行列表。
DSH 得到的是原生 slash invocation 与当前会话相对资源指引，不绕过其原生 Skill loader。
旧会话原有 `resources/skills` 不改写。

创建接口只创建真实会话并把候选要求放入 draft；不自动提交模型、不自动发布。
用户通过普通消息接口开始制作包，结束后选择实际 outputs/SKILL.md 或候选 ZIP。
选择根 SKILL.md 时仅一并读取实际根 capability.json/workflow.json；需要脚本/模板时产出完整 ZIP。
只有专用创建会话的 ZIP 才加入产品文件索引，普通会话不扩展文件格式。
导入仍需检查、审查脚本和显式发布。静态安全检查不是“恶意代码已证明安全”。

## 存储与安全

```text
<AF_RESEARCH_DATA>/capabilities/
  catalog.json                  # 原子产品目录、草稿、版本记录、发布 pending 标记
  originals/<id>                # 原始上传字节，只读；不提取、不运行
  versions/<id>/<version>/      # 不可变已审核包（文件 0444，目录 0555）
  native-skills/<native_name>/  # 仅当前启用版本的 DSH 单层 discovery 投影
  retired/<opaque-id>/          # 原生目录切换保留的旧投影，不扫描
<AF_RESEARCH_DATA>/sessions/<sid>/resources/capabilities/<id>/<version>/
```

导入压缩上限 10 MiB，展开总计 30 MiB，最多 128 ZIP 条目，单文件 10 MiB。
拒绝绝对路径、`..`、反斜线/盘符、点目录、大小写重复名、链接/特殊文件、加密 ZIP、
嵌套压缩、二进制可执行 magic、安装配置/钩子。ZIP 不使用 extractall，候选保存在索引与原始 blob，
恶意路径不会写出目标目录。允许 md/txt/csv/json/yaml/yml/html/css/j2 文档模板、
png/jpg/jpeg/webp/gif/svg/pdf 资料，及 `scripts/*.py` 研究脚本。
研究脚本语法、静态缺失 imports、显式依赖及安装行为检查；脚本哈希须加入 reviewed_scripts。
不存在自动依赖安装。URL/extras/marker 依赖声明不支持，明确报错。
导入检查保留失败问题；用户完整编辑候选是显式处理，不悄悄修复并声称原包兼容。

发布、停用、启用、回滚、发送共用 ResearchService.lock；原生父任务、子 Agent、诊断异常、
断连、未知受理或未确认交付均阻止目录切换，草稿仍保留。
切换前持久化 pending；异常尝试恢复原映射，无法确认时拒绝后续发送/发布。
进程崩溃遗留 pending 或目录与索引不一致时，启动 prepare_native_root 拒绝宣称成功；
须由操作者停止专属实例后核对 catalog、versions 与 retired，恢复一致状态再启动。
不自动覆盖、删除版本或清除未知标记。仅支持一个 Web worker。
macOS 移动目录需更新 `..`：native 投影顶层目录为服务自有 0700，文件仍只读；
不可变 versions 树与会话资源仍只读，不增加脚本沙箱权限。

## 原生接线与工具真实性

DSH 固定提交 `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`。
核对 upstream `packages/skill/skill-filesystem/README.md` 和 FileSystemSkillProvider 源码：
发现仅一层 bundle，watch 触发 invalidate，每次 get 重读正文，无版本 pin 或 install RPC。
产品以不可变包 + 带版本的原生名称实现绑定；自建名称为 `af-<产品id>-vN`，内置保留原 ID。

研究 preset 使用 `includeDefaultRoots:false`、唯一 `customSkillDirs:<data>/capabilities/native-skills`、
`watch:true`、`watchFollowSymlinks:false`。不读取宿主默认项目/用户 skills。
启动器 prepare 已接入此目录；本任务没有重启 live 3081/8088，更没有触及旧 3080。
主控制器须确认所有实际任务结束后，通过原授权启动器更新专属实例；旧实例指向仓库 skills，
自建版本在旧实例会明确报 native_discovery_pending，不伪装已经调用。

tools.py 是已核实原生注册的离线投影，读取现有 guard 取交集，并附参数、来源、审批和条件。
真实原生注册测试覆盖 skill/subagent/report/send_message/interrupt_agent/list_agents/web_search
及本项目 af_run_script/af_public_data；DataHub 的 Query schema 与五个 SOURCES 直接复用。
report 仅原生子 Agent 作用域可用；所有工具权限、模型、执行上限及审批策略均未改变。

## 验证映射

| 源码 | 测试 | 验证边界 |
| --- | --- | --- |
| capabilities/models/packages/catalog/seeds | test_capabilities.py、test_capabilities_safety.py | 离线种子、元数据、恶意ZIP、脚本审查、不可变版本、恢复失败 |
| capabilities/routes、main/service/store | test_capabilities_admission.py、既有 research_web 回归 | 原生名称核对、格式优先、幂等、跨会话、并发、创建产物 |
| tools、launch_runtime、research.cordis.yml | test_capabilities_native.py | 固定源码真实 provider list/get/watch 与实际注册；不调用模型 |

实际命令、RED/GREEN 和剩余验收见 [后端任务报告](../.ai/reports/2026-09-03-capabilities-backend.md)。
本批不涉及桌面/Windows/发布；不以本地协议测试代替主控制器后续真实界面与模型调用验收。
