# 独立报告生产工作区

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"新增报告业务前端路由和列表详情，但仍复用既有Web Host、Report Workflow API、状态和唯一DSH；没有新增服务、数据库或运行拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"生产、配置和历史共享原配置与运行证据，数据格式、后端路径及Host质量和定稿门保持；只是导航和所选Run的展示重组。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks通过JS通配符纳入新回归，Mac Bootstrap同一静态校验步骤增加两份文件，原三CI门和平台归属不变，无新job或依赖。","diagrams":[]} -->

## 范围与来源

宿主 macOS，Web功能开发；不是桌面打包或Windows/Linux适配。用户确认v0后实施真实组件，参考只读 AlphaFoundry 的生成优先、配置分栏、最近交付和桌面工具栏；保留RWB主题与唯一DSH。

旧主库只读fsck没有结果，未重写其对象、引用或锁。源码从同一 canonical GitHub remote 全新clone，独立 `git_safety check` fsck PASS、nativeLocks=[] 后由受管delivery创建worktree，base=1317968ea7e5e7227adbe9451882b381307438c2。旧库不因此被认证，原现场和所有预览数据保留。

## 变更

`#/reports` 项目目录及项目tab/run深链接；新增受原主管理员资格限制的主导航。能力中心取消前置独立报告区，通用Workflow保留。配置与历史复用原渲染，所选Run版本/用途/来源/质量不混用。执行操作沿原接口，重复提交有忙态拒绝，跨页迟到突变及回读不导航、不覆盖其他项目。所有失效文件入口封锁，取消和同ID核对不假报新执行。

## 验证记录

- Node定点先RED（缺少新模块），后目录/路由/权限/旧Run与文件测试通过。
- 首轮全JS保留失败：新轮询在模块加载时创建计时器，真实应用导入测试不能自然退出；改为仅可见活动生产页的有界只读定时刷新，离开清理。
- 全JS第二轮保留失败：原资产切页抽取夹具不包含新增timer变量；清理移至完整切页分支，保持资产同主题快捷路径。
- 独评发现并复现迟到响应、invalidated证据下载及取消/核对文案问题，修复后复审无P1/P2；实际新增10项定点通过。相关31项回归通过。
- 真实组件38992预览用独立空Host与既有4项目GET元数据快照，内存凭据、假Native、后台关闭、出站连接/进程启动及非GET拒绝。它不是生产验收。
- 完整JS：1511 passed / 3 existing skips，123.45秒；四项L4治理113 passed，8.91秒。原策略Python邻近244 passed / 1 existing skip，13.18秒；无供应商或模型实采。筛选表单的change重绘问题经实际浏览器复现并修补，相关59项回归通过。
- 完整changed-set约束34路径通过；文档治理和Python文件索引通过。浏览器覆盖4项目、搜索/空结果/状态筛选、三栏、v5未知记录刷新、Excel日程禁用；390/768/1440宽度DOM无横向溢出，明暗主题和截图已保存，控制台新error为空。仅UI隔离快照，不认证原后端数据生产。
- 最终同候选CI仍待远端实际运行，不复用基线1317968e三CI绿。Windows条件门由对应真机交接，当前Mac不派发Windows产品CI。

## 未验证边界

常驻部署、新历史生产、真实Wind/Office/模型与Word/认证下载均NOT_RUN；旧Run和全部数据保留，定时关闭。维护/DSH升级由原唯一维护任务独占；本变更不解除旧active=null阻断。

最终评审发现生成图册仍指向不含新增文件的旧源码提交；现将源码说明固定为已存在且包含三个新文件的2e1a6bfe，生成物交付提交另记，避免未来自指。三个Git blob逐项验证存在；生成器不变。

## CI repair 1：真实入口字节预算

Mac40464598312的干净安装完成，但启动因app.mjs 266724字节超过原256KiB硬门而安全回滚；基线262004字节，失败日志和原候选保留。未提高正文上限，而将已有报告操作HTTP协调提取为独立report-operations.mjs，保留页面代次/项目、忙态、未知核对和异常日志。新入口260079字节；使用原WebServiceManager._text_request实际读取隔离服务200、marker存在、原上限262144下通过。新增跨文件字节预算和取消/核对语义回归，原延迟/双击用例改为直接测试同一操作模块。新候选仍须独评、完整闭包及原三CI；旧Mac与旧Checks结果不沿用。
