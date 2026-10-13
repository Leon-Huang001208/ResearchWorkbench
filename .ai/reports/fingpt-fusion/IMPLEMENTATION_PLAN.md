# FinGPT Fusion Implementation Plan

> **For agentic workers:** Execute inline using executing-plans; no parallel implementers are assigned.

**Goal:** 原生计划、会话证据与统一中文报告完成 FinGPT 深入研究闭环。

**Architecture:** DSH 为唯一研究循环及历史真源。Web 只投影原生计划、资料与报告 artifact；HTML、DOCX、PDF 共用底稿。计划、执行、质量与文件交付分开认证。

**Tech Stack:** FastAPI、原生 ESM、固定 DSH、ReportLab、python-docx、pdfplumber。

## A. 深度与原生计划

- [x] test_fingpt_research.py 先测试全量替换、失败终态、新回合清空、无回合历史及坏事件；3 个 KeyError 为 RED。
- [x] GitHub 当前固定 DSH 48504f07 核对 todo/write、tools/sessionProjections 注入及必填 allowParallelInProgress。
- [x] projection.py、runtime/research.cordis.yml、guard.mjs：真实计划投影、插件装配、精确工具允许；协议/恢复/权限反例通过。
- [x] main.py、service.py、ui/core.mjs/composer.mjs/app.mjs：NewSession.research_depth=instant/deep，缺省 instant；草稿随受理锁定，既有会话不静默改写。
- [x] 深入研究原生 prompt 明确计划、来源、时点、底稿与交付要求；shell.mjs 展示真实计划，不由勾选推断完成。

## B. 会话证据与研究底稿

- [x] 新 research_evidence.py：从实际 search 结果、datasets 与本会话附件派生有界来源索引；没有全文读取证据时标为摘要。
- [x] 底稿 outputs/research-report.json 绑定 delivery.task_id，含 sections、required_sections、notes、missing、citations；未知来源、跨会话引用、缺章节、过期版本及恶意输入均不认证质量通过。
- [x] service.py 使用 Store.open_file 安全读取；ui/research-report.mjs 与 shell.mjs 显示证据、笔记、报告，保留既有活动/资料/文件。
- [x] 四种快捷入口复用既有能力或准备草稿，不自动发送、不开第二套运行器。

## C. PDF 与统一交付

- [x] resources/research_report.py、research_helpers.py 以相同 payload 生成 HTML/DOCX/PDF，包含引用与缺口。
- [x] 提供带许可和固定来源摘要的中文 TrueType 字体；无远程字体或宿主 Office 依赖。
- [x] main.py/delivery.py/report_rendering.py/report_render_script.py/ui/views.mjs 向后兼容增加 pdf；重开、文字、页数、哈希与文件上限检查。
- [x] requirements/web.in 添加 ReportLab，用原 universal/Python3.12/hashes 参数再生 web.lock；核对旧依赖漂移并同步安装入口、文档与 bootstrap 兼容。

## D. 验证与交接

- [ ] `.venv/bin/python -m pytest tests/research_web/test_fingpt_research.py tests/research_web/test_protocol.py tests/research_web/test_event_recovery.py --confcutdir=tests/research_web -q`。
- [ ] 新证据/PDF用例验证中文、引用一致、覆盖缺口与坏 PDF；`node --test tests/javascript/research_web_guard.test.mjs tests/javascript/research_web_ui.test.mjs`。
- [ ] 依据完整 changed set 生成验证计划；执行路由要求的格式/类型、文档治理、索引与架构检查。
- [ ] 原生插件、浏览器产品冒烟、干净安装与 Mac CI 分别记录；未授权付费模型及 push/merge/dispatch 保留 NOT_RUN。
- [ ] 保存 PROGRESS/BLOCKED 与日志、Harness 状态及主 checkout 保全证据。

本地执行完成的证据与未执行/基线失败见 PROGRESS.md 及 live-research-receipt.json；禁止将总体验收及远端CI标为PASS。
