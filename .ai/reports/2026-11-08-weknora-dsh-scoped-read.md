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
