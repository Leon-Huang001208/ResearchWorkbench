# 原生报告修订修复

宿主macOS Mac mini，功能修复；本平台原生沙箱和macOS安装CI验收，Windows/Linux产品NOT_RUN。

授权四普通账号真实模型并发首批未通过：报告修订触发research_report_archive_io_failed，模型恢复生成的同名备用文件又触发report_identity_ambiguous；不是内存不足或模型算术错误。全部临时密钥已清除、账号停用，失败会话与原始业务数据保留，额外槽恢复3。硬门未改成通过。

原始内核沙箱中连续两次write_research_report复现第二次失败；getcwd拒绝、规范报告旁同名备份、仅非规范副本四例先红，重复规范身份仍拒绝。tempfile.mkdtemp在Python3.12会对相对目录求绝对路径；改用原目录内UUID排他mkdir，原归档哈希/权限/原子rename/清理保持。质量投影只读规范Store映射，不接受备份冒充当前报告。无沙箱扩权，无质量门或补查预算变化。

相关报告、质量、计算及新回归闭包80 passed，包含真实内核沙箱二次写入。完整API、最终候选评审/CI/部署和四用户复测仍以实际回执为准。无新依赖/持久schema，核对Web锁文件和setup入口无需改变；Mac干净安装仍必需。

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"仍由同一会话输出能力归档与Host规范文件映射核验，无新增执行引擎、部署节点、持久schema或沙箱权限。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"新定点测试复用既有Python步骤与标准runner，Mac内核验证只归Mac本机，跨平台产品验收不借用。","diagrams":[]} -->
