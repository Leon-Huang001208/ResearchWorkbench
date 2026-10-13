# G2A Docker 模型凭据验收与交接

## 2026-10-13 真实供应商闭环补验

用户确认已在候选设置页保存 Key 后，本轮两次现有“模型最小生成测试”均实际通过。
DeepSeek 官方 / deepseek-flash、固定 DSH 返回的两份会话详情均为 completed，
且存在非空 assistant 文本；报告只记断言，不记 Key、主密钥或秘密哈希。

| 本次补验 | 结果 |
| --- | --- |
| 设置页保存后的首次真实生成 | PASS，session e3f213a2-333c-4ab5-b0b1-f15f68b269f2，completed/非空文本 |
| stop → 同一 image ID replace-image → up 实际重建 | PASS，容器 49b97e13f138… → eb8494a5565f…，同一五卷/网络/身份 |
| 无重新录入 Key，重建后再次真实生成 | PASS，session 90a328bb-d45a-4ddd-953a-7ca762adf218，completed/非空文本 |
| 显式清除模型 Key 后新请求 | PASS，model_credentials_missing，消息“模型凭据已清除，请重新配置” |
| 清除后主密钥保留 | PASS，只验证文件存在；未读取内容或哈希 |
| 收尾 | candidate 已停止；builder 已停止（5GiB）；dev g2a 可继续使用 |

以上更新取代下文历史的供应商 NOT_RUN 快照。镜像仍为同一 c3885222e 来源的固定内容 ID，
没有把后续报告提交冒称为镜像 revision。原始证据仅在私有 logs/g2a/real-*.json。
Key 已按验收要求清除，主密钥、身份、其他凭据资源与研究数据保留；后续使用需在设置页重新录入。
本轮仍保留九项已在未修改主线复现的 Linux 容器 Native/API 失败，未将其改写为 PASS；
PR 不因模型闭环成功自动宣称 mergeReady 或跨平台发布就绪。

本轮使用 Mac mini / Docker Desktop 的 Linux arm64 实例，沿用固定 DSH
`48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`。不迁移 Native Keychain 或其他应用凭据。
尚未收到用户在本实例保存真实 Key 的通知；真实供应商生成及重建后真实生成为 NOT_RUN。
保存、configured、健康和合成断言均不充当真实推理证据。

## 实现与来源

- 私有桥保持两个固定 ref、四操作白名单、Python `-I -B`、清洁环境和私有 stdio。
  受管安装路径解决模块导入，不继承 PYTHONPATH；凭据模块不加载会创建目录的全局 Settings。
- Docker 后端复用已锁定的 cryptography 50.0.1，AES-256-GCM、随机 12-byte nonce、
  版本化 envelope，AAD 绑定实例身份、service 和 ref。原权限、锁、原子替换和错误处理保留。
- 每实例独立随机主密钥和稳定实例身份；密文位于 credentials/models，主密钥与身份位于
  model_key 卷，业务只读挂载。Host 认证 record 与模型秘密分开，Native 原 Keychain 选择保留。
- 保留留空、明确清除、活动任务拒绝和写入未知阻断；后端失败不回退其他存储。
- 本地运行镜像内容 ID：
  `sha256:1c94c017574f163689bdb12122cd917008688c638e382b43b611238e9575a33b`。
  开发镜像：`sha256:612067237c886e3f83ddf9a933d24dd989d0e9535ca890add3ee08a40c39f68a`。
  二者来源是干净提交 `c3885222e5d818e4a509077e10fea90d1a455c5c`，平台 linux/arm64。
  没有推送 registry，registry manifest digest 为 NOT_PUBLISHED，不能将本地 image ID 称为它。
- 后续集成主线 PR94 的 legacy 资源生命周期改动，集成提交 `8150e1b23539adcbdbf55a26383ae2ba040c69d1`。
  六个模型链路源码文件逐字节与镜像来源提交一致；未将镜像 revision 标签冒称为集成提交。
  PR 最终提交与 CI 另据当前 GitHub 记录核对。

## 已执行证据

| 项目 | 状态与范围 |
| --- | --- |
| 加密、缺失/错误主密钥、篡改、权限、alias、写入中断、清除失败及原 Native 合同回归 | 最后 76 PASS、2 Native 实机 SKIP；不冒充 Keychain 真机 |
| 相关启动器/桥/管理器回归 | 228 PASS、2 SKIP（较早闭包）；最终日志导入修复另跑上述 76 项 |
| Node Docker/架构/文档/Actions/仓库/模型桥闭包 | 132 PASS；新增 DSH 刷新参数合同 18 PASS；最终设置页/文档检查 PASS |
| Ruff、Black、isort、mypy、Python 索引及项目约束 | 已执行；最终 changed set 与索引在交付前再核对 |
| 实际镜像构建、固定 DSH 完整编译、606 包 staging、最终导入 smoke | PASS，保持 5GiB builder / CPU2 / 并行2；builder 退出停止 |
| 首次模型桥在只读镜像失败 | FAIL 保留：全局 Settings 尝试创建 /opt/rwb/logs；回归先失败、修复后通过 |
| 固定镜像串行 helper 隔离 | PASS：A 保存/B 缺失、B 保存/A 不变、B 清除/A 不变，错身份和错主密钥均拒绝 |
| helper 资源与路径 | 128MiB / CPU .5 / PIDs32；A/B 独立资源、相同内部路径，借已停止候选登记额度，非两个完整 stage |
| 实际候选与设置页 | PASS：DSH connected、healthy；Chrome AX 显示本实例加密存储、凭据未配置，不回填秘密 |
| 缺少凭据时产品最小生成请求 | PASS：实际 POST 返回 model_credentials_missing；未调用真实模型 |
| 设置页真实 Key 保存与真实文本生成 | NOT_RUN：等待用户在本实例设置页自行输入 Key |
| 重建后真实生成、真实 Key 清除后的请求 | NOT_RUN：同一真实供应商前置条件未满足 |
| 本轮 GitHub CI | 交付时据 exact head 更新；不沿用 PR93 或主线旧 CI |

最终集成后的 Node 合同批次为 145 PASS，耗时 2.512842376 秒。回执中同一合并执行批次的
验证 ID 共享该批次实测耗时，不将它解释为某个单独文件的耗时。Python 的 203.60/212.85/1.56
同样对应相应日志中完整批次；文档/索引/项目约束由 perf_counter 单独实测。

一次扩大检查耗尽 dev 的 256MiB /tmp，夹具改放本实例 cache 卷后消除空间问题。
剩余 9 项 Native 恢复/文档生成失败在未修改主线的同一 Linux 容器复现，保留 FAIL；
不修改无关守卫或把它们写成 PASS。详见 PROGRESS 及私有基线对照日志。

## 命令与继续入口

```sh
./rwb-docker dev task stop
./rwb-docker dev task cleanup  # 退休 G1 名额，保留旧源码和卷
./rwb-docker dev g2a register
./rwb-docker dev g2a up
./rwb-docker dev g2a stop
./rwb-docker build --refresh-dsh  # 已实测；只在缺失资产且需刷新时使用
./rwb-docker stage candidate replace-image --image sha256:1c94c017574f163689bdb12122cd917008688c638e382b43b611238e9575a33b
./rwb-docker stage candidate enable-model-credentials  # 已初始化，重复不会重建主密钥
./rwb-docker stage candidate credential-probe  # 要求候选/builder 停止
./rwb-docker stage candidate up
./rwb-docker dev g2a rebuild --image sha256:612067237c886e3f83ddf9a933d24dd989d0e9535ca890add3ee08a40c39f68a
```

上述对应操作实际执行；最终正常 `build` 已生成日志修复镜像。
真实 Key 只由用户在 `http://127.0.0.1:18088/#/settings/model` 输入并保存，回复“已保存”后
继续按钮生成 → 受管 stop/replace-image/up（记录 ID 改变）→ 再次生成 → 清除/缺失请求。
当前没有供应商成功记录；Linux 严格沙箱未放宽，不据文本调用推断研究、多用户或生产能力。

最小恢复材料：该实例的 credentials 密文卷、model_key 主密钥/身份卷及管理账本关联。
缺失、错配或损坏明确拒绝，不自动生成新密钥覆盖；清除模型 Key 保留主密钥。
完整备份、生产迁移、多人登录、公网入口和 Linux 研究沙箱属于后续阶段。

## 状态与证据位置

dev g2a 绑定本 worktree、3GiB、新开发镜像，可继续使用；候选已准入 2GiB，端口 18088。
收尾按目标停止 candidate 和 builder，保留源码、数据、凭据和夹具卷，最终状态以私有 CLOSED 记录为准。
用户另行明确授权限定外部 rwb-hot-probe：现为 memory=swap=480MiB、CPU1、PIDs128，仍运行，
未停止/删除它；该小额上限使 dev/stage/控制器与 2GiB 余量符合实际 VM 8319238144 bytes。
没有扩大 dev/stage/prod 池或将 VM 改为 16GiB。

原始构建/状态/布尔 helper 证据：`~/.local/share/rwb-docker/logs/g2a/`；
早期合成/基线回归：`~/.local/share/rwb-docker/logs/g01/g2a-*.log`。原始日志、Key、主密钥与秘密哈希不进 Git/CI。
Windows/Linux 原生与同平台产品 dispatch 均 NOT_RUN，由对应真机交接；本 PR 不合并、不操作生产。
