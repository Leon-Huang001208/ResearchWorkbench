# RWB 开发镜像命名调整

受管开发构建使用 `rwb-development:development`，解析出完整 ID 后再写入 `dev.image`。既有实例按其独立账本的完整 ID 启动，候选与管理镜像仍按各自的 G0/G1 用途管理。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"改动仅限受管开发构建的本机用途标签与登记的失败保护；实例仍按原完整镜像 ID、工作树和卷登记运行，Native 部署和 rollback 边界、候选与控制镜像及入口均沿原合同。","diagrams":[]} -->

本地回归使用 Docker 命令替身，核对构建标签、完整 ID 和查询失败时的旧登记保全。实际开发镜像构建、现有容器切换及回滚均待相应验收。
