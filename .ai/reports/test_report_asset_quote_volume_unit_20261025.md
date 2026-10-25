# 当前交付范围更新（2026-10-26）

按统一部署协调已确认的B分工，本轮最终diff撤下未合入、未上线的V10草稿，仅保留单位业务修复、测试与证据；旧V10提交和CI保留在原祖先，不改写或删除历史。Native操作员和其测试已逐字恢复为当前origin/master，因此V1–V9及主线Wind恢复准备不变。下文V10过程属于历史记录，不代表最终提供该模式或授权其部署。新组合与新controller由独立受审任务负责；旧现场仍NO-GO，未执行任何服务、Excel、工作簿、凭据、数据或模型操作。

# 报价成交量单位修复

宿主macOS；Web功能修复，最终Native常驻部署另验。任务asset-quote-volume-unit-20261025，基线f71c8063；现驻留b800e503。本报告不将源码/隔离源验证当常驻成功。

## 缺陷与来源事实

实页主图显示46.03万手，右侧4602.71万且提示源单位未提供。根因是CJPY同一get_market_data(day)路径中，market_bars标注原生vol单位，market_snapshot截取最后行后返回普通rows，fetch默认把各字段单位置空。不是成交量原数不同，也不在前端按来源/数量级补猜。

独立专用CJPY0.5.2客户端读取list_market_fields（markettable_columns）返回53字段，vol规则明确“股票：股”，amount规则“股票：元”。规范JSON（UTF-8、sort_keys、紧凑分隔）hash458a5aaf5495d776d9391ac246daa360808fe2ce5c35be057e235451b28b8705。本次新snapshot合同独立保存该hash，未改旧bars合同和27df...证据。

真实数据单独存于本机私有logs/asset-quote-volume-unit-20261025：live-unit-proof.json、vendor-market-field-dictionary.json、fixed-live-workspace-proof.json。未把53字段全包或凭据提交Git。2026-10-23 SH603986实际返回vol46027129、amount12917512995、close292；旧Provider的vol.unit=null，新隔离真实AssetWorkspace→DataHub→Broker→Provider→Snapshot字段为share。实际右侧组件渲染46.03万手；原rows不除100、不改变金额或币种。该探针为报价/投影验证，历史任务和部署后同日主副图对账另验。

## 变更与边界

仅精确SDK0.5.2、显式stock、实际day周期、规范沪深单证券及返回别名身份一致时，对新snapshot原生vol/amount发布share/元证据。未知SDK、未声明类型、非股票、BJ、冲突身份与未证明volume别名不猜单位。零保持零。前端沿用既有100股/手formatter，不增加跨快照借单位。旧冻结manifest/rows字节保留，overview显式刷新才生成有单位的新快照。沿用最后返回行行为，本次不额外保证供应商排序或最大日期。

## 已执行

- 最小回归：修改Provider前3失败/8通过，失败均为snapshot单位None而期望share；修后11通过。
- 扩展至真实AssetWorkspace/按区块刷新/Broker/Provider（只替SDK，未替DataHub.query），验证旧冻结字节不变。
- 当前test_datahub_cjpy.py 61通过；JS行情条8通过（含原生vol字段、canonical历史单位对齐、旧unknown不补、输入不变）。
- 独立Python评审61通过、ruff/black通过、未发现阻断；独立JS评审Node24三个相关文件30通过，Approve。最终SHA绑定复核待交付候选。
- 真实SDK数据和测试合成fixture分开，未安装依赖、未改系统配置、未调用模型、未写生产观察或旧证据。

本机环境说明：开发/测试venv的云占位pycache和无关dist-info entry_points导致启动等待，未将其叫作业务RED。专用只读探针在取凭据/发请求前的导入等待已对自有进程SIGINT；生产venv只作解释器/依赖读取，未安装包。测试使用已安装Web运行依赖与原etf-excel-first测试依赖，私有PYTHONPYCACHEPREFIX；本机显式加载现有pytest_asyncio对象避免无关entry-point扫描，--confcutdir=tests/research_web与原CI相同。CI配置/插件环境及必需检查不改；最终CI不能用本地结果替代。

首个手工投影探针误把quote dataset作为history dataset，chart规范volume元数据不符，失败保留为探针输入协议问题；修正探针仅验证真实报价右侧，主图接口由独立canonical fixture覆盖，实际生产同日对账待部署。没有为让探针通过而改前端字段推断。

## 待完成

完整Router与本地静态/相邻回归、独立最终SHA复核、原三CI/同候选macos-14干净安装；固定新产品SHA及b800前版的封闭部署profile与原完整idle/恢复/保全门；认证实页刷新新报价后，核对主读数/成交量副图/右侧同日同单位同值，以及红绿/月K/页签无回归。Windows/Linux原生验收不由Mac冒充。尚未部署本修复，不宣称收尾cleaned。

## 封闭部署候选

产品检查点9142016accd6994673abe15a8d418a494e9b0f1b已冻结。新增V10固定前版b800，不复用旧weekly admission mode、不运行旧维护动作；Source reader/hash/web锁沿V9，不重写旧常量。profile注册前最小测试以model_upgrade_profile_unknown真实失败；注册后目标32项通过，完整旧/新矩阵2758项全部通过，219.02秒（1项原Starlette弃用警告）；旧/新恢复、保全和失败拒绝均保留。来源/产品修复与操作员在同一普通祖先链，由最终组合自身重新验证、评审和CI。

类型检查曾发现抽出cycle后的None-key问题，已用显式str分支保留SDK缺省/None原行为，mypy对Provider一文件实际通过；不是通过skip导入或改检查级别掩盖。

## 结构复核

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "最终diff不修改Native操作员或部署profile，原主实例、网关、锁、恢复、安装和所有旧模式逐字保留；V10草稿只作为历史提交，不提供新的运行入口。", "diagrams": []} -->
<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "新报价单位只作为现有Provider Result字段证据沿Broker和Snapshots传递，纯显示股转手不写raw，不新增Provider、仓库桥、HTTP边或历史PIT资格。", "diagrams": []} -->
<!-- architecture-review {"group": "private-multiuser", "structure": "unchanged", "reason": "报价单位字段沿原账号DataHub、RuntimePool、用户根和来源授权传递；最终diff没有Native或部署模式变化，不修改登录有效期、Token、租户策略或跨账号访问。", "diagrams": []} -->

## 最新基线与部署范围

PR233在集成前合入主线7408e1d3，包含月度宏观字段证据及浦发2026H1财务原件核验等额外生产路径。单修复9142016的冻结门正确拒绝未冻结组合，未绕过。集成普通merge9b6ba57a保留两者祖先，作为待审组合产品冻结；V10仅把payload改为该精确组合，前版仍b800、原门不变。用户额外部署范围问题已单独提出，尚待答复；可先完成源码候选验证/CI，但未获得允许前不得调用apply。若用户选择不纳入，则本轮不切换服务，不能用已授权单位修复冒充PR233授权。

## 主线初始化修复后的本候选重验（2026-10-26）

已普通合入实际主线PR240 cf2830aa（包括先前239/238），未复制未合入源码。合并点87a0714e上，原3项SDK/市场resident API失败用例实际3PASS/4.88s，Junit及日志api-regression-after-cf保留；旧f5及精确旧主线4c的3FAIL不回改。Native操作员/main/service/catalog及其API测试相对新主线无差异；本任务仍只有CJPY单位业务、原JS回归与文档。完整API及Router/独评/原三CI仍须按新最终候选重新执行，不能借父PR结果认证。旧b800现场NO-GO不变，未操作服务、模型、Excel、供应商或原数据。
