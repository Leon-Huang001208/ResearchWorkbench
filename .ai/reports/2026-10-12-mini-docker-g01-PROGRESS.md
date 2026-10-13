# G0/G1 Mac mini Docker PROGRESS

<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"新增管理员Docker控制平面、受限开发与构建器、显式环境实例及独立数据卷；Web和DSH单运行单元及唯一研究引擎保持","diagrams":["01-deployment"]} -->

后续进展：完整4GiB heap源码编译在借用stage预算的5GiB冷构建器通过，结束精确停止。
开发环境补齐procps/lsof及PATH受限的容器Python兼容入口，去除全局Git工作树污染。
949项既有相关Python回归通过，管理器后续15项通过；127项相关Node合同通过。
实际候选healthy，运行API connected/health_check_passed均true；root/static请求成功。
候选stop/up数据保留，开发rebuild及cleanup/register/up源码与数据保留，候选哨兵哈希不变。
开发临时新增源模块未进入候选固定镜像，测试后仅删除该新建哨兵源文件。
后续部署图/说明门禁与回执收口中；所有早期失败保留在私有logs，不能把这一进展写成CI已通过。

- architecture-review: 单一 Research Web + DSH；仅新增管理员控制平面和开发工具容器，无旧API/数据库/研究引擎恢复。
- 宿主：macOS 27.0.1/26A434，Mac18,5，arm64，24GiB，12逻辑CPU。
- Docker Desktop 4.94.0/Engine29.8.2，Compose5.5.1，Linux arm64；VM实际8319238144字节（约7.75GiB），尚不符合建议16GiB。
- 内置APFS约460GiB，可用约138GiB；未迁移、清理或扩容。
- 主checkout HEAD `4a5e7523d7407525d108757727c64f10783203f4`，含既有未跟踪报告；保留原样。
- 最新GitHub master `f32d6993af99652c76e9a77dbc6f44877e39cd1c`；从该基线创建独立 `codex/mini-docker-g01` worktree。
- 原Docker research-web Compose实例均停止，数据绑定多个已有独立/tmp验收根；canonical `~/.research-workbench/research-web`仍存在且私有。未复制其数据、状态或秘密。
- 原Docker公开shell安装仍需宿主Python，资源无完整硬限额、无dev/stage/prod显式目标；新增shell管理员入口，legacy Python/cmd保留。
- 新实例按环境/名字/管理根指纹隔离四卷、网络、端口与账本；stage/dev默认禁用Automation；业务/dev无socket。
- 构建器已实际创建：3GiB memory/swap、CFS200000/100000、PIDs256、日志10MiB×3、并行度2，独立cache卷。
- 初始Docker Hub认证超时，daemon pull成功；Docker Desktop代理与buildx宿主认证分层。重试仅使用系统已有无凭据回环代理，未改变系统代理/软件源/TLS。
- 第一次完整DSH构建在3GiB硬限额持续触发内存回收（无OOM kill）；原脚本Node heap请求4GiB。已停止精确所属builder，加入build-only2GiB heap适配，完整编译/打包重试中。
- 管理器10项拒绝/准入测试在限额Linux容器通过；首次测试因legacy根conftest引入sqlalchemy失败，使用仓库Web专用confcutdir后通过，没有恢复历史数据库栈。
- 旧本地Node基础镜像直接运行返回`accessing a corrupted shared library`；只记录环境异常，未清理/替换它或假称Node验证成功。新开发镜像内测试仍待执行。
- 真实候选健康、开发重建与源码/数据隔离验证仍在进行；供应商/多人认证/Linux严格沙箱/公网/生产迁移均NOT_RUN或后续G2-G6。
- 尚未push/PR/merge、dispatch或执行GitHub macOS新候选CI；旧证据不计本轮PASS。
