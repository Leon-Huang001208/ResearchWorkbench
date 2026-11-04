# 事件与日历研究：结构审阅（2026-11-04）

本次仅记录候选的架构判断与文档影响，不认证业务、来源完整性或部署。新增实现位于既有Host：事件与报道、个人SQLite追加版本和原件、人工确认／冻结、确定性日历与事件研究、独立测试区间账本、市场研究评分及来源采集心跳。新增API和持久化是真实变更，不能用“旧部署图不变”概括为没有接口、存储或数据边变化。

## 图与抽象层次

旧部署、账号与研究协议图仍抽象为浏览器／Host／个人业务根／唯一DSH等角色；本轮未添加宿主服务、容器角色、第二研究引擎或跨tenant数据库。新细节集中在[14-event-research](../../outputs/research-web-architecture/14-event-research.html)，由主任务登记图源、模块组和安全阅读白名单。

原Automation增加确定性来源采集分支，属于结构变化；它仍用原心跳，不加第二timer。Native通用Automation开关与逐源启用均须成立；tenant采集通道保持禁用，不扩展discovery跟踪权，也不唤醒不相关历史生产者。

## 本次证据与未完成边界

图14交付回执记录9／9检查、0错误／0警告；规格SHA256为`30d7636cea819042b7f3b73628c6653b05b1357ec47b752e7195cb8519981c55`，HTML SHA256为`4672d1e941238d82a9bcdd54d2598f08e2b4e80edef6b4fef846957c7582c964`。四尺寸包含性回执为pass，主任务已实际观察浅／深色截图；读取时机器回执的`visualReview`字段仍为pending，不能把人工观察说成已改写该字段。

本次结构审阅时Native集成夹具仍在修复，Docker与CI为NOT_RUN；图文门、源码测试、公开源可达、业务准入、同候选Mac安装与真实常驻升级分别留证。其他平台保留对应设备验收，不新增Windows／Linux支持声明。来源受限、历史PIT与资格对账门详见[集成合同](../../docs/research-web-event-research.md)，原恢复／备份／未知任务保护不减。

## 机器结构决策

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"事件API、个人SQLite和资格对账标记新增于原Host与账户业务根；旧部署图仍以Native或Docker承载同一Host和唯一DSH为抽象，没有新服务、容器角色或端口。新增业务数据边在图14展开，不表示接口或存储未变。","diagrams":[]} -->

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"原浏览器产品壳新增时间线、事件研究与评分视图，仍通过既有认证Host边界工作；原部署和模块总图的浏览器/Host角色抽象保持，新视图的确认、冻结和资格流由图14详细展示。","diagrams":[]} -->

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"确有新增事件、研究和评分API及不可变记录；它们位于原Host业务边界内，不增加研究执行者或改变唯一DSH提交/质量角色。旧系统与协议图的角色层次保持，新API到存储和验证的详细流放在图14。","diagrams":[]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"新API继续由既有网关选择账号Host和Store根，事件元数据/原件不跨账户共享；没有新网关、跨tenant存储或授权主体。Native通用采集和tenant禁用分别保留，不从discovery窄跟踪权扩展事件采集权限。","diagrams":[]} -->

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"新增固定事件图、模块文档与API清单仍经原登记、扫描、Atlas、哈希及安全阅读白名单流程；更新的是内容和固定清单，不新增任意文件入口、文档服务或生成执行管线。","diagrams":[]} -->

<!-- architecture-review {"group":"automations","structure":"changed","reason":"原Automation心跳新增默认关闭的确定性来源采集边，绑定账户/逐源定义并在联网前持久claim、活动与失败未知状态；没有第二timer或模型自动研究，新增边在事件研究图14中明确展示。","diagrams":["14-event-research"]} -->

<!-- architecture-review {"group":"event-research","structure":"changed","reason":"新增来源候选到个人事件版本、人工确认和冻结、日历/行情输入、确定性研究、不可重用测试区间及评分资格的完整模块流；新增API、元数据、原件与失败边均由图14展开，实际有效性和业务验收仍单独认证。","diagrams":["14-event-research"]} -->
# 验证通道补充

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"事件功能仅扩展既有Checks分区的定点测试和原Mac Bootstrap静态资源核对，沿原runner、job、45分钟时限和受管临时根；不增加CI执行节点或放宽验收、额度、来源及模型权限。新领域数据流在14图单独展开，源码与真实运行仍分开认证。","diagrams":[]} -->

