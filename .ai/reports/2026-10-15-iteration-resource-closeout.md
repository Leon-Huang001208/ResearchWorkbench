# 每轮迭代资源收尾

宿主macOS，工程功能开发；本地Mac Docker Desktop和适用CI验收，他平台真实验收保持交接。
基于master d744029a54c4f4a30f5c21d3def564c486c1bc50，独立task iteration-resource-closeout-20261015。

## 目标与边界

按用户已批准计划，将验收、合并、证据归档、受管资源回收、Git安全清理与空间复查串联。
两个明确受管构建器缓存合计20GiB；当前/上一通过镜像、运行服务、业务数据、凭据、
报告和恢复归档保留。复用docker_resources的精确退休/引用/归档恢复检查，不新增删除引擎。
不改产品API、不新增依赖、后台定时器或模型请求，不删除构建器卷或手工改快照。

## 实现

iteration_resources记录任务worktree目录身份、严格再生依赖白名单和证据目录；原件及
归档hash复核后才移除原日志，复制中断可校验重放。临时Docker资源记录delivery-task，
仅本任务退休对象进入原清理器。iteration_cache共用rwb-docker操作锁，校验Buildx单节点/
endpoint和已有实例归属，内存门内对已停止构建器临时使用2GiB，恢复原容器限额和状态。
BuildKit负责引用/租约和LRU，总预算超限或无法恢复即blocked，不伪报完成。

Git安全入口修补publish时验证feature tip干净、同任务、已包含在实际候选，才更新身份记录；
不重置CI次数或伪造验收。status确认真实合并和CI后自动收尾；原可恢复备份、未归并/脏目录/
ignored数据/占用检查均保留。证据与回执位于common Git私有目录，避免任务目录清掉后丢证据。

## 当前验证状态

先建立Python与JS反例，初次因实现缺失真实失败；Python新增13项、原Docker资源12项、
协议81项通过。完整所选Node集合275项通过；随后新增的分支错属、伪cleaned、其他任务
正常收尾后查询旧任务三反例单独复验通过，最终源还需完整Git单元和精确候选CI绑定。
测试工具仅沿既有授权隔离安装pytest/pytest-asyncio，目录进入任务依赖清理；产品无新依赖。
本机没有ruff/black/isort可执行入口，未安装新的格式工具，不虚报这些检查已执行。

独立Python/JS审查先后发现Buildx名称重绑定、资源删除前身份校验、部分证据复制恢复、
最终回执失败重放及旧任务历史快照误阻断等问题，均有修复及反例；最后复核无P1/P2。
当前Mac真实GC已终态PASS：合计101481676974→21407539619 bytes，低于20GiB；两个原服务
的CID/image/mount/StartedAt、59原镜像和全部卷不变，原构建器5GiB资源限制及停止状态恢复。
证据为本机visualizations/2026/10/15/iteration-closeout-live/receipt.json；真实Docker资源
归档/恢复/失败清理等4项也通过。实机未发模型请求或扩大VM/资源池。

当前候选CI、合并和本任务实际自动收尾仍待本轮完成，不能由局部PASS提前认证。资源和
Git最终化分别持久化；pending审计恢复，complete之后只校验本任务持久化成功证据，不要求
其他任务历史分支/worktree永久存在；重复status/cleanup不重新删除或因瞬态查询错误污染完成回执。

最终Git safety与新身份测试47项完整通过（34.45秒）；原275项集合中其余模块没有新源码变化。
初次prepare的控制器merge非零被标为integration_conflict，但工作区没有未解决路径；原生Git
完成同一feature的三方merge后，按既有冲突恢复prepare正式记录59fc7cf5，未删除锁、重置计数
或跳过验证。随后仅此报告补充是一次受控晚到feature提交，用于实测publish自动同步已包含
候选的feature身份；代码和真实GC源保持相同。失败记录保留在任务交付日志。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在既有管理员资源控制和Git交付边界补任务归属、缓存预算与收尾回执，不新增产品服务、数据库或Web接口；既有部署拓扑保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"在现有Project Constraints job加入无Docker的stdlib回归和同一步骤JS身份验证，不新增workflow或runner；真实Mac卷验收保持本机证据。","diagrams":[]} -->
