# Claw 融合实施计划

已批准设计：2026-10-13-claw-alphaengine-fusion-PROGRESS.md。宿主 macOS，功能开发；独立分支 codex/claw-fusion-20261013。不安装或重启生产实例，不自动发布。

## 执行顺序

- [x] 项目元数据：新增 claw_projects.py / claw_routes.py；默认项目兼容旧会话，创建/改名/归档与移组只修改索引；项目文件聚合保留来源；受控打开文件后复制为当前会话附件。先写 tests/research_web/test_claw_projects.py，再运行 RED/GREEN。
- [x] 日程草稿：复用 AutomationCreate 校验与现有目标版本解析；新增 prepare/list/confirm/dismiss 端点；确认创建使用稳定创建键防止重复和崩溃重放。增加 native prepare 工具、实例私有通信与 guard 白名单；工具不能保存、启用或投递日程。
- [x] UI：core.mjs 解析 Claw 四入口及新增 API；claw-workspace.mjs 提供项目/文件/日程草稿画布，app.mjs 串联现有目录与事件；已有日程管理继续共用能力中心。项目引用须用户点击，复制成功才加入附件草稿。
- [ ] 文档与完整性：更新模块合同、架构机器清单与 API Atlas；核对安装相关合同；执行 changed-file 验证 Router、目标 Python/JS 测试与质量检查。
- [ ] 一次分支评审；修正重大问题并运行回归；报告实际结果。生产模型验收及 macOS CI 未执行时保留 NOT_RUN。

## 验收重点

旧会话默认归属、归档保留文件、跨项目拒绝、软删除过滤、符号链接/硬链接与路径逃逸拒绝、文件上限、来源哈希绑定；日程仅草稿、时区/目标必需、取消不保存、重复确认不重复创建、版本变化拒绝；四入口、键盘和错误保留草稿。

## 进度

基线 Python 测试未运行：现有解释器缺 pytest，已请求任务测试环境安装授权；不修改现有依赖锁。

核心实现与源码检查已完成；完整本平台验收因已复现的基线门禁和浏览器访问受阻，见同日 PROGRESS 报告。
