# 资产交互 v5 固定部署：验收草稿

日期：2026-10-22。宿主：macOS Mac mini。任务类型：Web功能／固定部署工具交付；本平台范围为本机macOS与适用的同候选Mac CI。任务为`asset-interaction-v5-deploy-20261022`，基线及已审产品为PR185真实merge `9bc4e4cab91130647a5bc0dfa519e97f4773416a`。当前报告状态为未部署；最终工具提交、独立评审、CI、切换、认证页面和资源收尾由主任务分别绑定。

## 固定合同与边界

- `reviewed-asset-observation-v5`／`apply-assets-v5`只扩展原常量表、ASSET_MODES、previous_for、review_assets与CLI分派；PREVIOUS固定当前常驻`51f09fa783694aae5234905933948394ca167dcc`，PAYLOAD固定上述PR185真实merge，不接受任意旧版或产品SHA。
- 复用version4 journal、原维护锁、BirthFence、空闲准入、严格全账号索引保全和内容寻址恢复。v5 recover只回51f09；旧资产v1–v4、两个market profile、模型恢复、controller／evidence及自动兼容白名单保持。
- 产品祖先、完整路径并集、blob、模式、干净checkout及源码／发布仓库身份仍需核验。活动目录租约、区块／历史任务、真实Future或未知witness不能被HTTP取消或预览认证为空闲。
- 无新服务、HTTP、持久格式、数据流、依赖、秘密入口或平台能力。当前01／12等图源仍准确，不重画图；API inventory保持318条声明／315个唯一接口。阅读入口源码链接固定到已审产品9bc4，工具与报告提交另记。

## 改动与证据映射

| 改动 | 回归／文档 | 当前证据边界 |
| --- | --- | --- |
| 固定v5身份与原分派 | test_model_provider_upgrade.py；部署合同、架构、开发映射 | 源码及测试由主任务／独评负责，文档任务不改写代码 |
| README及四字段复核回执 | 根README、readme-review.json | 补正确51f09恢复基线，历史合同保留，明确未部署 |
| 双运行时／多用户相关合同 | 架构01–05、installation、docker、platform、ai-news、ETF production | 分别说明保全及无影响依据；无新图源或API |
| 官方索引及阅读页 | generate_py_file_index.py、build_research_web_api_atlas.mjs | 只使用官方生成器，执行结果另记私有logs/asset-v5-docs-impl |

## 验收状态

主任务已核定PR185产品candidate／preview／merge同tree且产品三CI通过。这只证明已合并产品，不认证v5操作员候选通过。本文不把其他任务的CI、浏览器、供应商预检或恢复记录改写为本profile证据。

| 验收层 | 当前状态 |
| --- | --- |
| 本机v5操作员／恢复矩阵及独立评审 | 待主任务及独评回执 |
| 完整changed-set Router／constraints／doc-sync／文档回归 | 本轮24路径完整规划，L4；constraints／doc-sync PASS，文档JS112／Python29 PASS，范围见下节 |
| 原Project Constraints／Research Web Checks／同候选macos-14 Bootstrap | NOT_RUN／待最终v5候选绑定 |
| 固定DSH、3081／8088与Doctor | 待同候选Mac干净安装；本机installed环境不替代 |
| 实际apply／运行版本／全账号保全／真实认证页面 | NOT_RUN／未部署 |
| Windows／Linux原生与Docker产品验收 | 本任务未执行，由相应设备保持各自状态 |
| 归档／资源回收／Git清理 | 待主任务合并与部署验收后正式收尾 |

## 本轮文档实际检查点

| 检查 | 实际结果／证据 |
| --- | --- |
| 完整Router | Git绑定plan v4涵盖24路径，L4，保留unknown-boundary；按既有catalog补选原Project Constraints、Research Web Checks、Mac Bootstrap三门，没有执行或削减CI。logs/asset-v5-docs-impl/router-bound-plan.json；提交后须重绑最终候选 |
| 全文constraints及doc-sync | 24路径均检查，0 violations；governance 798文件、官方索引check通过。logs/asset-v5-docs-impl/constraints.log、doc-sync.log；首次文档锚点失败已修正，原失败日志保留 |
| Router本地文档闭包 | research_web_architecture、documentation_governance、actions_quota_governance、repository_cross_platform_contract四个JS模块112 PASS／0 skip。logs/asset-v5-docs-impl/router-documentation-tests.log |
| 文档HTTP／同步回归 | test_documentation.py与test_doc_sync.py共29 PASS；1项第三方Starlette弃用警告。logs/asset-v5-docs-impl/python-documentation-tests.log |
| 官方生成物 | Python索引官方重生成后字节不变；Atlas／阅读页只更新源码链接到9bc4，318声明／315唯一API，官方check PASS。logs/asset-v5-docs-impl/pyindex-preview.json、atlas-preview.json；图源及其HTML／PNG未修改 |

## 安装与结构复核

已核对requirements/web.in、requirements/web.lock、scripts/setup_web.py、research-web-installation.md与research-web-bootstrap.yml。依赖、安装器和workflow与产品基线逐字节相同；仅安装说明增加v5操作合同，不安装包、不新增job／runner／条件。三个一键入口及原同候选Mac安装门保留；核对记录为`logs/asset-v5-docs-impl/installation-contract-review.json`。

文档范围不执行Git提交／发布、apply／recover、系统配置、凭据读取、供应商或模型调用。原业务会话、市场缓存、账号、报告状态和未验收限制保持；源代码评审与本地、CI、部署、平台证据分层。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"v5只在既有Native操作员增加固定旧51f09与PR185产品9bc4的封闭身份和CLI分派，原进程、部署节点、version4事务、锁和恢复边界不变，无新增HTTP或数据流，现有01部署图与12资讯图准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"v5沿原主实例／网关身份、BirthFence、空闲准入和全账号索引保全，不新增账号、权限、秘密namespace或资料归属；旧资产／market／模型恢复保留，01及12图的多用户与独立资讯边界无需改变。","diagrams":[]} -->
