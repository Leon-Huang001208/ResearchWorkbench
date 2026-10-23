# 经济事件原生字段保留修复

宿主 macOS；本任务是既有 Web 私有 Excel Provider 的功能缺陷修复，验收范围为离线
合成来源与本机 Python 静态检查。基线 `f58c1d5e1cc1256856b09e726d000d8be483eeb1`。
本报告不认证远端最终 SHA、CI、常驻部署、Office/Wind 实采或正式报告质量。

## 根因与范围

`_run_owned` 的经济事件字典仅投影日期、原页名、国家、指标和重要性，遗漏原生第2、6、7、8列。
修改为保留 `time/previous/forecast/actual`；缺列、None和空字符串为None，其余仅接受
原样字符串、整数及有限浮点数，零不丢弃。布尔、非有限浮点、容器和 `datetime.time`
等未审类型沿原 `weekly_excel_collection_blocked` 日志及
`weekly_excel_economic_value_invalid` 限制显式阻断。不补值、不改单位、时区或Word母版三列。

生产差异仅12行近处标量helper及4行字段映射。移除这两处新增后，与基线Provider逐字节一致；
市场采集、57项、日期／重要性／原页名、哈希、双sheet、周日覆盖、clear代码均保持原字节。
范围断言和哈希见 `logs/etf-excel/economic-fields-scope-hashes.json`。

## 实际验证

- RED：修改原有8列经济数据／5或8列财经大事夹具，加入真实数值及可选字段断言；
  原实现两例均 `KeyError: time`，日志 `economic-fields-red.log`。
- 首次完整回归148 passed／21 failed：失败均来自新反例夹具尾部None被读取器裁剪后赋值越界；
  已在测试输入注入前补足8列，未调整生产规则。原日志 `economic-fields-provider-green.log` 保留。
- 修复后完整Provider 180 passed／21.68秒，日志 `economic-fields-provider-final.log`。
- 合法标量正例随后改为真实合成XLSX，重新冻结导出哈希、原生观察、coverage及SOURCE_CONTRACT；
  相关既有成功夹具也同步冻结其实际变更。再次180 passed／22.66秒，日志
  `economic-fields-provider-frozen.log`。XLSX会把0.0编码为整数0，断言以实际解码类型为准。
- 新反例覆盖四个字段各自的True／False／NaN／正负无穷／list／dict／datetime.time；
  正例覆盖缺省、空串、含空白字符串、整数零、浮点零、负有限小数及整数，原双页顺序保持。
- Ruff、Black、isort两近处Python文件通过；mypy
  `--follow-imports=silent --check-untyped-defs` Provider通过。首次Black指出测试格式需调整，
  已格式化且重新通过，保留initial日志。diff检查通过。

实际测试命令（无依赖安装、无真实xlwings导入）：

```bash
PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/lib/python3.12/site-packages \
/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/bin/python \
-c 'import sys,types,pytest; sys.modules["xlwings"]=types.ModuleType("xlwings"); sys.exit(pytest.main(["--noconftest","tests/research_web/test_datahub_wind_excel_weekly.py","-q"]))'
```

上述日志均位于 `logs/etf-excel/`。静态命令使用同一既有任务 `.venv/bin/` 的
`ruff check`、`black --check`、`isort --check-only` 与 `mypy`，目标为本次Provider和测试
（mypy仅源码）。未使用Git写操作、网络、Office、供应商、模型、新依赖或原raw快照重写。
主任务负责完整Router／Harness、独立同冻结来源重放、最终候选评审／CI／Git交付；Host新增
原件独立核验由另一受限任务维护，不以本Provider断言替代其验收。

最终本子任务源码SHA-256：Provider
`3f568867b3a53896a29cdb6cd359984cfc48c18a4b3769c9a462050c91608520`；测试
`3015616addfd2284d210bf1a0fa8e1fef846714808c82741ef6be4152f05ab2c`。
这些是文件身份，不是最终Git候选批准；任何后续变更须重新绑定实际哈希与检查。

联合Host原件门复验：首轮211例209通过、2失败，均为另一任务新增Host用例的夹具字段及
校验顺序问题，原失败日志 `economic-fields-provider-host-final.log` 保留。负责Host的任务
修正后，以以上同一命令同时选取Provider与
`tests/research_web/test_report_weekly_economic_fields.py`，实际212 passed／28.97秒，
日志 `economic-fields-provider-host-v2.log`。此轮再次验证Provider180例及Host32例；
未删旧门或放宽失败状态。随后Ruff／Black／isort两文件及全diff whitespace检查仍通过。
