# Hot旧候选的受管升级兼容修复

macOS功能开发，独立hot-intel-continuation worktree，父候选c8b0b0ae。完整Goal仍未完成；预算不变。

真实复现：stage/candidate旧24060ee镜像容器退出，账本已有ready model_instance/model_key五卷，projection与实际匹配，但原容器只有四挂载。最新status报model_master_mount_mismatch，显式replace同样被普通owned拒绝。dev/g2b正常运行且未停止。

修复仅允许明确stage不可变镜像replace退休严格认证的停止pre-AES旧容器，保留五卷/旧image；普通owned/status/up/stop门不变。两次核对后使用固定ID普通rm，无force，未启动容器可安全替换。日志stopped_pre_model_candidate_verified，无秘密读取/复制，无新增依赖。

实际测试：candidate-pre-model-red.log为1FAIL/25PASS；candidate-pre-model-green.log为26PASS。扩大闭包candidate-pre-model-python.log为259PASS，JS为129PASS，项目约束/文档/文件索引PASS。反例包括运行中、AES旧镜像、模型环境、projection不符、初始化未完成。独立Python只读审查Approve，无阻断。ruff/black/isort/mypy在已授权隔离环境均不可用，未安装也未声称通过。实际Docker替换/新镜像/当前MacCI仍NOT_RUN。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"现有管理平面只新增停止pre-AES stage显式替换的严格兼容判断，旧容器退休并由原up建立新容器，五卷/实例/凭据和唯一DSH节点保持，无新增服务、依赖或秘密迁移。","diagrams":[]} -->
