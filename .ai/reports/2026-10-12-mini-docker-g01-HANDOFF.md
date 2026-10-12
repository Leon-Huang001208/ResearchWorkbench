# G0/G1 Docker 基座交付与验收

本地基座已实现并实际运行；用户已授权推送并创建PR，正在执行本轮 GitHub macOS 干净安装 CI。未合并、
发布registry镜像或迁移生产。`hostAcceptance=NOT_RUN(CI pending)`，`aggregateAcceptance=NOT_READY`。
本地源码是从 GitHub master `f32d6993af99652c76e9a77dbc6f44877e39cd1c` 创建的
`codex/mini-docker-g01` worktree，已有本地提交 `27d5fbac752d31caca5968f4dafd047548afef61`。镜像revision标签是该基线，
不把含未提交改动的构建说成已发布exact-SHA镜像；G2再完成发布manifest/digest提升。

## 实现与归属

- Mac mini：Apple M6、24GiB、12CPU、macOS27.0.1/26A434、arm64；Docker Desktop4.94.0、
  Engine29.8.2、Compose5.5.1，实际Linux arm64。内置盘500.3GB，G0空闲约138GiB。
- VM实际8319238144字节，约7.75GiB；建议16GiB尚未修改。MacBook角色改为远程入口，
  SSH/跨设备可达性未实测，步骤见操作手册，常驻/电源恢复留G5。
- `rwb-docker` / `rwb docker` 是 shell＋Docker CLI 入口。Python/Node/Git/构建器/测试依赖
  在容器内；管理代码只读加载于瞬时控制器，仅该管理员控制面获得socket。
  Native无参数入口、Windows cmd、底层Python legacy入口保持，不能混用新旧账本/数据。
- 新实例显式环境/名字，四卷data/logs/credentials/cache、网络、回环端口、身份账本各自独立。
  dev绑定本worktree/Git common dir，stage/prod无源码bind，只用固定image ID；DSH仍是唯一引擎。
- 上限：dev合计3GiB，stage2GiB，生产池6GiB（含控制器256MiB预留，默认最多两个2GiB实例），
  每业务/dev容器CPU2/PIDs256、只读root/drop ALL/no-new-privileges、日志10MiB×3，
  tmp256MiB/home128MiB/state1MiB，swap与memory相同。
- 初始BuildKit3GiB实际持续触发回收；完整编译尝试2/2.25GiB heap均OOM。
  最终保留固定DSH原4GiB heap/全部TypeScript/打包检查，冷构建借stage2GiB到builder5GiB，
  CPU2/PIDs256/并行2/日志10MiB×3；stage互斥且构建退出精确停止。生产6+dev3+builder5+
  stage0+VM余量2仍为16GiB。准入另核对实际VM及全部运行容器硬上限，未知无限额容器拒绝。
- 本机旧日常数据和全部历史foreign容器保留；没读取/复制Native Keychain、密钥或旧认证状态。
  不引入历史API/PostgreSQL/pgvector/桌面栈。root私有与alias检查、环境池预留、容器配置/镜像/
  网络/卷/ID核验都保留，不能手改账本放行。

## 实际镜像与命令

最终候选（本地Linux arm64内容ID，无registry digest声明）：
`sha256:dd9bc19cbeadaac5100d294fd21d06e04a2dc6bdb47da0ef19072046807bf852`。
固定DSH `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`，Web锁/CJPY锁未改变。
开发验收使用登记工具镜像 `sha256:e912d55fb893b17d89c12e19a1483901e3383241472257d3c78f6f90f6a2bde9`。
新构建产生的新dev镜像不隐式改动已有登记；显式 `dev task rebuild --image sha256:…` 才更新。

```sh
./rwb-docker bootstrap
./rwb-docker builder-cold-budget  # 本轮已登记初始3GiB builder的受管升级；新装默认冷构建5GiB
./rwb-docker build
./rwb-docker dev task register
./rwb-docker dev task up
./rwb-docker dev task exec -- python -m pytest tests/research_web/test_docker_manager.py --confcutdir=tests/research_web -q
./rwb-docker stage candidate register --port 18088
./rwb-docker stage candidate up
./rwb-docker stage candidate doctor
./rwb-docker dev task rebuild
./rwb-docker dev task stop
./rwb-docker dev task cleanup
./rwb-docker dev task register
./rwb-docker dev task up
./rwb-docker stage candidate stop
./rwb-docker stage candidate replace-image --image sha256:…
./rwb-docker stage candidate up
./rwb-docker stage candidate stop
```

上述命令均实际执行。安装入口的shell分派另有测试，真实bootstrap/build管理路径使用了
本机现有无凭据回环代理，后续入口自动检测已配置相同HTTP/HTTPS本地代理，不修改系统设置。
真实 `rwb docker stage candidate doctor` 还在仅含shell/Docker/标准管理工具、无Python/Node/Git
的PATH中通过；公开Docker管理没有探测宿主解释器。宿主已有Harness和架构图管理工具不作为
产品安装依赖；架构图截图使用宿主已有Chrome，应用构建与回归在Docker。

## 验证结果

| 验证 | 实测 |
| --- | --- |
| 固定DSH、锁定Web/CJPY、最终runtime导入和arm64镜像构建 | PASS，最终builder5GiB实际inspect，结束停止 |
| 既有相关Python回归：supervisor/launch/setup/protocol/packaging/contract/CLI/runtime mode/controller | 949 PASS，74.23s；早期缺工具/污染环境失败保留 |
| 最终管理器拒绝/准入/cleanup/候选更新单元测试 | 17 PASS；不当作平台生命周期证据 |
| Docker/架构/文档/Actions/仓库Node合同 | 127 PASS |
| changed Python Ruff/Black/isort/mypy | PASS；工具版本在dev-requirements中固定 |
| Project Constraints、research architecture、doc sync、Python index、documentation governance、diff check | PASS |
| 实际候选healthcheck、Docker healthy、root/static/API | PASS；connected及health_check_passed均true，仅发布127.0.0.1:18088，DSH未暴露 |
| stop/up、显式换候选固定镜像后数据保留 | PASS；stage哨兵SHA相同 |
| dev重建、cleanup退休/重新登记启动，源码/data保留 | PASS；stage数据和镜像未被开发清理改变 |
| dev新增源模块不出现在固定候选文件系统 | PASS；源哨兵重建后保留、候选不存在，测试后只移除该新建源哨兵 |
| 最终部署图字节在候选镜像中一致 | PASS，HTML SHA `fb102b50ce6ae49d1c3248f967a44576c7f4637c8824dbdf591b71b034b3523f` |
| 架构图showcase与窗口/图像检查 | deliver9/9、0错误/警告，四尺寸无溢出，Agent查看两主题最终图；用户未确认 |
| 本轮新候选GitHub macOS CI、Windows/Linux/amd64、真实供应商、生产迁移 | NOT_RUN |

Stage哨兵SHA：`f199585b5d0a36de9149f8d3fefde3042cc3ba3459144000a163ce64d263a122`；
dev哨兵SHA：`6e6ec063533e60f1d203fce8db8bd19eabc52a645437545e1b1684dcb23db9b0`。
这只是实例文件隔离与保留，不证明多人鉴权、模型研究、供应商或备份恢复。
运行中轻量占用观察stage约484MiB、dev约159MiB；没有30分钟混合负载、峰值容量或RPO/RTO声明。

## 证据与后续

完整原始stdout/stderr、失败重试、实际JSON/检查和SHA256SUMS仅保存在本机私有
`~/.local/share/rwb-docker/logs/g01/`，不上传原始日志。`rwb-g01-required-python-final.log`、
`rwb-g01-manager-last.log`、`rwb-g01-node-closed.log`、`rwb-g01-final-build.log`、
`rwb-g01-no-host-interpreters.json`、`rwb-g01-stage-final-image-up.json`、
`rwb-g01-stage-new-image-sentinel.txt`为定点证据；时序失败另保留PROGRESS记录。
早期旧本地Node基础镜像直接运行报shared-library corruption，未全局清理/修复；新镜像内
真实Node/DSH构建与回归通过，不能扩大成所有Docker内容存储都已健康。

G2：加密/隔离Docker模型凭据和同digest发布/回退；通用业务文件后端不等于模型后端。
G3：完整任务期全机配额、Linux严格沙箱与攻击回归；当前非Mac脚本门保持拒绝。
G4：邀请制身份、可信入口与跨账号负向测试；固定workspace=research仍非租户身份。
G5：私网/HTTPS、公网入口、关机恢复、迁移、一致备份/恢复；目前均未实施/未验。
G6：30分钟混合负载、构建干扰与容量/RPO/RTO实测。

本轮完成只剩新候选Mac CI证据；用户已明确批准推送并创建PR，合并仍需单独授权。
其他平台保持交接NOT_RUN，不作为本Mac任务前置门。仓库visibility已实时核对为public、默认master，
Actions预算规则已读取；未据此自动获得push/merge授权。
