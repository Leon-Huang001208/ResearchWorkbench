# Task14 最终受管 integration 文档冲突

宿主 macOS；任务为已实现 Web 功能的受管本地集成，不执行产品安装、Docker、服务、
远端写入或 controller prepare。集成第一父节点为实际 fetch 的远端 master
`c24a8a161674678d572bf9ac35fab30489b40605`，待合入 feature 为
`6232f00eac81a78b1adec25a56613221d68c66e4`。

## 结构决策

只解决 08-research-frameworks、09-integration-coordinator、readme-review 三个真实 U。
保留主线两模块的领域概述、分层阅读锚点、单一 DSH/Provider 责任边界，与 feature 的
fresh-root/lease、单写者、实际宿主端点、控制 origin、模型与凭据隔离边界。
README 回执保持既有四字段 schema：当前 changed set 实际包含 README，所以选择 updated；
源码/文档哈希另外保存于本报告和私有日志，不增加 schema 字段或伪造视觉检查。
自动合并的 architecture-map 保持当前两侧资产；本轮验证 source/document/API/reading
合同，不重建图源、图形 HTML 或视觉回执，不修改生产源码。首次检查后获批准，仅用既有
Atlas 生成器机械刷新实际过期的图册 index.html，API Atlas 字节保持不变。

## 实际验证

完整当前 branch 的 `check_research_architecture --base c24a8a16…` 首次仅报
`generated_artifact_stale:outputs/research-web-architecture/index.html`；Atlas --check 同样失败。
先读取现有生成流程及模块文档，按新增单文件授权执行
`node scripts/build_research_web_api_atlas.mjs .`，而非改生成器或 metadata 政策。
实际生成计数为 188 个 API 声明、186 个唯一接口、12 个领域。
index 从 74641 字节 / SHA-256 `cdf66685b4169a5af3fc1848eeba3ee12a78d33f4a0dcea3f0f71628ef4c17e2`
变为 76234 字节 / `5f6ec432a5a1b48fdea1c37738ff227e4550adfc4bbdcb2adb4177d819db40ba`。
api-atlas 仍为 105453 字节 / `c335e4ebb2fd456f03bba176d972e84558b850c060c238895f315efc80cb9b20`。
图源、十份图形 HTML、截图、deliver/visual/human 回执保持原字节；未重新进行浏览器视觉验收。

生成后实际架构/Atlas --check 均 PASS。文档治理 569 文件 / 83 current / 0 violations，
Python index --check PASS。相关四文件 JS
`research_web_architecture/documentation_governance/actions_quota_governance/repository_cross_platform_contract`
共 100 PASS（5.820 秒）；实际合并验证日志为 `logs/task14-final-integration-*.log`。
第一轮重定向因新 worktree 尚无 logs 目录未执行检查；创建本 worktree logs 后使用独立日志
执行并保留真正结果，不将重定向失败称为测试失败或绕过。

当前 map 所覆盖的 405 个受跟踪 source 文件逐一摘要，聚合 SHA-256 为
`94fe1f9b7b50ad421c2a35dcc46b2a9ecef9c57bd8086348bc490ac0ea7f13c2`；
21 份模块文档聚合为 `430d7bb86ebb1c7d7ce773c2a173c5a6f54b906b2ea95a04e0c3746ed9b688cb`。
单文件清单/字节数保存在 `logs/task14-final-integration-source-document-hashes.json`；
README 为 `ef3ed7ffdf3ef64b74208232aa9de390f0444aeaf0e602b70aa919ab816ec0df`，
map 为 `5bbf2da18928528713ae75f42de53c716f7951fea7d48aa6f2a27f12ed8698c9`。
这些是当前本地字节证据，不是图形新视觉证据或外部 GitHub 可达性证明。

首次合并时 reading.repository.revision 仍为 `6ca33b2fbcab94357e129ee11bb236fc8683feff`；
新增 runtime_endpoints/control_origin 两个源码和两个测试在该旧 Git 对象不存在（本地
git cat-file 实查），尽管当前 source/document 合同有效，也不能把四个旧 pin 阅读链接标 PASS。
主任务随后批准先提交当前合并冻结实际源码，再用单独文档提交将 reading revision 精确绑定
该已存在 merge SHA；不使用 self/future SHA，也不修改 metadata policy/图源/视觉回执。
GitHub 链接可达性仍要等该源快照被明确授权发布后验证。

## 冻结 merge 后的阅读快照绑定

实际第一份 merge 为 `a186633bb6b7b3e23d2be275e18542924ba0849f`，双父节点为
`c24a8a161674678d572bf9ac35fab30489b40605` 和
`6232f00eac81a78b1adec25a56613221d68c66e4`。其完整 changed set 为 80，kernel
11 个文件 SHA 校验一致，完整 80 路径 Project Constraints PASS；该冻结提交不代表发布或 prepare。

按随后授权，本次只把现有 `reading.repository.revision` 的一行旧 SHA 替换为上述已存在
merge SHA，保持 URL、levels、modules 和 metadata policy。README 本身在这个 delta 未改变，
四字段 review 选择 unchanged，并携带真实 source/document 聚合 SHA 与具体源快照。
既有生成命令机械刷新 index 和 api-atlas：两者现在分别为
`24cb4e867d1e3bccc68a7b32dd8ea3db6406cb4f10f5db2b8bd45ef7d5c1eef0`（76234 字节）和
`2b76488c3a99bc97888c296579bb0d2c94496f0d000de09f661d4ad5a7edcfe5`（105453 字节）。
map SHA 为 `f73041a8004d400a4b4c8440d9ba6e5a45534cf54e0700877c7809f18602c4af`。

本地 Git 对象核对全部 200 个 mapped source/document/test 引用均存在于已冻结 a186 快照。
405 source / 21 documents 的工作树 SHA-256 均仍匹配首次真实摘要；其 Git canonical blob
也逐一匹配 a186，共 426 项。首次按裸字节直接计算 blob 的诊断对 rwb.cmd/setup-web.cmd
报告不等，原因是仓库既有 `.gitattributes` 规定工作树 CRLF、Git 存储 canonical LF；未改变这两个
生产文件、属性或策略。通过既有 `git hash-object --path` 正确使用原属性核对后全部匹配，
两种实际结果分别保存在 `logs/task14-final-integration-repin-proof.json` 与
`logs/task14-final-integration-repin-canonical-proof.json`，不删除首次失败证据。
源码/文档工作树摘要与 Git canonical blob 是不同表示，不混称为所有文件裸字节与 blob 相等。

这一 delta 仍不新增输出、重绘图形、修改截图或重新浏览器视觉验收；GitHub 可达性未运行。
本轮只处理文档/链接源快照，生产与协议验收及 controller 恢复由主任务负责。

第二文档 delta 为 map、review、index、api-atlas 和本报告五个路径。独立现有规划器因
HTML/validation_failure 选择 L4：3 本地门均实际 PASS（治理 0.121 秒、Python index
0.874 秒、相关四文件 JS 100 PASS / 6.233 秒）；一个 Project Constraints CI 未运行。
另实际执行当前全 branch 架构检查和 Atlas --check，均零违规；精确五路径 Project Constraints
PASS。完整 branch 的 source-affinity 与最终总回执由主任务继续，不另写一套完整验收回执。
两个 HTML 的实际字节严格等于 a186 版本中旧 revision 字符串统一替换为 a186；没有额外
UI、生成器或 API 改动。图源/原图/截图/视觉回执的 Git delta 为空。
完整命令、耗时及独立日志在 `logs/task14-final-integration-repin-{plan,records}.json` 和
相应 `*.log`；它们只认证这个文档 delta，不把旧 source 回执冒充最终 HEAD 的安装或生命周期。

本轮不替换任何既有 75b9da6、1a76d5、fresh-root 的历史报告或验收归属。

<!-- architecture-review {"group":"frameworks","structure":"unchanged","reason":"仅合并领域说明、阅读入口与双运行时消费者边界，既有框架源码和图源不变。","diagrams":[]} -->
<!-- architecture-review {"group":"integrations","structure":"unchanged","reason":"仅合并集成协调器阅读入口和运行边界，不改变五阶段源码、API或图源。","diagrams":[]} -->
