# 资产v5业务索引预检修复

组合版额外修复安装清单：PR188修改web.lock，仅更新code_commit会触发Doctor web_lock_mismatch。新增target_manifest仅v5固定已审88ef锁SHA256 `7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`；配置校验仍精确接受原/目标两种清单，回滚恢复原始清单，旧profile及v4 journal不变。先写八profile清单回归均失败后实现，最终完整回归另留日志。三个wheel已按原锁哈希下载，wheel metadata依赖在生产venv均满足，尚未安装。实际安装须对原有包版本保全并pip check；该前提不能用清单字段替代。数据库不启用不迁移，外盘不改。

## PR188合流后的当前候选

主线已合并DataHub研究仓产品`88ef3817680ac822e2d7c819db845de4b7275173`，包含资产PR185产品9bc4。用户当前明确批准“组合验收后一起部署”，包括已合并锁定baostock0.9.4／psycopg3.3.6进入常驻；数据库不启用、不迁移、外盘不改，不新增服务或DB连接配置。尚未成功部署的v5由root将PAYLOAD固定为完整88ef，PREVIOUS仍51f09，旧profile保持；源码常量／兼容测试及实际部署由root负责。

阅读入口与Atlas采用已提交组合产品88ef；该提交没有v5一行读取修复，修复源码单独保留为[8f2cb39a](https://github.com/Leon-Huang001208/ResearchWorkbench/blob/8f2cb39a63c99c6e64875daf21dbb8b07518ff43/research_workbench_entrypoint/resident/model_provider_upgrade.py)。最终包含两者及新PAYLOAD常量的操作员提交须在合流后另行绑定，不能把88ef链接误当作读取修复已在该提交内。

主任务已核定旧候选`a114beeabadc88a018872e997387978a934d805e`原三CI全PASS；PR188前进后，这些PASS仍只属于旧树，新组合的本机兼容、独评、原三CI与同候选Mac安装必须重验。更早CI39794625674的文档缺失FAIL记录同样保留，不被后续通过覆盖。当前尚未部署，本次文档不安装包、启用数据库或执行切换。

合流保留双方模块／API／证据边界：map为23组、321条API声明／318唯一接口；PR188实际新增的04研究仓数据流、HTML与visual-review保留其原字节。v5读取修复自身结构不变与PR188数据流扩展分别评审，不以选择旧图或单边生成物解决冲突。下述“无新依赖／图源不变”及24路径结果均是原8f／a114阶段范围，不提升为新组合结论。

主任务已实际报告组合部署工具769、资产／Broker／Provider／活动状态278，以及JS965 PASS／2 skip；锁内三份wheel已下载并核验哈希，尚未安装常驻。这些检查点与新候选CI、安装终态、数据库启用及实际部署分别记录。文档合流另以双方完整118路径及相对88ef的净24路径运行constraints／doc-sync，均0 violations；governance804文件通过，四个文档JS模块112 PASS／0 skip，官方Atlas与Python索引check通过。完整argv与日志保存在`logs/asset-index-fix-docs-impl/pr188-*`；最终提交后仍由root重绑Git候选及原三CI，本文不冒充该候选已通过CI或部署。

宿主macOS Mac mini，Web部署工具修复。任务 `asset-v5-index-fix-20261022`，基线PR186合并240bbac。实际apply-assets-v5停机前拒绝 `resident_record_invalid`：verify_primary误用1 MB元数据读取器读取业务index。服务仍为51f09，无journal、无业务索引裁剪。原失败日志保留于Git common delivery evidence与用户home logs/model-upgrade.log。

仅将v5加入已有64 MiB业务读取绑定，保留普通文件、非符号链接、大小、JSON对象校验及全部保全/恢复门；旧profile不变。新增真实故障回归在修复前1失败2通过，另保留五种旧读取绑定回归。初次测试误载legacy根conftest缺SQLAlchemy，随后采用现有CI的confcutdir，不安装依赖。完整本地回归、Router、独立评审、原三CI与Mac干净安装及实际部署待最终证据分别绑定。Windows/Linux原生未执行，不冒充通过。

没有新服务、HTTP、数据流、持久格式、依赖或权限；controller/evidence字节及固定PREVIOUS/PAYLOAD不变，图文拓扑保持准确。常驻切换继续遵循既有授权、空闲与全账号保全检查。

## 候选与原失败记录

已提交修复集成为`8f2cb39a63c99c6e64875daf21dbb8b07518ff43`，相对PR186基线`240bbac3fd3ea22c87145e34aa00715e74cebc88`只有v5复用既有业务读取器的一行源修复、近处回归及文档。固定PREVIOUS仍51f09，固定产品仍PR185 merge9bc4；阅读入口说明源码绑定8f2cb39a，产品身份不随文档修补改变。

PR187 Project Constraints run39794625674真实失败，原因是未同步双运行时／多用户映射要求的模块文档、README复核回执及meaningful structure decision；原日志保留`logs/asset-index-fix/constraints-failed.log`，后续本地文档检查或新CI不改写该run为PASS。补入实际读取／保全边界后须正常提交，重新绑定原三CI及同候选Mac干净安装；本报告仍未部署。

## 文档与验收边界

| 变更 | 实际影响／验证边界 |
| --- | --- |
| verify_primary的v5读取绑定 | 业务索引沿既有64 MiB安全读取器，1 MB元数据及旧profile保持；源回归与独评由主任务负责 |
| 双运行时与多用户模块文档 | 架构01–05、installation、docker、platform、ai-news、ETF production分别说明保全及无影响依据，不增加节点或资料路径 |
| 根README／四字段回执 | 说明停机前错误拒绝、业务与元数据容量区分；保留历史profile、固定产品、失败CI和未部署状态 |
| architecture-map／官方阅读页 | 只固定已提交说明源码8f2cb39a；318条声明／315唯一HTTP及全部图源保持，不以重画图掩盖结构未变 |

主任务已取得本机769＋112及独评173项检查点，具体候选及原始日志分别保留；这些不是文档补齐后CI或实际切换的证明。此次文档执行的完整changed-set Router、constraints、doc-sync、官方生成检查与文档回归另留`logs/asset-index-fix-docs-impl/`；执行结果据该目录真实回执记录，不提前标PASS。修补候选三CI、Mac安装、实际运行版本、全账号保全与真实认证页面仍待root分别绑定。

本轮文档检查已实际完成：以PR186真实merge240bbac为基线的完整24路径constraints为0 violations，doc-sync及799文件governance通过；Git绑定Router plan v4保持L4／unknown-boundary并补选既有catalog的原三CI，未改门。Router文档闭包四个JS模块112 PASS／0 skip，test_documentation.py与test_doc_sync.py共29 PASS、1项第三方Starlette弃用警告。Python索引官方重生成字节不变；Atlas／阅读页只更新说明源码链接，官方check通过，图源和图HTML／PNG不改。完整argv、日志及文件哈希交接在`logs/asset-index-fix-docs-impl/`；这些PASS仅属于本轮本机文档范围，原CI39794625674仍为失败，新候选CI及部署仍待验。

安装五文件继续核对：requirements/web.in、web.lock、scripts/setup_web.py、research-web-installation.md及research-web-bootstrap.yml。无新增依赖／workflow／安装器字节，不安装包；三个一键入口、固定DSH和同候选Mac的3081／8088／Doctor门保持。Windows／Linux原生、Docker产品层及资源清理不因本次读取修复获得通过声明。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"本修复只给既有Native操作员verify_primary的v5分支绑定已有64 MiB业务读取器，元数据与旧profile不变；原主实例／网关、锁、version4事务、账号根和恢复边界没有新节点、HTTP或格式，01部署图与12资讯图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"v5大索引预检复用原安全读取，不增账号、角色、秘密namespace或数据归属；全部账号索引不裁剪并继续严格保全，BirthFence、空闲准入与旧profile恢复不变，现有01及12图的多用户边界无需重画。","diagrams":[]} -->
