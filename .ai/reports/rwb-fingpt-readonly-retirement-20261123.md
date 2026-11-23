# 旧 FinGPT 封存资源清理修复

Mac mini / macOS 功能修复。接续原替换任务，PR329 后部署在封存 capability 只读目录 unlink 失败。原数据保全检查通过，正式 recover 回滚 7dc，未完成删除。

仅修专有目录复用 Store._remove_owned_tree；混合目录保留实际引用文件，解除目录写限制后逐项删除。新增真实只读目录与共享文件同会话回归。不新增模型、备份、依赖或删除范围。

7项退役回归通过，Ruff通过；原数据未变且正式recover已rolled_back7dc/preserved=true。最终辅助函数提取后再跑同7项；Windows/Linux 原生 NOT_RUN。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"仅复用Store既有只读目录删除方法，实际共享文件和数据集仍原路径保留，不改变身份权限、服务拓扑、安装依赖或存储结构。","diagrams":[]} -->
Product-Progress: not-required — 本次仅修正已交付入口的封存资源删除故障，不增加用户能力或导航。
