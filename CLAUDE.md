
# AlphaFoundry - Claude配置
#
# 此文件定义了Claude对项目的理解
# 用于自动化任务和AI辅助开发

## 项目概览
name: AlphaFoundry
type: 本地优先、企业级买方投研情报系统
languages: Python (主), HTML/CSS/JS (Web UI)

## 项目结构
- core/ - 核心业务逻辑和契约
- data_layer/ - 数据访问和持久化
- knowledge_layer/ - 知识提取和管理
- reasoning/ - 情景分析和推理
- timing_engine/ - 市场择时模型
- memory_learning/ - 从结果学习
- signal_lab/ - 特征工程和回测
- reporting/ - 报告生成
- app/ - API和Web UI
- scripts/ - 工具脚本
- tests/ - 测试
- .ai/ - AI助手工作目录

## 任务管理
- 任务文件: .ai/tasks/task.json
- 进度文件: .ai/progress/progress.md
- 报告目录: .ai/reports/

## 状态定义
- todo: 未开始任务
- doing: 正在进行中
- blocked: 任务受阻，依赖未完成
- done: 任务成功完成
- failed: 任务失败

## 当前任务集
- af-auto-000: 初始仓库审计和验证

## 脚本
- .ai/scripts/check-project.sh - 检查项目结构和测试
- .ai/scripts/check-db.sh - 检查数据库健康
- .ai/scripts/check-api.sh - 检查API健康
- .ai/scripts/run-automation.sh - 编排任务执行

## 关键命令
- 运行测试: python -m pytest tests/ -v
- 启动API: python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
- 初始化数据库: python scripts/bootstrap_db.py

## 分支工作流规则

1. 不要在 master/main 上直接执行 AF-AUTO-001 或后续任务。
2. 在执行实现任务前，先创建或切换到任务分支。
3. 分支命名约定：
   - `af-auto-001-<简短描述>` 用于单个任务分支
   - 示例：
     - `af-auto-001-fix-failing-tests`
     - `af-auto-001-reasoning-todos`
     - `af-auto-001-quick-win-tests`
4. 每个任务应该产生一个原子提交或一小系列相关提交。
5. 任务完成后，推送分支并打开 Pull Request。
6. master/main 仅通过 PR 合并接收更改。
7. 除非用户明确指示，否则不要自动合并 PR。
8. 仅审计任务（AF-AUTO-000）可以直接提交到 master。

## 硬性规则 - 绝不能违反

### 安全规则
1. **审计任务期间不得修改业务逻辑** (af-auto-000)
2. **审计任务仅提交.ai目录和CLAUDE.md的更改**
3. **失败时大声报错** - 脚本遇到真正的失败必须非零退出
4. **不得伪造成功状态** - 除非经过验证，否则不要报告"✓"
5. **每个完成任务必须更新task.json和progress.md**
6. **仅使用仓库相对路径** - 不得使用绝对路径

### 脚本规则
7. **脚本必须验证从项目根目录运行**
8. **脚本执行前必须验证所需文件存在**
9. **脚本必须记录所有假设和限制**
10. **脚本退出码规则**: 0 = 成功, 1 = 错误, 2 = 依赖失败

### 仓库健康规则
11. **测试允许失败** - 基线已记录在案
12. **数据库连接检查≠完整导入**
13. **API检查≠完整服务器重启** (如果已运行则使用现有)
14. **自动化中不得执行破坏性操作**

## 控制层限制和假设
- 假设PostgreSQL运行在localhost:5432
- 假设API可能已在8000端口运行
- 假设git仓库是干净的
- 不会执行不可逆操作
- 不会优雅处理网络故障
- 还不会管理任务依赖
- 还不会恢复中断的任务
- 还不会处理并发执行
