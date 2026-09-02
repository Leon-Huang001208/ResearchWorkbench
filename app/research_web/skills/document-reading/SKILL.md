---
name: document-reading
description: 解读上传的 PDF、图片、Markdown、CSV 和 Excel，按页码或工作表定位来源。Use when 用户要求阅读研报、财报、说明书或上传资料。
---

# 资料解读

1. 只读取当前会话 inputs 中用户选定的附件；先列出真实文件名和类型。
2. 用 af_run_script 的 Python 读取资料；PDF 使用 `resources/research_helpers.py` 的 `read_pdf`，返回的 page 从 1 开始。空文本页说明需要 OCR，不编造页码。
3. 分别列出原文观点、数据和你的分析；引用格式 `[文件名，第 N 页]`，表格注明 sheet/列名。
4. 发现冲突或缺失时显式列出，不能用零补缺失。
5. 用户要求文件时运行脚本实际生成到 outputs，检查存在且能够重新打开，再给出文件名。不要把聊天正文当 Word/Excel。

示例：在 af_run_script 中 `from research_helpers import read_pdf; print(read_pdf('inputs/实际文件.pdf'))`。
运行器已经加入当前会话的只读资源导入路径；不要添加相对 sys.path，也不要依赖读取会话根目录或 getcwd。

报告结构见 `templates/report.md`。共享脚本随新会话复制到 resources，不访问宿主资料。
