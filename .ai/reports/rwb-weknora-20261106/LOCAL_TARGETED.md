# 最终定点 Python 验证

- 结果：133/133固定node IDs完成，133 PASS、0 SKIP、0最终失败/错误、0 NOT_RUN。
- 范围：9个WeKnora模块75例、multiuser_cli58例；清单未裁剪，SHA-256 `e920928d5465259d3bb557cd3e63fa2a6ede406a7ef3e68b8af9b1a334edbfad`。
- 宿主：macOS；共享Python；WIP HEAD基线 `f1939eccdcfe924ed661cff7314ccb8ddf7eebc4`。工作区改动未提交，本报告不认证最终exact-SHA、真实业务部署或其他平台。
- 原始7批＋同nonce恢复累计28.921秒；7/7正式回执retired，活动本任务临时根0。512MiB根／64MiB输出／3GiB宿主门保持。

| 批次 | node IDs | 最终tests/fail/errors/skips | 实际pytest/初次入口退出码 | 状态 | 秒 |
| --- | ---: | --- | --- | --- | ---: |
| targeted-python-001 | 20 | 20/0/0/0 | 0/0 | completed | 13.573 |
| targeted-python-002 | 20 | 20/0/0/0 | 0/0 | completed | 2.391 |
| targeted-python-003 | 20 | 20/0/0/0 | 0/0 | completed | 2.075 |
| targeted-python-004 | 20 | 20/0/0/0 | 0/0 | completed | 3.906 |
| targeted-python-005 | 20 | 20/0/0/0 | 0/0 | completed | 2.374 |
| targeted-python-006 | 20 | 20/0/0/0 | 0/1 | completed | 1.355 |
| targeted-python-007 | 13 | 13/0/0/0 | 0/0 | completed | 3.247 |

## 原失败与恢复

- 第6批首次真实20例中17 PASS、3 FAIL，退出1；三个失败均为冷Doctor原有隔离guard拒绝导入server模块。原stdout/stderr/JUnit/result完整保留，未把首次失败改写为PASS。
- 主任务将origin解析移至全stdlib `knowledge_configuration.py`；dispatcher与冷Doctor共享该helper，无测试断言放宽。变更只有server.py、multiuser/__main__.py、新helper三项，前后Git blob/SHA映射见retry attempt及closeout observation。
- 在原root/nonce `8404bea7593e429f899cd8f62fe7aca2` 保留原active与3FAIL证明，追加retry-active和新proof，原batchId/20 IDs真实复测20 PASS、退出0（0.740秒），再由正式retire_root退役。之后原集合第7批13 PASS、退出0。
- 原失败result SHA-256：`d6a9c364a7268da5fd3db3c1bd6eba3310f2b2def5be46c2044a0faf0b1a2a23`。
- 恢复PASS result SHA-256：`02587ad91acaedecd7e300a03177b2b46a5442f51ea237fd713617fd72cf8ca1`。

## 证据与边界

- 完整原件、每批正式回执及源码映射：`logs/weknora-targeted-python/private/`；结果摘要：`logs/weknora-targeted-python/summary.json`。
- 前100例与修复后的33例保留各自WIP源码身份；第6批恢复后到最终复核源码漂移0。测试源未随修复改变，不重新标记首次失败或较早运行的源码版本。
- 仅使用隔离fixture和MockTransport，没有真实模型、供应商调用、生产服务变更或Git修改。成功临时根按身份即时收尾，历史失败证明保持。
