# 资产分时正式接入进展

Mac功能开发，隔离worktree；用户已采用v0并授权验收后受控部署。当前未更新常驻，登录/会话/业务数据无写入。

真实样本：10月23日1m为241点，5/15/30/60/120m分别49/17/9/5/3根；含09:25竞价，量额均对齐日线。正式Workspace→DataHub→Broker→Provider链于10月26日开盘后取得当日9点，固定昨收292；原件、读取时间和分钟标签保留，正在形成的分钟标签不等于已完成时点。分钟K仅实源核验，尚未产品接入。

本地近处Python210通过，完整Research Web JS1199通过/3项原有skip；首轮完整Router L4的14本地门通过（测试环境失败/文档门失败原记录保留，修复后通过）。最终提交仍重跑同候选门；最终独评、CI和同候选Mac安装/常驻认证仍待执行，不能作为完成。证据保存在私有logs/asset-intraday-contract-20261026，供应商和离线输入分开；无模型、新依赖或凭据导出。

图层不重建K，动态授权缓存、64项上限、整分钟、空结果清图与窄屏裁剪已针对首轮评审修正，最终评审待绑定最终候选。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "分时为原Host资产区与DataHub固定来源快照链内的有界展示分支；没有新增节点、服务、数据库或研究引擎，原图的浏览器/Host/Provider/冻结边保持准确，新增HTTP逐项登记API Atlas。", "diagrams": []} -->
<!-- architecture-review {"group": "workbench", "structure": "unchanged", "reason": "分时为原Host资产区与DataHub固定来源快照链内的有界展示分支；没有新增节点、服务、数据库或研究引擎，原图的浏览器/Host/Provider/冻结边保持准确，新增HTTP逐项登记API Atlas。", "diagrams": []} -->
<!-- architecture-review {"group": "datahub", "structure": "unchanged", "reason": "分时为原Host资产区与DataHub固定来源快照链内的有界展示分支；没有新增节点、服务、数据库或研究引擎，原图的浏览器/Host/Provider/冻结边保持准确，新增HTTP逐项登记API Atlas。", "diagrams": []} -->

<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "仅在既有Checks步骤登记分钟回归并使用原JS通配符，不新增job、runner、依赖或超时；原Mac安装和仓库硬门保持，既有验收/交付拓扑不变。", "diagrams": []} -->

部署独立阻断：旧b800实际常驻仍由受控恢复任务处理合作接入/未知活动见证；本任务不附加进程、不清poison、不重启旧实例，也不以源码绿替代现场门。

首个候选af334ccad：后端独评Approve；前端发现主题重挂载可能丢失empty/failed/pending状态，修复为当前状态统一渲染，不在异步闭包持有旧DOM节点。增加隔离fixture负例/延迟条件用于真实浏览器验收，原失败结论保留，不算最终通过。

## 原CI超时与修复1

候选0e4ceeb2的Checks40262625759在40m上限取消：Python7109通过/72原skip/117subtests（2201.70s），另47通过（0.89s）；JS1199通过/3原skip（20.80s），但step因总时限取消，末尾固定编辑引擎检查NOT_RUN。完整日志18446774B保留原失败归属；只把原同一ubuntu-latest job有界延长40→45分钟（增加5分钟），不新增job/runner/依赖/跳过或删除用例，不改变permissions/concurrency。约132s依赖安装+约37m Python已耗尽旧预算；新增分钟合同本地亚秒，不把超时伪称功能通过。新候选重跑原三CI/Mac安装，不rerun旧run，CI不调用实际供应商或模型。

原Mac40262625776安装与新模块字节校验通过、PC40262625754通过，只保留原0e4候选身份。产品Python/JS/CSS字节在预算修复中不变，旧浏览器/真实源证据可按blob映射复核；新候选的完整CI仍须真实重跑，常驻继续BLOCKED。
