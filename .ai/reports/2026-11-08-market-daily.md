# 全市场逐日浏览、可读行情图与首批真实证据

宿主：Mac mini / macOS；功能开发、原三项 CI / macOS 干净安装与受控常驻验收。Windows/Linux 原生交由对应设备。
原私网实测当前范围事件与评分运行均为零，日期轴按约八日标一格、画布无实际滚动空间，卡片曲线没有点位刻度。
本轮按用户批准方案把逐日选择和来源覆盖放到总览、把一次性预检与导入放到研究工作台；缺证据保留，正式分不启用。
真实上游原件、离线合同、源码与安装 CI、实际常驻及登录后数据验收各自留证，不能相互替代。

Product-Progress: updated — 市场逐日交互和明确的首批数据操作可见，进展保持验证中，实际导入另证。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"原综合总览与研究工作台增加日期/图表交互和显式操作面板，不新增壳或路由。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原账号网关和明确动作Host校验覆盖新增一次性入口，继续使用账号内原件与存储。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新增固定前版和载荷的Native模式，原主实例/网关、三锁、保全恢复及关闭门不变。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks和Mac安装步骤覆盖追加合同，任务源、CI、Native及真实资料分开留证，不新增工作流节点。","diagrams":["08-iteration-docs"]} -->

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"首批资料复用已有公开来源与账号原件归档，显示的原值与原生资格核验不混用，不增加数据服务。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow","11-hot-events","13-market-overview","15-inbound-mcp"]} -->
<!-- architecture-review {"group":"event-research","structure":"unchanged","reason":"原事件与评分域增加明确的预检和一次性操作，候选事实、原值、研究资格及正式开关分离。","diagrams":["14-event-research"]} -->

首轮本机回归在 `311a283a` 发现 NYSE 同一脚注换行导致错误拒绝，保留原失败批次和临时根。
修复只归一化同一文本节点中的空白；新载荷以新候选验证，不改写旧回执。
邻近回归校正来源目录和总览 HTTP 夹具：明确校对九个来源及其关闭状态，
并让两条新增只读请求通过真实路由，继续比较账户文件指纹和存储内容。

Research Web Checks `42409469688` 在原入口脚本健康余量的三个合同失败；
原脚本 260195 字节，高于保留 2 KiB 余量后的 260096 字节上限。
修复由市场工作区包装一次根视图绘制，保留捕获、绘制、恢复的次序及原市场路由保护；
新脚本 260094 字节，健康探针与上限不变。新候选必须重新通过三个 CI。
