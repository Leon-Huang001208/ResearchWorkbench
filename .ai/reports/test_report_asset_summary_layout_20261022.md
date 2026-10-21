# 资产观察摘要布局与主题：源码检查点

宿主为macOS，本任务为Web功能开发并已获用户明确常驻部署授权。本文先记录源码工作，后续CI、实际部署及资源收尾由绑定候选的私有回执补充；未执行项不据此宣布通过。

## 已批准范围

资产栏、交易/估值分组、默认收起的来源口径汇总及研究卡片密度按批准方案实现。PB与PB-MRQ分开，PS-TTM只接受明确TTM字段；Wind总股本单位未核实，不参与市值派生。实际供应商接入、HTTP请求、观察持久化及历史快照未扩展或重写。用户追加授权取消图表独立背景：主图/四副图/筹码画布透明，文字、网格、tooltip和中性区域随RWB主题，语义线色、公式、尺寸与联动保持。

使用已批准本地ECharts5.5.0与Chart.js4.4.7，无新依赖、CDN或模型调用。来源摘要从当前已加载行和快照元数据投影，不额外查询。原日历范围硬门、账号和证券身份、迟到响应、局部失败及已冻结研究交接边界保持。

## 验证状态

- 新估值/覆盖及页面边界目标测试39项PASS，含未采集区块不继承全局请求来源/范围、首次分页短读和比例单位。
- 图表主题目标42项PASS，含真实固定ECharts深→浅→深及18个series view、原生缩放、键盘和取消恢复；日志`logs/summary-theme/`。
- 完整浏览器最终attempt3：离线原版对照30/30、真实CJPY冻结数据读回4/4 PASS，80张截图，0控制台错误/外部请求/模型/供应商调用；10组宽度/主题中主图canvas与原版逐项等宽。两套运行原始与产品source hashes首尾一致。日志`logs/asset-summary-layout-20261022/browser-*-attempt3/`。真实CJPY仅使用已获授权的243条冻结日线读回，不把快照称为实时。
- 红灯证据保留：初轮遗留全局CSS背景覆盖透明canvas，补局部background透明；独立评审发现首次分页短读误称保留旧快照、浏览器发现派生涨跌幅继承每股/币种单位，已补红绿回归并修复。延迟刷新/主题重挂载测试同步也按真实生命周期修正，保留原检查与全部失败日志。
- 独立JS规格/质量评审APPROVE，六文件109/109 PASS，最终14文件摘要见`logs/summary-review/review-final.json`。完整Router当前9项本地门全部PASS（21.398秒，L0→L4），日志`logs/summary-local-closure/results.json`；报告最终文字完成后再复查文档门。后续同候选macOS干净安装、实际部署和资源收尾由Git绑定回执补充，源码检查点不冒充未来验证。
- 其他平台原生产品验收交接NOT_RUN；常驻切换须在产品源码合并后正式新增版本化封闭联合升级profile，绑定现场previous和已审payload，不改现场控制器或自动白名单。

## 架构复核

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅重排已有资产组件、增加纯投影和默认折叠来源表，图表主题沿既有生命周期，未增节点。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"现有观察记录、读取取消与快照交接保持，前端估值和来源DTO不改变Host/Store路径。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"未增加或改变Method/Path、HTTP参数、认证或DSH协议。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api-contract","structure":"unchanged","reason":"字段增加属于已有冻结行的前端投影，观察请求及冻结格式保持兼容。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"保留现有Provider与Broker链路，来源表不发查询，未知字段和单位不伪造。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"只改Web UI资源，不增加依赖或Native/Docker服务节点，安装通过同候选Mac CI另证。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"不改账号、私有池、权限或数据根，资产和来源读取仍经原认证Host。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"沿现有Checks通配符和Mac Bootstrap验证，无新job、runner或平台dispatch。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"视觉及纯数据投影不新增Skill/Tool或研究引擎，DSH继续唯一执行。","diagrams":[]} -->
<!-- architecture-review {"group":"ai-news","structure":"unchanged","reason":"保留资产新闻公告的原独立阅读来源，未修改AI资讯worker、数据库或模型预算。","diagrams":[]} -->
