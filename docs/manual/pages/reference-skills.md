## Skill 的输入与依赖

Skill 是任务方法，不是数据源。每个版本都应说明用途、适用范围、输入参数、所需资料/数据、执行步骤和输出。
实际字段定义从 [能力中心 API](../../../outputs/research-web-architecture/reference-api-capabilities.html) 的 DraftInput、VersionInput 等模型查阅，避免另写一套冲突的参数表。

## 状态与版本

| 状态或字段 | 如何理解 |
| --- | --- |
| draft | 尚未发布的草稿。 |
| invalid | 检查未通过，先查看 checks。 |
| blocked_dependencies | 依赖不足，不能仅靠启用开关视为可执行。 |
| enabled / disabled | 当前发布能力的启用状态。 |
| has_draft | 已发布版本之外还有未发布编辑。 |
| checks / readiness | 分别查看包检查结果和当前使用条件。 |

已发布版本与草稿分开。内置能力可以复制修改，不能把修改过的草稿冒充原内置版本。

## 输出与质量判断

不同技能的默认格式不同：资料解读没有默认文件格式，公司研究的内置种子列出 docx、html、xlsx。
具体实例仍以所选发布版本的 default_formats、用户请求和当前工具能力为准。
CPU 有界计算器只处理声明的输入和字段映射；缺少必要资料时不能生成看似完整的业务结论。

查看输出时至少核对：输入是否对应本次对象与时点、来源是否明确、缺失是否保留、结果文件是否真实可下载。

## 开发与管理入口

内置“公司研究”可以作为理解元数据的例子，以下是代码中的种子定义，不代替实例当前版本：

| 项 | 已声明内容 |
| --- | --- |
| 用途 | 基于实际材料开展公司研究，保留来源、口径和缺失，按需交付文件。 |
| 输入 | question：研究问题与资料，text，必填。 |
| 工具依赖 | research_run_script、datahub_search_news。 |
| 文件格式 | docx、html、xlsx。 |
| 数据约束 | 种子未列独立 data_requirements；具体取数仍须经过来源授权和调用条件。 |

编写新技能可从能力中心复制已有技能开始：修改草稿的说明、输入和指令，执行检查，解决依赖后
发布一个版本，再决定是否启用。复制会创建新草稿，不修改原内置技能；发布与启用是明确的写操作。

| 操作 | 现有接口 |
| --- | --- |
| 列表与详情 | GET /capabilities；GET /capabilities/{cid} |
| 创建与编辑草稿 | POST /capabilities；PATCH /capabilities/{cid}/draft |
| 复制、检查与版本发布 | 按对应能力的 copy、check、versions 接口查阅。 |
| 由专用创建会话产物导入 | POST /capabilities/from-artifact |

以上路径均以 /api/research 为前缀。开发者先查真实请求模型、包检查和版本接口；本页不引入新的加载或执行流程。

## 相关指南

- [选择并使用技能](../../../outputs/research-web-architecture/guide-skills.html)
- [数据依赖与字段口径](../../../outputs/research-web-architecture/reference-data.html)
- [能力中心完整 API](../../../outputs/research-web-architecture/reference-api-capabilities.html)
