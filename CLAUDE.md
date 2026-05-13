
# AlphaFoundry - Claude配置

此文件定义了Claude对项目的理解，用于自动化任务和AI辅助开发。

## 项目概览

- **name**: AlphaFoundry
- **type**: 本地优先、企业级买方投研情报系统
- **languages**: Python (主), HTML/CSS/JS (Web UI)

### 项目结构

- `core/` - 核心业务逻辑和契约
- `data_layer/` - 数据访问和持久化
- `knowledge_layer/` - 知识提取和管理
- `reasoning/` - 情景分析和推理
- `timing_engine/` - 市场择时模型
- `memory_learning/` - 从结果学习
- `signal_lab/` - 特征工程和回测
- `reporting/` - 报告生成
- `app/` - API和Web UI
- `scripts/` - 工具脚本
- `tests/` - 测试
- `.ai/` - AI助手工作目录

### 任务管理

- **任务文件**: `.ai/tasks/task_<任务集ID>.json` (例如: `task_af_auto_003.json`)
- **进度文件**: `.ai/progress/progress_<任务集ID>.md` (每个任务集有自己的进度文件，例如: `progress_af_auto_003.md`)
- **通用进度**: `.ai/progress/progress.md` (包含所有任务集的摘要)
- **报告目录**: `.ai/reports/`

### 任务状态

- `todo` - 未开始任务
- `doing` - 正在进行中
- `blocked` - 任务受阻，依赖未完成
- `done` - 任务成功完成
- `failed` - 任务失败

### 当前任务集

- `af-auto-000` - 初始仓库审计和验证
- `af-auto-001` - 测试修复和覆盖提升
- `af-auto-002` - 数据摄入和报告模板
- `af-auto-003` - UI 设计规范落地和 Playwright 调试

---

## MANDATORY: Agent 工作流

### Step 1: 初始化环境

```bash
# 检查环境
python --version
pip list | head -20

# 检查服务状态
lsof -ti :8000 || echo "API server not running"
lsof -ti :5432 || echo "PostgreSQL not running"
```

### Step 2: 选择下一个任务

读取 `.ai/tasks/task.json` 并选择一个任务（优先级）：
1. 选择 `status: "todo"` 的任务
2. 考虑依赖关系 - 基础功能先做
3. 选择最高优先级的未完成任务

### Step 3: 实现任务

- 仔细阅读任务描述和成功标准
- 遵循现有代码模式和约定
- 每次只专注完成一个任务

### Step 4: 全面测试（强制要求）

**强制测试要求：**

1. **大幅度页面修改**（新建页面、重写组件、修改核心交互）：
   - **必须在浏览器中测试！** 使用 MCP Playwright 工具
   - 验证页面能正确加载和渲染
   - 验证表单提交、按钮点击等交互功能
   - 截图确认 UI 正确显示

2. **小幅度代码修改**（修复 bug、调整样式、添加辅助函数）：
   - 可以使用单元测试或 lint/build 验证
   - 如有疑虑，仍建议浏览器测试

3. **所有修改必须通过**：
   - `ruff check .` 无错误
   - `black .` 和 `isort .` 格式化
   - `mypy` 类型检查通过
   - 相关 pytest 测试通过

**AlphaFoundry 测试清单：**
- [ ] 代码没有类型错误
- [ ] lint 通过
- [ ] 测试通过
- [ ] 功能在浏览器中正常工作（对于 UI 相关修改）
- [ ] API 端点响应正常（对于后端修改）

### Step 5: 更新进度

**重要规则：每个任务集都有自己的进度文件！**

对于任务集 `af-auto-xxx`：
1. 首先创建/更新任务集专用进度文件：`.ai/progress/progress_af_auto_xxx.md`
2. 然后在通用进度文件 `.ai/progress/progress.md` 中添加该任务集的摘要引用

```markdown
## [日期] - Task: [任务描述]

### 完成的工作:
- [具体的变更]

### 测试:
- [如何测试的]

### 备注:
- [对未来 agent 有用的备注]
```

### Step 6: 提交更改

**IMPORTANT: 所有更改必须在同一个 commit 中提交，包括 task.json 的更新！**

流程：
1. 更新 `.ai/tasks/task_<任务集ID>.json`，将任务的 `status` 从 `"todo"` 改为 `"done"`
2. 创建/更新 `.ai/progress/progress_<任务集ID>.md` 记录该任务集的完整工作
3. 在 `.ai/progress/progress.md` 中添加该任务集的摘要
4. 一次性提交所有更改：

```bash
git add .
git commit -m "[任务描述] - completed"
```

**规则:**
- 只有在所有步骤都验证通过后才标记 `status: "done"`
- 永远不要删除或修改任务描述
- 永远不要从列表中移除任务

---

## ⚠️ 阻塞处理

**需要停止任务并请求人工帮助的情况：**

1. **缺少环境配置**（.env 密钥、数据库配置、外部服务账号）
2. **外部依赖不可用**（第三方 API 宕机、OAuth 流程、付费服务）
3. **测试无法进行**（需要真实账号、外部系统未部署、特定硬件）

### 阻塞时的正确操作

**DO NOT（禁止）：**
- ❌ 提交 git commit
- ❌ 将 task.json 的 status 设为 done
- ❌ 假装任务已完成

**DO（必须）：**
- ✅ 在 progress.md 中记录当前进度和阻塞原因
- ✅ 输出清晰的阻塞信息，说明需要人工做什么
- ✅ 停止任务，等待人工介入

### 阻塞信息格式

```
🚫 任务阻塞 - 需要人工介入

**当前任务**: [任务名称]

**已完成的工作**:
- [已完成的代码/配置]

**阻塞原因**:
- [具体说明为什么无法继续]

**需要人工帮助**:
1. [具体的步骤 1]
2. [具体的步骤 2]

**解除阻塞后**:
- 运行 [命令] 继续任务
```

---

## 关键命令

```bash
# 测试
python -m pytest tests/ -v

# 开发服务器
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000

# 代码质量
black . &amp;&amp; isort .
ruff check .
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
```

---

## 分支工作流规则

1. **不要在 master/main 上直接执行** AF-AUTO-001 或后续任务
2. 在执行实现任务前，先创建或切换到任务分支
3. **分支命名约定**: `af-auto-001-<简短描述>`
   - 示例: `af-auto-001-fix-failing-tests`
4. 每个任务应该产生一个原子提交或一小系列相关提交
5. 任务完成后，推送分支并打开 Pull Request
6. **master/main 仅通过 PR 合并**接收更改
7. 除非用户明确指示，否则不要自动合并 PR
8. 仅审计任务（AF-AUTO-000）可以直接提交到 master

---

## 硬性规则 - 绝不能违反

### 安全规则

1. **审计任务期间不得修改业务逻辑** (af-auto-000)
2. **审计任务仅提交 .ai 目录和 CLAUDE.md 的更改**
3. **失败时大声报错** - 脚本遇到真正的失败必须非零退出
4. **不得伪造成功状态** - 除非经过验证，否则不要报告"✓"
5. **每个完成任务必须更新 task.json 和 progress.md**
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

### 开发铁规则

15. **所有代码都要有全面的测试** - 新增或修改功能时，必须同时添加完整的测试覆盖

### Session 规则

16. **每个会话只处理一个任务** - 专注高质量完成一个任务
17. **标记完成前必须测试** - 所有成功标准都必须通过
18. **UI变更必须浏览器测试** - 新建或大幅修改页面必须使用 Playwright MCP 测试
19. **每个任务集必须有自己的进度文件** - 任务集 `af-auto-xxx` 必须有对应的 `progress_af_auto_xxx.md`
20. **每个任务一个 commit** - 所有更改（代码、progress 文件、task.json）必须在同一个 commit 中提交
21. **永远不要删除任务** - 只将 `status` 从 `"todo"` 改为 `"done"`
22. **阻塞时立即停止** - 需要人工介入时，不要提交，输出阻塞信息并停止

---

## 控制层限制和假设

- 假设 PostgreSQL 运行在 localhost:5432
- 假设 API 可能已在 8000 端口运行
- 假设 git 仓库是干净的
- 不会执行不可逆操作
- 不会优雅处理网络故障
- 会管理任务依赖（使用 task.json 中的 dependencies 字段）
- 会从断点恢复中断的任务
- 不会处理并发执行
