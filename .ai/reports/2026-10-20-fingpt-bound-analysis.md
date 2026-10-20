# FinGPT自由分析系统绑定修复

宿主macOS/arm64；Web功能开发，本平台验收及Mac CI。DSH唯一引擎，原质量门未改。数据/模型配置保留，部署仅空闲准入；真实Flash同题仅新增一次，完成前保持NOT_RUN。

## 复现与实现

本次真实SID 4791a6a3-c613-47fd-994c-4055b983422c的两篇公报正文、Host发布日期证据和失败报告以SHA封存于tests/research_web/fixtures/fingpt-20261020。原report_plan接受手写52795及错误−1.05%，RED16项失败；新自由分析用fact/formula完整标签引用，Host从原始输入重建plan/声明/呈现。精确年度增量52795、名义3.91%、未舍入隐含平减指数−1.03%，不认证可比性。

审计附件保留重复英文底稿与精确轨迹，实际正文中文/去重表。附件语义core绑定+canonical/不可变归档完整SHA绑定，JSON最后发布及恢复保持；Host另核对实际HTML/DOCX/PDF渲染，不接受伪造自洽hash。新网页任务冻结policy防止降级，旧receipt不迁移。

## 实际验证

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. 主产品.venv/python 调用已存在私有pytest_runner.py，test_bound_analysis.py 42 passed in 1.07s；首轮16项RED已归档。此前139项系统/格式/计算/修订回归2.80s通过，新增审计文件导致旧文件计数断言需要同步；完整扩展回归211通过、2失败（计数断言）、1 skipped，实际122.92s，失败日志保留并继续修正，不视为最终通过。

本次真实记录离线回放0模型调用，原题SHA81385dc8675d5f7c45fae311aa42ca3c1840fbadf84531ea7f9029438e9acd4c；中文正文1291字，所有数字声明通过，质量仍incomplete：解释性分析、最终核实/可比性缺口保留。已有正常通过及来源/声明/呈现/附件/渲染损坏后恢复测试；最终Router/独立评审/CI/部署/真实复测结果待本地私有证据完成后记录。

私有证据：~/.research-workbench/acceptance/fingpt-bound-analysis-20261020/；离线只读效果页127.0.0.1:8102。不写业务数据、Keychain或生产模型配置，无安装新包。其他平台原生NOT_RUN交接，工程通过不替代研究质量。

原生转换器检查发现原工具混用type/oneOf及不支持的边界关键字；wire改为独立互斥对象分支，所有16/40/8/0..12及32000字节等实际限制仍由原入口/SDK强制，未删除质量或执行预算。先前default dsh-source为陈旧c919b2a，实际固定runtime为7ecf564；两次失败日志保留，最终必须在固定runtime转换器重验通过。
