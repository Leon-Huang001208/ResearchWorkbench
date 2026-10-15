# Claw 重做：本地验收收口

宿主为 Mac mini/macOS，功能开发，范围为 Web、独立 Native 与本机浏览器。实现提交55ff00c6a，集成源码6370ceed447b89a4a17cfb5058c554c87ce3fe85已保留master的PR102历史模式修复。此报告记录实际本地证据；候选与CI身份以绑定plan/receipt为准，不自引用报告提交。

## 每日收盘点评真实主线

已通过原生对话完成缺参澄清、确认创建并启用、第一次试跑、澄清“增加”的修改意图、确认同一任务v2、再次试跑及最终结果查询。没有伪造Skill，也没有创建后自动运行。任务ID为automation-4cd751c08c243e16644dd8c8b5fe0a25f933502b2873b2d5539d6ede6896231e。

| 定义 | 真实运行 | DSH执行会话 | 交付 |
| --- | --- | --- | --- |
| v1 | automation-run-26f89ff629f6491f8aa71fe832d6dabe | 9afbf684-3bf3-480c-92a6-da7b1349c78e | 原生completed、非空回复、Markdown12980字节，SHA256 dcb97c4b4724091f2aa3db6957a9773cbdaad5e9dd94dd08c4d87cf72b693d9d |
| v2 | automation-run-254722ddc3d840f2b9a98cf389686981 | 40820bb3-86b3-4d72-828f-89b83554abfc | 原生completed、非空回复、Markdown12859字节，SHA256 f0e9019ae4f20e5be0568478ad1c3020dbfb05aed9940fe586696027b734212e |

恢复候选后再次下载两份文件，状态、字节数、摘要与项目归属一致。任务仍为v2且启用；周一至周五15:30/Asia/Shanghai，下次执行2026-10-14T07:30:00Z。修改与手动运行没有改变模型、权限或下一次计划。星期集合不等于交易日历。

之前的截断运行保留为失败。原生事件证明4096输出上限曾导致max-tokens与空内容；owned overlay改为有界16384后v2完成文件交付，不修改失败历史、不自动重试。金融内容覆盖仍受限：指数行情缺失、未识别标的不能当指数、T-1日期表述存在错误；这里只认证交互/执行/文件交付，不认证完整金融分析。

## 布局、来源和拒绝边界

1440桌面为72px模块轨、280px内侧栏和画布；收起后按钮可见，Enter能展开并恢复焦点。1050抽屉/Escape、390移动遮罩/展开均已验证，无水平溢出；深浅主题与中央首页编辑器/案例卡已截图。示例只填草稿，能力和连接由能力中心统一管理，Agent日程单独显示任务与真实运行。

创建项目、移入原对话和两个执行会话、聚合两份实际文件，显式选择接收会话后引用。实际刷新曾丢来源展示字段，已修复有界白名单持久化；重新显式引用并刷新后，原文件名与来源入口保留，发送仍仅使用真实副本ID。独立测试项目归档后可恢复。旧草稿不自动补造来源或读取其他会话。

原生提问确认精确绑定规范问题中的名称、ID、版本；否定、解释、另一任务、过期版本、未确认RPC均不能授权试跑。并发更新CAS、重复确认、启用失败重试、取消、删除后重放、运行快照、时区及旧记录兼容有回归。历史展示容错不解除严格执行检查；未知子会话活动保持真实，禁止猜测模式与读取历史。

## 实际验证

- 集成源码完整Router Python：944 PASS、1既有SKIP，793.98秒，/tmp/claw-router-python-integrated-final.log。全目录首轮失败均已修复对应测试夹具/断言，并完成失败文件闭包，未新增跳过或降低生产门。
- Router JavaScript：449 PASS、1既有SKIP，/tmp/claw-router-js-storage-final.log；引用持久化与渲染独立复审70例通过。
- Ruff、Black、isort相关22文件及mypy10源码通过；项目约束、架构、文档治理、Python索引通过。源码/历史合并与JS独立复审均Approve。
- 通过公开SetupWebInstaller为授权候选repair/no-start，固定web.lock/CJPY/DSH不变；随后18190/13190恢复owned健康，rwb web doctor --json为ok。数据、模型凭据与两次文件保留，正式服务未操作。

完整日志、原生事件、文件与截图位于授权候选的acceptance/claw-redo-20261013/evidence。最终事实native-restored-facts.json、两个trial-native-proof、claw-schedules-two-success.jpg、claw-v2-source-file.jpg、claw-explicit-reference-refresh.jpg及深浅/移动截图可定点核对。

## 尚未闭合

当前仓库PUBLIC；最近五次成功macOS Bootstrap实际job为546/502/520/366/472秒。此轮推送、PR及绑定候选的macOS/通用CI尚未授权或执行，仍为NOT_RUN。合并、正式部署及工作区清理没有此轮授权。Windows/Linux原生由对应真机接手，NOT_RUN；不由模拟单元或Ubuntu通用CI冒充产品验收。

参考Chrome原生并排截图因Mac锁定BLOCKED，已请求解锁；候选IAB与本地验证继续。取得该证据与所需CI前，不记录整个任务完成。金融覆盖保持受限，不以合成资料填补。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"仅汇总既有任务的本地验证与真实状态，不引入新执行节点、接口或发布授权。","diagrams":[]} -->
