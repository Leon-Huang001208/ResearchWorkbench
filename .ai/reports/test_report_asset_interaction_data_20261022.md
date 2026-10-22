# 资产交互与结构化数据迭代：验收草稿

日期：2026-10-22。宿主：macOS Mac mini。任务类型：Web功能开发；本平台范围为本机macOS及同候选Mac CI。本文是当前实现／验证检查点，最终SHA、完整回归、认证浏览器、CI、部署与资源收尾仍由主任务绑定；不作为最终通过或跨平台支持证明。

## 范围与行为

- 单一沪深北A股搜索框按代码／名称／简拼选择，更多菜单保留其他操作；图下七个真实专题页签局部更新，同资产保留行情行引用及图表实例。宏观占位和重复新闻入口移除，原手工API／观察／数据保持兼容。
- 新证券自动概览→recent qfq历史，默认近120条；视区、日周月变化保持实际选中日与索引，只有“最新”显式回末日。大于600条历史、可见120条时保留蜡烛实体；累计筹码仍使用所选日前缀，不随视区改变。
- 新GET目录搜索无研究会话／模型；24小时账号与授权配置指纹缓存，冷启动合并、失败节流、未知pending保护、完整目录不在5000条截断。
- 新POST区块load补旧观察缺块，普通区块15分钟同条件缓存，显式来源／范围变化实际取数；成功缓存／合并也保存幂等签名，冲突409，失败503不启动新查询。初始／旧refresh／load共用锁；回滚保持其他活动区块及共享引用，旧快照可读，规范历史只由history-job发布。
- 天软封闭表／因子支持估值、同报告期财务、股东汇总／名单、行业分类、两融和公告事件；财务不受行情60日截断，不混报告版本。普通PB=PBLF、PBMRQ独立；未提供行业PE／PB、币种、资金流出或构成不补造，宏观／ETF／指数不由此次接入获得支持。

## 改动与证据映射

| 改动 | 定点回归 | 合同 |
| --- | --- | --- |
| AssetDirectory、DataHub目录授权、search路由 | test_asset_directory.py | UI、DataHub、03文件、04API、05安全 |
| load路由、区块缓存／幂等／锁／原位回滚、resident活动 | test_asset_loading.py、原workspace/history | API、存储、安全 |
| providers_cjpy_assets与已有Provider规范化／选源 | test_cjpy_asset_data.py、test_asset_provider_normalization.py、原Provider/Broker | DataHub、UI、开发映射 |
| 单搜索、专题controller、新闻缓存、日期／实体图形 | 搜索／专题／controller／图表JS、合成浏览器E2E | UI、架构／开发映射 |
| 原Checks追加四模块、Bootstrap静态清单加搜索模块 | 原Python及静态校验步骤；无新增job／runner／条件／依赖 | 安装文档及本报告 |

## 当前已取得的检查点

| 验证层 | 状态与边界 | 证据 |
| --- | --- | --- |
| 后端目录／加载／原资产／历史四模块 | 阶段PASS：114项，1项第三方Starlette弃用警告；后续root日期接线等变更须另绑定最终字节 | logs/asset-load-impl/backend-rollback-fixed.log |
| 独立后端评审 | 阶段APPROVE：仅当时锁定范围，四个已复现缺陷闭合；不套用后续改动 | logs/asset-backend-review/review-rollback-fixed.md、reviewed-rollback-fixed-files.sha256 |
| 后端格式／静态检查 | 定点ruff、black、isort通过；mypy五源模块无错误，保留既有未检查函数体说明 | logs/asset-load-impl/rollback-{ruff,black,isort,mypy}.log |
| 目录真实有限预检 | 5577/5577条；不证明每只证券所有数据能力 | logs/asset-data-preflight/normalized-directory.json |
| 七类结构化有限预检 | 根任务预检603986：估值1、财务12、股东汇总1／明细10、行业1、两融37、事件31行；非全市场／全历史证明 | logs/asset-data-preflight/normalized-*.json；只读计数与SHA见logs/asset-docs-impl/preflight-evidence-summary.json |
| 纯SDK／规范化fixtures | 根任务已报告局部11项纯SDK通过，最终合并测试数待记录 | 新两测试模块，主任务完整回归日志待绑定 |
| 本轮CI清单 | PASS：既有checks单job／原Python步骤51个模块条目，四新增模块各一次，旧核心模块保留 | logs/asset-docs-impl/ci-list-validation.log |
| Mac Bootstrap静态清单 | PASS：两名单只追加asset-search.mjs，16项包含原15项，原job／门保持；尚未执行远端安装CI | logs/asset-docs-impl/bootstrap-smoke-list-check.log |
| 完整文档门 | 当前tree PASS：架构／映射／API inventory／回执检查无违例，governance 789文件无违例；最终产品提交后仍复核 | logs/asset-docs-impl/full-doc-sync-final.log；早期失败保留 |
| 官方Python索引 | PASS：源码格式固定后官方重生成及check；后续Python AST若再变仍需重生成 | logs/asset-docs-impl/index-generation-final.log、index-check-final.log |
| 架构HTML／回执 | 02、04最终deliver均showcase9/9零错警告，四桌面包含性通过并已查看1440深色／2048浅色；04收窄尝试曾溢出，已按root确认恢复1900宽首版且spec／HTML hash相同，保留右侧留白说明 | outputs/research-web-architecture/02-module-dependencies.*、04-data-file-flow.*；失败在logs/asset-docs-impl/04-r2-failed/，恢复见04-visual-check-restored.stdout.json |
| 文档只读HTTP合同 | PASS：26项，1项第三方Starlette弃用警告 | logs/asset-docs-impl/documentation-tests.log |
| 官方Atlas／阅读入口 | 生成范围仅api-atlas.html和index.html；317源码声明／314唯一接口，官方check通过；最终源码链接SHA待主任务代码提交绑定 | logs/asset-docs-impl/atlas-generation-preview.json、atlas-generation.log、atlas-check.log |

复现和修复证据保留：日期／蜡烛实体的RED→GREEN位于logs/wind-date-impl/；来源／缓存幂等／旧刷新锁及并发回滚的RED→GREEN位于logs/asset-load-impl/。早期BLOCK及错误现场不删除，不以新APPROVE覆盖旧字节的结论。

root随后发现并修复冷启动日期接线：新缺失activity／margin持久默认上海时区近60日；events由保存截止日或当日派生60日，避免None／仅end_date的Provider拒绝，不扩RangeBlock。无日期及固定截止2026-10-21两条RED→GREEN见logs/asset-data-impl/lazy-range-{red,green}.log。这些新字节及cold overview hydrate仍由root单列回归和独评，不能沿用上述114项阶段结论。

文档生成实际使用本机既有Node24与Python3.12，不安装包。官方命令包括`generate_py_file_index.py`及`--check`、`check_doc_sync.py`、`build_research_web_api_atlas.mjs`及`--check`，以及Archify对02／04的validate／deliver／visual-check。完整执行器路径、argv与结果日志记录在私有`logs/asset-docs-impl/executed-commands.json`；结构图两个最终HTML均9/9、零错误／警告，自动visualReview仍为pending，已看图的独立记录位于visual-review.json。04不再扩几何优化，恢复已通过版面的动作和失败归档均保留。

## 必须继续记录的验收

| 验收 | 当前状态 |
| --- | --- |
| 最终候选全部Python／JavaScript、架构／完整性门 | 待主任务最终tree执行并记录；局部114项不能替代 |
| 合成浏览器E2E与冷启动overview hydrate | 进行中，结果待UI／root记录；不能先写PASS |
| 真实认证浏览器：搜索、切证券／专题、按需缓存、来源字段、日期／筹码／蜡烛 | NOT_RUN／待主任务真实链路记录；有限Provider预检不替代 |
| 同候选Project Constraints／Research Web Checks／macos-14干净安装 | NOT_RUN／待CI；未发布候选前不沿用旧run |
| 固定DSH构建、3081／8088健康、rwb web doctor | 待同候选Mac Bootstrap；本机installed环境不作为安装PASS |
| Docker／Windows／Linux产品原生验收 | NOT_RUN，由相应平台任务负责；不冒充本Mac任务已验证 |
| 常驻部署、实际版本／认证页面、数据保全与回滚 | NOT_RUN／待正式受管事务；本文没有执行部署或处理秘密 |
| 归档、资源回收、Git清理与空间复查 | 待验收／合并后的主任务收尾；不标cleaned |

## 安装与限制

已核对requirements/web.in、requirements/web.lock、scripts/setup_web.py、research-web-installation.md及research-web-bootstrap.yml。沿现有CJPY、Web锁、DSH及本地图表依赖，未新增或安装Python／Node包；requirements/web.in、web.lock及setup_web.py无须改字节；Bootstrap两处原静态名单补asset-search.mjs，现16项，兼容性仍必须由最终同候选Mac安装CI证明。目录能搜索某证券不表示其所有Provider／历史数据均可调用，原封闭复权与平台门保留。源码合并、局部fixtures、数据预检和正式研究质量彼此独立，不增加模型或付费重试。

文档／CI收尾在扩展授权后编辑指定Markdown、架构map／细图及官方生成产物、Python索引和原CI测试列表；只读Git用于核对原细图／差异，没有Git修改／提交／发布、供应商／模型调用、依赖安装、生产更新或跨平台dispatch。日志和原始业务预检留在私有logs，不把原始数据／秘密复制到报告。

## 结构评审

02模块图增加Host内的账号目录缓存分支并明确搜索／按需入口；04保留原会话取数与不可变快照关系，扩展资产专题调用方并明确无会话目录不经过该发布链。既有DSH、Provider、框架、认证与部署节点不新增。API inventory登记两新端点，Atlas／阅读入口通过官方生成器更新；图与截图回执分别绑定，未检查的截图不写人工通过。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"资产由长页改为单搜索与真实专题，Host入口增加搜索及按需读取，02模块图反映现有浏览器到Host资产工作区及账号目录缓存；主题和框架部署边界保持。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"DataHub在原认证与CJPY单Future内增加无会话目录缓存及封闭结构化区块，02补账号缓存分支，04界定资产专题与DSH取数沿原会话快照且目录不进入该发布链。","diagrams":["02-module-dependencies","04-data-file-flow"]} -->
<!-- architecture-review {"group":"workbench","structure":"changed","reason":"AssetWorkspace新增目录搜索与按需load，旧观察可补块并保存来源范围和幂等元数据；02与04同步调用方、缓存归属和不可变快照边界，不新建研究引擎。","diagrams":["02-module-dependencies","04-data-file-flow"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"向现有Checks Python步骤追加四模块，并在原Mac Bootstrap静态名单补搜索模块；原job、runner、条件、依赖、平台归属和全部必需验收保持，08迭代流程图仍描述相同检查交付节点。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"Host增加账号目录及区块按需入口与持续活动witness，02补资产工作区／目录缓存模块，接口inventory登记两条HTTP；原DSH研究协议、运行状态和部署节点不变。","diagrams":["02-module-dependencies"]} -->
