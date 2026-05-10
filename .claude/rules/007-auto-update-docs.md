---
name: Auto Update Documentation
description: AlphaFoundry 文档更新规范 - 每次项目迭代必须更新的核心文档
---

# 文档更新规范

## 概述

**每次项目迭代完成后，必须同步更新以下核心文档，确保文档与代码保持一致。**

---

## 核心文档清单（每次迭代必须更新）

| 文档 | 位置 | 更新内容 | 检查点 |
|------|------|----------|--------|
| **README** | `README.md` | 功能列表、实施进度、快速开始 | ✅ 功能是否完整？进度是否更新？ |
| **REFERENCE** | `docs/REFERENCE.md` | CLI 命令、API 接口、服务使用 | ✅ 新增命令？新增 API？新增服务？ |
| **ARCHITECTURE** | `docs/ARCHITECTURE.md` | 架构设计、模块说明、数据流程 | ✅ 架构变更？新增模块？ |
| **CHANGELOG** | `docs/CHANGELOG.md` | 变更记录、新增功能、修复内容 | ✅ 本次迭代的所有变更 |
| **FILE_GUIDE** | `docs/FILE_GUIDE.md` | 文件说明、新增文件、目录结构 | ✅ 新增文件？目录变更？ |

---

## 其他文档清单（按需更新）

| 文档 | 位置 | 更新场景 |
|------|------|----------|
| 快速开始 | `docs/QUICKSTART.md` | 新增安装步骤、变更配置方式、新增快速入门示例 |
| CLI 指南 | `docs/CLI_GUIDE.md` | 新增 CLI 命令、变更命令参数、新增使用示例 |
| 备份恢复 | `docs/backup_restore.md` | 变更备份流程、新增恢复方式 |
| 数据源 | `docs/DATA_SOURCES.md` | 新增数据源、变更数据格式 |

---

## 需要更新文档的场景

### 新增功能时

- [ ] 更新 README.md 功能列表
- [ ] 添加或更新使用示例
- [ ] 更新相关的指南文档
- [ ] 如有新 CLI 命令，更新 CLI_GUIDE.md

### 变更 CLI 命令时

- [ ] 更新 CLI_GUIDE.md 中的命令说明
- [ ] 更新参数列表和说明
- [ ] 添加新的使用示例
- [ ] 更新命令速查表

### 变更配置时

- [ ] 更新 .env.example
- [ ] 更新 QUICKSTART.md 中的配置说明
- [ ] 更新相关文档中的配置引用

### 变更架构时

- [ ] 更新 ARCHITECTURE.md（如存在）
- [ ] 更新目录结构说明
- [ ] 更新模块关系说明

---

## README.md 更新约定

### 进度标记

更新实施进度部分：

```markdown
### 五月：事实层与报告骨架
- [x] 项目基础配置与目录结构
- [x] Core Contracts（Pydantic 模型）
- [x] Core Interfaces（接口定义）
- [ ] 待完成任务
```

### 功能描述

添加新功能的简要描述和使用示例：

```markdown
## 核心特性

- **资产分析卡**：对股票、ETF、指数等资产形成标准化快照
- **专题研究备忘录**：围绕产业链、政策变化等主题形成结构化研究
- **新增功能**：新增功能的简要描述
```

---

## CLI_GUIDE.md 更新约定

### 新增命令

添加新命令的完整说明：

```markdown
## 新命令名称

命令简要说明。

### 基本用法

```bash
af command --option value
```

### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--option` | ✅ | 选项说明 |

### 使用示例

```bash
# 示例 1
af command --option value
```
```

---

## 每次迭代完成后的检查清单

### 1. CHANGELOG.md 更新
- [ ] 在 `[Unreleased]` 部分添加本次迭代的所有变更
- [ ] 按类别组织：Added、Changed、Fixed
- [ ] 每项变更有清晰描述
- [ ] 涉及的关键文件有提及

### 2. README.md 更新
- [ ] 更新功能列表（如新增核心功能）
- [ ] 更新实施进度标记
- [ ] 更新快速开始示例（如有变化）
- [ ] 检查链接是否有效

### 3. REFERENCE.md 更新
- [ ] 更新 CLI 命令说明（如有新增/变更）
- [ ] 更新 API 接口文档（如有新增/变更）
- [ ] 更新服务使用示例（如有新增服务）
- [ ] 更新 Signal Lab 文档（如有变更）

### 4. ARCHITECTURE.md 更新
- [ ] 更新架构图（如有架构变更）
- [ ] 更新模块说明（如有新增模块）
- [ ] 更新数据流程（如有变更）
- [ ] 更新开发路线图（如有调整）

### 5. FILE_GUIDE.md 更新
- [ ] 添加新增文件的说明
- [ ] 更新目录结构说明
- [ ] 更新文件用途描述
- [ ] 检查所有链接是否有效

---

## 迭代发布检查清单（版本发布时）

当准备发布新版本时：

### 版本准备
- [ ] 在 CHANGELOG.md 中将 `[Unreleased]` 改为新版本号
- [ ] 添加新的 `[Unreleased]` 部分在顶部
- [ ] 在 README.md 更新版本号
- [ ] 检查所有文档中的版本引用

### 最终检查
- [ ] 运行 `pytest` 确保所有测试通过
- [ ] 运行 `black .` 和 `isort .` 格式化代码
- [ ] 运行 `ruff check .` 确保没有代码质量问题
- [ ] 运行 `mypy` 确保没有类型错误
- [ ] 运行 CLI 帮助命令确保无错误
- [ ] 启动 Web 服务确保可以正常访问

---

## README.md 更新约定

### 进度标记

更新实施进度部分：

```markdown
### 五月：事实层与报告骨架
- [x] 项目基础配置与目录结构
- [x] Core Contracts（Pydantic 模型）
- [x] Core Interfaces（接口定义）
- [ ] 待完成任务
```

### 功能描述

添加新功能的简要描述和使用示例：

```markdown
## 核心特性

- **资产分析卡**：对股票、ETF、指数等资产形成标准化快照
- **专题研究备忘录**：围绕产业链、政策变化等主题形成结构化研究
- **新增功能**：新增功能的简要描述
```

---

## CHANGELOG.md 更新约定

### 格式规范

```markdown
## [Unreleased]

### Added
- **模块/功能**：简要描述新增内容

### Changed
- **模块/功能**：简要描述变更内容

### Fixed
- **模块/功能**：简要描述修复内容
```

### 条目示例

```markdown
### Added
- **Signal Lab**：完整的信号研究模块，包含特征工程、标签生成、信号评分和回测功能
  - `signal_lab/features/` - 特征工程框架
  - `signal_lab/labels/` - 标签生成框架
  - `signal_lab/scoring/` - 信号评分框架
  - `signal_lab/backtests/` - 回测引擎

### Changed
- **AKShare Integration**：重构 AKShare 集成，统一使用 crawler 模块的 utils
  - 新增 `data_layer/crawlers/akshare/utils.py`
  - 重构 `data_layer/crawlers/akshare/market.py`
  - 重构 `data_layer/crawlers/akshare/financial.py`

### Fixed
- **Dashboard**：修复仪表盘数据问题，给 SignalOutcomeDB 添加 event_type 字段
```

---

## CLI_GUIDE.md 更新约定

### 新增命令

添加新命令的完整说明：

```markdown
## 新命令名称

命令简要说明。

### 基本用法

```bash
af command --option value
```

### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--option` | ✅ | 选项说明 |

### 使用示例

```bash
# 示例 1
af command --option value
```
```

---

## 文档检查清单

完成功能开发后确认：
- [ ] 所有相关文档已更新
- [ ] 使用示例代码可正常运行
- [ ] 命令行参数说明正确
- [ ] 进度标记（如适用）已更新
- [ ] 没有过时的文档内容

