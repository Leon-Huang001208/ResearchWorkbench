---
name: Code Quality Standards
description: AlphaFoundry 代码质量规范 - black, isort, ruff, mypy
---

# 代码质量规范

## 概述

AlphaFoundry 使用统一的代码格式化和检查工具，确保代码风格一致。

---

## 工具配置

### black 格式化

**配置文件位置**：`pyproject.toml` 的 `[tool.black]` 部分

**基本命令**：
```bash
black .
```

**常用选项**：
- `--check` - 只检查不修改
- `--diff` - 显示差异而不修改
- `-v` - 详细输出

**代码检查清单**：
- [ ] 提交前运行 `black .`
- [ ] 确保所有 Python 文件被格式化
- [ ] line-length 保持在 100 字符以内

---

### isort 导入排序

**配置文件位置**：`pyproject.toml` 的 `[tool.isort]` 部分

**基本命令**：
```bash
isort .
```

**常用选项**：
- `--check` - 只检查不修改
- `--diff` - 显示差异而不修改

**导入分组约定**：
1. 标准库导入
2. 第三方库导入
3. 本地项目导入
4. 每组之间用空行分隔

**代码检查清单**：
- [ ] 提交前运行 `isort .`
- [ ] 确保导入顺序正确

---

### ruff 代码检查

**配置文件位置**：`pyproject.toml` 的 `[tool.ruff]` 部分（如需要）

**基本命令**：
```bash
ruff check .
```

**常用选项**：
- `--fix` - 自动修复可修复的问题
- `--watch` - 监听文件变化
- `--select <rules>` - 只检查指定规则

**代码检查清单**：
- [ ] 提交前运行 `ruff check .`
- [ ] 确保没有错误或警告（或理解为什么可以忽略）
- [ ] 使用 `--fix` 自动修复简单问题

---

### mypy 类型检查

**配置文件位置**：`pyproject.toml` 的 `[tool.mypy]` 部分

**基本命令**：
```bash
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
```

**常用选项**：
- `--strict` - 严格模式
- `--ignore-missing-imports` - 忽略缺失的导入
- `--show-error-codes` - 显示错误代码

**类型注解约定**：
- 所有公共函数和方法必须有类型注解
- 复杂数据结构使用 `typing` 模块（`List`, `Dict`, `Optional` 等）
- Pydantic 模型自动提供类型支持

**代码检查清单**：
- [ ] 新代码包含完整的类型注解
- [ ] 运行 `mypy` 没有类型错误
- [ ] 对确实无法注解的地方使用 `# type: ignore` 并说明原因

---

## 完整检查流程

提交代码前运行：

```bash
# 1. 格式化导入
isort .

# 2. 格式化代码
black .

# 3. 检查代码质量
ruff check .

# 4. 类型检查
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
```

或使用单个命令检查（不修改）：
```bash
black --check . && isort --check . && ruff check . && mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
```

---

## 例外情况

以下情况可以例外：
- 第三方库生成的代码
- 临时脚本文件（放在 scripts/ 目录并在文件名中标注）
- 测试文件的类型检查可以适当放宽

