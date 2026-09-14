# Research Workbench 推理方法层任务记录

## 范围

- 仅实现 Research Workbench 独立 Method 层；不把 Codex／Claude 建模为产品 Runtime。
- 三份外部 Markdown 只作为思想来源，未修改、迁移或复制正文。
- 新增十个内置、版本化、只读、无脚本、无依赖、无外部权限的 Method。
- DSH 仅承担 Runtime 适配，将 Method 编译为原生 Skill 包装并保留稳定产品 ID。
- 不修改现有报告项目的 `prompt_templates.md`；Prompt 模板库等待真实 Method Evals 通过后另行实施。

## 实现

- `capabilities/methods.py` 定义 `ReasoningMethodSpec`、固定优先级解析、三方法上限、冲突／缺失失败、
  本轮采用证据检查、三场景三变体评测矩阵和晋级门。
- Skill／Workflow 元数据增加 `method_policy`；研究请求增加可选 `method_ids`，会话收据锁定解析后的
  方法 ID、语义版本、目录版本、原生名称与选择来源。
- `rwb_record_method_use` 只接收并写入 `method_id`、`version`、`source`；拒绝额外字段，保持会话
  隔离、有界文件和链接防护，不记录 Prompt、正文或隐藏思维链。
- 必需／用户指定 Method 缺证据时阻断完成；推荐／模型补选缺证据时标记
  `method_trace_incomplete` 并允许降级。
- 能力中心增加独立“方法”页签，研究输入区支持最多三个手动选择；会话页显示采用来源和降级提示。

## 权限与依赖

- 未新增或安装任何依赖。
- Method 不增加数据、文件、网络、shell 或模型权限；内部采用记录工具不进入用户可选 Tool。
- 未触碰 `src-tauri/`、`desktop/`、`scripts/desktop/` 或 `services/desktop_platform/`，本任务不是桌面交付。

## 评测与下一阶段

- 当前只交付可复现的 Research Eval 矩阵与晋级判定代码，不虚构真实模型质量结果。
- 十个 Method 均至少包含三个投研样例，覆盖 baseline、single、combined 三种变体。
- 默认 `recommended` 保持为空。真实评测证明质量改善且成本、延迟无明显倒退后，才允许配置默认推荐
  并启动用户可编辑、版本化的 Prompt 模板库。

## 验证证据

- `DSH_SOURCE_ROOT=/Users/leon/.research-workbench/dsh-source python -m pytest tests/research_web --confcutdir=tests/research_web -q`
  ：`920 passed, 1 skipped, 1 warning`；warning 为 Starlette `BlockingPortal` 弃用提示。
- `DSH_SOURCE_ROOT=/Users/leon/.research-workbench/dsh-source node --test tests/javascript/research_web*.test.mjs`
  ：`272 passed, 0 failed`。
- `python -m ruff check ...`、变更 Python 文件的 Black／isort、全部变更 MJS 的 `node --check` 及
  `git diff --check` 均通过。
- `node scripts/check_research_architecture.mjs`、`python scripts/check_doc_sync.py` 及携带全部变更路径的
  `.agents/project-constraints.mjs` 均为零违反。
- 隔离浏览器夹具验收通过，共 38 项检查、51 张截图、零模型／变更请求和零浏览器运行时错误；覆盖
  Light／Dark、1440／1280／768／390 响应式布局、五类能力页、键盘页签、方法详情与三方法上限。
- 人工查看了 Light 方法库、Dark 方法选择器和 390px 移动端能力工作区截图；未见遮挡、横向溢出、
  文本截断或不可见焦点。
