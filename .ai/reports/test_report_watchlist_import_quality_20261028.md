# 自选导入质量问题闭环（待独立复核）

基线ec81ec71b9e6e5a2722585d9801a0ac7e4fad0ce。当前为macOS Web有限修复，root独占协调，未发布/部署。原SPEC整体已通过，本报告不替代其增量复核或两位原quality reviewer。

## P1原生文件跨owner

真实Chrome、真实custom element与updateAssetSummary先RED：B草稿sourceFile=false/filename空，但同节点原生files=1、oldFiles=1（logs/watchlist-quality-owner-red.log）。修复按owner+draft实例双重匹配复用，仅同owner保留控件。换账户清旧原生FileList、File/编码/选择/键/回执，retired scope（包含A→B→A）不接受旧File读取、preview、confirm回调；metadata及原create迟到响应仍按账户拒绝。同owner局部/完整重绘、metadata到达时File未完成场景保留。

实际Chrome A→B partial更新、同element重连回A、等待原完整File处理Promise后fresh A仍无文件/编码，B及回A期间旧CSV POST0。Node另覆盖retired preview/confirm和A metadata/create延迟响应不装入B。不是只清JS状态或静态attr断言；不把假fixture owner标签当真实系统登录证明，后端真实tenant隔离沿原Python门。

## Python主体类型检查

--check-untyped-defs在原配置5源先实证4错误：codes/names/existing缺注解、exact Optional未收窄（logs/watchlist-quality-mypy-strict-red.log），未证运行时None崩溃，不称修复崩溃。新增CSV/目录/行/目标/manifest/receipt/namespace的TypedDict及核心参数/返回注解，DTO/现有Store读取边界cast，关键映射明确类型，exact/selected显式收窄到稳定既有错误码。无全Any、type-ignore、mypy配置/业务字段扩大。normal与--check-untyped-defs均5源PASS，原unused override提示保留。

## 网络边界进一步收窄

早前Seatbelt允许all localhost且继承proxy环境，不能单由它排除借本机代理出网；review未见当前旅程实际代理泄露，不写成已泄露。现Host删除所有outbound许可，只保留localhost bind/inbound与已接收连接回包。运行器/Chrome剔除大小写HTTP/HTTPS/ALL/FTP/NO_PROXY和RESEARCH_CREDENTIAL_HOME，Host若残留即拒绝；客户端/audit/内存凭据后端及真实系统凭据拒绝均保持。没有修改产品默认采集配置。

research_web_watchlist_proxy.mjs仅创建本任务inert localhost sink，绝不转发外部，非真实29758或生产服务；向子进程注入11种合成proxy/凭据home键。native curl尝试借此sink被kernel EPERM，sink连接/请求0。随后同环境的原5+新4=9旅程PASS，两个Host均报告清理键、proxy keys[]、credential_home=false、所有受控客户端/socket/真实凭据调用0。负例与正常旅程分开计数；原218完成HTTP/200个2xx/GLD8的旧记录及纠正报告保持，不倒灌新0。

## 实际本地验证

新45个Python用例全部覆盖：19+20+7通过（1重叠），Store13、原自选/目录16，共74不同用例；全部在inbound-only子进程、清理后的环境执行。PID/opaque根身份与argv在logs/watchlist-quality-*.json，各组正常退出：24.181/32.833/10.293/0.374/2.541秒。B3及后续driver已设120秒进程上限；不将后来新增的上限回填到B1/B2旧回执。Node90通过；带受控proxy挑战的9真实浏览器旅程通过并绑定各自13源hash。mypy normal及strict5源PASS；类型/必要收窄不改变业务输出。余格式/完整性/source pin与独立复核另记，不把早期epoch改称新候选。

## 范围保持

app.mjs、Store保存算法、HTTP schema、目录/预算/事务语义、唯一DSH、凭据/依赖与常驻配置不变。无远端/真实供应商/模型/Keychain/安装/部署操作。本轮新测试根均有各epoch ledger，保留给复核，未宣称整任务cleaned；原8根精确收尾回执不改。

<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"只修客户端owner/draft文件隔离、补导入核心typing和必要收窄，既有HTTP/Store/目录与研究节点不新增；测试profile/proxy负例不改变产品拓扑或默认。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"原自选组件按owner和draft实例复用/销毁原生控件，保留同owner metadata/File场景，无新导航、API、服务或引擎，原UI到Host图保持。","diagrams":[]} -->
