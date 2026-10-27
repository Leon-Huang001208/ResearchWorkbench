# C3/C4 自有方法动作切片

宿主：Mac mini / macOS；任务：Web 功能开发。工作区基线
`397365b1c565636eb1b8c9955efecad5d18d627d`，沿主任务已启动 Harness，不重复初始化。

已实现三份 `kind=skill` 版本化方法包、冻结 stdlib 原件动作、严格 query/limit 与问题预置适配。
没有增加模型循环、引擎、供应商调用、依赖、秘密、部署或 schema 数据库迁移。

RED：新增参数测试先因模块缺失失败，证据 `/tmp/rwb-c3-actions-3V1xlNQt/red.log`。
首轮 GREEN：参数/原件 32 tests PASS，Catalog/冻结脚本 3 tests PASS，证据同目录
`green.log`、`packages.log`。该目录已登记 owner.json。
后续当前纯模块目标集 `target3.log`：43 tests PASS；Ruff、Black、isort 对本切片 Python 文件通过。
实际重开三份已有官方摘录的原 SHA（MSFT income/cashflows、FOMC September），不等于新抓取、完整文档
或 live 来源证明。未执行 mypy（现成环境 librt 不可用），不安装依赖补门。

## 当前集成切片

主任务已批准并实现固定三 CID 的 `method_execution={capability_id,version,context_sha256}`。
三份独立 owned-method 场景沿原 prepare/handoff/send/选材链运行，原八合同字节不变；来源选择使用
固定 registry 区分旧两 pack 与三方法，不产生伪 pack_seal、pack 资格或执行记录。

`scenario_method_sources.py` 从当前授权原件冻结 inputs/methods 私有副本，Host 固定 launcher、
真实 Native supervisor 与原私有桥 `kind=owned-method` 完成后，Host 重新授权、核文件身份、重读
原件与 ledger，并用已验证与冻结资源同字节的固定函数复算，再写原 receipts/index.json 的
method_executions.saved。普通 code 不能读内部原件或写 method-results，不能自造 ran。

私有输入明确由现 HTTP file、Dossier file 与 Claw reference 三入口按 path.parts[:2] 固定拒绝，
包括旧缓存 ID、.txt 半文件、撤权和回执缺损，不以扩展名当唯一边界。原 page-evidence、普通上传及
来源引用仍进入旧强核。仅已登记 scope.file_bindings 的生成副本从数字观察投影排除；未登记文件
仍可使真实 quality 返回 invalid。取消/未知不保存为成功，也不能换 callId 重跑。

## 实际验证

- `integration-final.log`：53 tests PASS。三方法各实际 source capture/read→固定 DSH SkillProvider/
  ToolRuntime/guard→原 sandbox→私有 completion→Host复算→原 report_plan/canonical/HTML/DOCX→
  research_check_quality。正例真实状态均 incomplete；公司原表 245122/211915 经系统计算为15.67，
  测试叙事为 scripted fixture，不是真实模型。覆盖取消、不可重试、完整性、普通 code 禁读写、
  receipt 丢失、撤权、半文件、未知输入触发 invalid。
- `regression-final.log`：25 tests 已通过后，旧 stage2 总 Skill 数30断言失败。前三十之外，397基线
  已有九 pack（实际39），本候选再加三方法为42。stage2/3/4 仅更新显式42与九 pack/三方法集合，
  六/七/五个旧算法的 disabled、receipt、selection 拒绝保持；不是新方法等价通过旧阶段。
- `gates-final.log`：修目录计数后，三阶段18禁用门与原零分母剩余目标共5 tests PASS。前25包含
  原八场景、原两pack实际 Native（含取消）、weekly 权限与普通 sandbox；不重复执行已过25项。
- `source-picker-js.log`：20 tests PASS，包含固定 owned flag、旧两pack、来源预览/冻结及 unknown。
  Ruff、Black、isort 对26个本切片 Python 文件 PASS，五个改动 JS 文件/Native helper 的 node --check PASS。
  mypy NOT_RUN（主任务已记录现成环境 librt 缺口），没有安装依赖。
- DataHub 财务正例使用实际 Sina HTTP MockTransport→原 provider parser→真实 snapshot manifest/query/rows：
  600600.SH、2026-06-30 与 CNY 保留，单位与累计 basis 未知保持 partial。没有 mock DataHub.query 或
  假造单位；也没有声称执行了真实供应商请求。

## 尚未实现的代码集成

1. C2 去重制品尚未绑定，新闻/调研明确 source_version_dedup_not_run；属于 CODE integration pending。
2. C4 仅严格纯参数函数，未接实际兼容工具入口；C1 全部相应参数仍 unsupported/pending，没有 mapped。
3. 原 report_plan percent_change 尚无 owned 方法对非正基数的独立准入硬门。现正基数示例与零分母
   回归不覆盖负基数；禁止升级为完整财务方法或正式映射。不改通用数学，下一窄集成处理。
4. 现 annual 解析器不认证实体/URI/通用币种。MSFT fixture 的 numeric/report_plan 链可跑，但来源动作
   保留 unclassified/financials 缺口，没有新增 MSFT URL 专用分类。非 UTF-8/PDF reader 自动接入未实现。

真实模型、外部来源网络、正式研究接受、部署与其他平台 NOT_RUN；当前候选不是整个 T3 完成。

## 本轮测试资源收尾

只归档并回收本轮登记的 `/tmp/rwb-c3-actions-3V1xlNQt` 下19个 pytest 子目录。510份必要原件、
Store index/执行回执、canonical/格式/ledger 与日志进入 `evidence/run-evidence.tar.gz`（2,369,573 bytes），
SHA-256 `721d4377e10f3193b97a3f0704b55c9e81760bcb5b3839237243a82445ebe14c`。
全部41,002,652原始字节逐文件恢复后按 manifest SHA-256 读回通过，详见
`evidence/retirement.json`。初次清理遇只读测试包目录失败，
仅给本轮已验证退休目录恢复 owner 写位后重试成功，回执 status=cleaned。未改任何服务、全局配置、
其他任务、Docker 或工作树。测试根1.7 GiB降为4.0 MiB，磁盘可用由5.9 GiB回到7.7 GiB。

模块合同与边界见 `docs/research-web-owned-methods.md`。独立 SPEC/QUALITY、完整 Router、
本地 CI、Mac 干净安装及发布交由主任务聚合，不由本切片自评替代。
