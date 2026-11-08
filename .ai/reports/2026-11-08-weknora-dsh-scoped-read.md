# WeKnora 资料单轮读取候选

macOS Mac mini Web 功能开发。基线 `79102a95a267044c4a28b1818a9181f788be77fd`。
工作树使用受管任务 `rwb-weknora-dsh-20261108` 独立创建。源码接入认证消息授权、
私有只读工具桥和原生首轮请求复核。评审指出的提前封存、原生请求绑定、升级竞态、
索引失败还原和冻结定位问题已在候选中处理。固定 DSH 源码审查核对原生请求 ID
与首轮编号，真实 DSH 执行仍独立验收。

## 本机证据与阻断

- Git 安全预检通过。Docker Desktop 安装存在，当前 daemon socket 无法连接。
  宿主观察到约 41 GiB 可用，未通过完整 Docker 容量准入。构建与 Go／Vue 运行均未执行。
  保留 2026-11-06 上游初始化与编译容量失败回执。
- 首批 WIP 认证 API 7 项通过。受管批次封存后发现复制的会话资源带 macOS 文件标志
  `0x40`，回收拒绝 `nested_identity`。保留原临时根、JUnit 和退出码，未创建第二个
  pytest 临时根。这批结果早于审查修正，不作为最终候选回归。
- 真实上游、Embedding、零生成、双用户撤权、20 题及原周报语料仍待验。既有模型预算档
  未提供适用于本工具的实际发送硬限额，且未获本轮模型凭据和调用授权。真实 DSH 记为
  `BLOCKED`。收口不跨入生产迁移、周报交接和常驻切换。

## 最终离线核验

- 固定 DSH 工具单项登记、精确原生请求/取消竞态与协议检查合计 83 PASS。
- 原生桥及质量工具 Node 回归 45 PASS／1 SKIP。架构、文档、Actions 与平台治理组合
  120 PASS。完整变更集 Router 为 L4，项目约束、API 清单和架构图同哈希截图检查通过。
- 全量原生目录探针还暴露历史目录合同漂移。旧夹具漏挂问答和专家工具，临时补挂后
  发现脚本的既有 `report_plan` 参数目录缺失。本任务只新增当前资料工具的定向合同验证，
  保留宽探针两次失败记录。最终完整 HTTP、其他 Router Python 项及候选 CI 待验。

## 结构复核

<!-- architecture-review {"group": "research-api", "structure": "changed", "reason": "认证消息受理记录绑定批准范围与原生首轮，私有桥校验同一原生请求。", "diagrams": ["04-data-file-flow"]} -->
<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "复用实例私有认证通道，知识读取走专用范围服务，金融供应商和快照拓扑延续。", "diagrams": []} -->
<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "资料范围只由手动认证提交授予，自动化任务继续使用原有准入和调用边。", "diagrams": []} -->
<!-- architecture-review {"group": "files", "structure": "unchanged", "reason": "会话索引承载单轮封存，原件仍由现有冻结服务核验并保存。", "diagrams": []} -->
<!-- architecture-review {"group": "runtime", "structure": "changed", "reason": "固定原生首轮从现有私有桥读取已批准范围中的资料分块。", "diagrams": ["04-data-file-flow"]} -->
<!-- architecture-review {"group": "capabilities", "structure": "unchanged", "reason": "新增原生只读工具声明，目录和授权机制均沿用既有分类和运行边。", "diagrams": []} -->
<!-- architecture-review {"group": "private-multiuser", "structure": "changed", "reason": "实例私有白名单增加仅当前原生请求能使用的资料回调，继续由账号独立核权。", "diagrams": ["04-data-file-flow"]} -->
<!-- architecture-review {"group": "knowledge-backend", "structure": "changed", "reason": "批准范围接入原生单轮回调，资料冻结独立保留用户写权限。", "diagrams": ["04-data-file-flow"]} -->

## Docker 恢复后的核对

Mac mini Docker daemon 后续已可连接，Linux ARM64、虚机总内存约 11.7 GiB，宿主
可用盘约 40 GiB。总分配内存不是现场空闲内存。当前发现的 Go SDK 镜像确为 ARM64
且 digest 与旧回执一致。未取得标准五组件实际镜像及峰值容量证明，隔离构建准入保持
`BLOCKED`，本任务未消耗计划中的一次构建尝试。

只读复用前一窗口结果。私有 ARM64 Lite 进程健康、双账号私有隔离、viewer 共享、
撤权、过期 JWT 和生成路由拒绝已有独立证据。后续隔离生产前端/回环服务和合成向量
回执也已存在，资源已退役、供应商请求为零。这些回执绑定 Lite 试点，不覆盖标准栈
装配、真实 Embedding 或本任务候选的 DSH 回合。保全引用为私有验收根下的
`sqlite-acl-06/result.json`、`formal-pilot/operator-run/result.json`、
`synthetic-recovery/recovery-run/synthetic-result.json` 和
`rwb-host-readonly/host-read-run/result.json`。

## 公开试点语料与问题草案

以北京时间 2026-10-30 23:59:59 为截止点。原周报窗口未提供冻结清单时，
使用以下公开语料。入库时核实文件字节、原件 SHA-256 和获准外发范围，
将来源键解析为实际文档 ID，人工核对分块定位与引文哈希后才冻结正式 gold。
下列问题在任何检索前确定，尚未采集结果或授予外发许可。

| 来源键 | 公开来源 |
| --- | --- |
| INDEX | [证监会指数基金指引及公告](https://www.csrc.gov.cn/csrc/c101877/c1415875/content.shtml) |
| MARKET | [上交所 ETF 行业发展报告（2026）](https://etf.sse.com.cn/fundtrends/c/10808765/files/31409f49c20a4ca6944fb4cfd387cff8.pdf) |
| ACTIVE | [上交所 2026-10-19 主动 ETF 获批公告](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20261019_10835135.shtml) |
| FUND | [589080 基金 2025 年年度报告](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-03-31/589080_20260331_ATFA.pdf) |

| 题号 | 问题 | 预期来源 |
| --- | --- | --- |
| pub-01 | 申请募集指数基金时，对成份券的分散程度、流动性和容量有哪些要求？ | INDEX |
| pub-02 | 指数许可费能不能从基金资产列支，应由谁承担？ | INDEX |
| pub-03 | 指数成份券面临退市风险，而指数公司还没调仓时，管理人能依据什么原则处理？ | INDEX |
| pub-04 | 招募说明书应为投资者提供哪些指数编制和查询信息？ | INDEX |
| pub-05 | ETF 上市前需要完成什么与标的指数相关的工作？ | INDEX |
| pub-06 | 上交所 2025 年 ETF 全年成交和日均成交各采用什么口径？ | MARKET |
| pub-07 | 2025 年沪市股票、债券、跨境和商品 ETF 的成交分布在哪里披露？ | MARKET |
| pub-08 | 截至 2025 年末，科创板 ETF 中有多少进入互联互通？ | MARKET |
| pub-09 | 华夏科创 50 ETF 在泰国的跨境上市采用了什么产品形式？ | MARKET |
| pub-10 | 2025 年科创 50 ETF 期权成交规模和权利金如何披露？ | MARKET |
| pub-11 | 上交所首批主动 ETF 获批的具体日期与审批机构是什么？ | ACTIVE |
| pub-12 | 首批主动 ETF 的投资策略覆盖哪些方向？ | ACTIVE |
| pub-13 | 获批公告怎样描述主动管理与 ETF 交易形式的结合？ | ACTIVE |
| pub-14 | 到 2026 年 9 月底，上交所上市 ETF 的数量和规模是多少？ | ACTIVE |
| pub-15 | 该获批公告怎样描述中长期资金在沪市 ETF 的持有规模和占比？ | ACTIVE |
| pub-16 | 589080 基金合同何时生效，年报为什么按不足一年披露？ | FUND |
| pub-17 | 589080 从合同生效到年末，基金净值与比较基准的累计收益在哪里对照？ | FUND |
| pub-18 | 589080 年报如何说明到报告期末的建仓和资产配置比例？ | FUND |
| pub-19 | 589080 在 2025 年末前是否进行过利润分配？ | FUND |
| pub-20 | 589080 年报用哪些指标监测市场价格波动风险？ | FUND |

## 接续本机回归

首个 WIP 临时根与候选 `0509a7357` 的完整 WeKnora HTTP 批次已按原受管入口回收。
后一批 8 PASS。两批均保留原始封存回执。针对 16 个受管普通文件分别核对
inode、设备、owner、单链接、无占用、候选资源字节和 `UF_TRACKED`，清除此位后
由原命令验收证据并退休。Mac mini 实测 `copy2` 继承该标志，`copy` 保持字节与
文件模式且不继承。会话创建和恢复两处统一按后者复制。

接续候选复审补齐两处失败分支。场景与证据交接会话不得借普通研究 scope 扩大既有
截止范围。索引临时文件创建失败按原 StoreError 合同回传，未派发授权回滚。
复现保留在任务日志。现有公开样本的三份 PDF 已核实文本层，四份原件均记录字节与
SHA-256，20 题草案绑定到原件哈希。实际文档 ID、分块及检索结果仍待试点。
Docker Hub 五个 ARM64 元数据查询在 Mac mini 超时，未把标签、Lite 容量或
前一轮本地镜像用作标准栈构建准入证明。
