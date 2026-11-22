# 网关冻结恢复任务环境修复

宿主macOS；Web部署最小修复，本机及同候选Mac CI验收。原常驻网关已通过冻结包回滚恢复健康、保全通过，主实例及DSH原PID不变；本轮不操作账号、退出或模型。

根因：launchd缺少现有Homebrew Git LFS路径，Git checkout钩子失败，冻结恢复停在rolling_back。隔离真实Git钩子先复现受限PATH失败；恢复任务显式提供固定系统/Homebrew PATH并在任何信号前验证工具，冻结包真实回滚转为通过。没有安装包、禁用钩子、改全局PATH或调整自动更新白名单。优雅等待延为90秒，超时仍保留journal、不强杀。

目标124项网关合同通过，包含六阶段冻结回滚；受限路径负例及修复环境正例的定点检查另留日志。格式、lint、类型、治理、最终独立评审和CI按受管流程记录；实际部署验收不由本机测试推断。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"既有网关恢复LaunchAgent只补齐自身Git钩子工具环境并延长优雅等待；原锁、出生栅栏、身份、保全、回滚和部署节点均保留，不新增研究循环或业务接口。","diagrams":[]} -->
