# Native stop port release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development task-by-task, with spec then Python quality review.

**Goal:** 完成本次可信 Native stop 后最多45秒的端口释放等待，保留最终安全检查。

**Architecture:** 在原 switch_runtime 的公开 stop 成功与 final scope/lease 建立之间使用既有普通 bind 观察等待。本次捕获原端口、deadline和耗时只在调用内保留；无新权限、OS解析器或框架。

**Tech Stack:** 已有 stdlib Python、pytest、Node planner/receipt，macOS Web。

---

## Task 1: 最小修复与回归

**Files:**
- Modify: `research_workbench_entrypoint/bootstrap.py`
- Test: `tests/research_web/test_runtime_mode.py`, `tests/research_web/test_docker_runtime.py`
- Modify: `docs/research-web-installation.md` 与 policy 要求的直接模块文档
- Create: `.ai/reports/2026-10-07-native-stop-port-release.md`

- [ ] 在既有 fixture 中建立真实 NativeRuntime 类型的控制器与真实临时 bound socket。
  模式为Native，初始状态通过原 Native bridge/fixture，stop明确成功；释放线程晚于stop。
  在最终写 mode 前断言既有 port_busy 对原端口均 false，模式仅按原 CAS 改为Docker。
  增加持续 bound 超时、invalid timeout、stop失败、未知状态、外部默认端口与并发CAS负面断言。
- [ ] 执行 RED：`PYTHONPATH=. <既有venv>/bin/python -m pytest --confcutdir=tests/research_web tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py -k stop_port_release -q`。
  预期因缺少等待而失败；保留日志，非环境失败不能当 RED。
- [ ] 最小实现：import math/time；默认 wait_timeout=45；仅在本次可信 NativeRuntime 停止分支中验证预算并捕获 `tuple(native.ports)`。
  成功 stop 后、finalize 定义／调用前执行以下逻辑，不改 final checks：

```python
deadline = time.monotonic() + wait_timeout
while any(port_busy(port) for port in stopped_native_ports):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ControlError("runtime_stop_failed")
    time.sleep(min(0.1, remaining))
```

  stop前预算验证使用 `type(value) in (int,float)`、`math.isfinite(value)`、`0<=value<=45`；
  非法输入使用既有 runtime_stop_failed，不部分停止后才抛输入错误。
  输出既有 logger 的固定 wait begin／released／timeout 分类，不输出路径、PID、认证或原 report。
- [ ] 同条目标命令 GREEN；执行 planner 当前所选完整 runtime-mode 门：
  `PYTHONPATH=. <既有venv>/bin/python -m pytest tests/research_web/test_runtime_mode.py tests/research_web/test_docker_runtime.py --confcutdir=tests/research_web -q`。
- [ ] 更新安装说明的可观察等待／超时语义与必要模块文档；不改依赖、CLI参数、policy、CI或平台矩阵。
  用原 planner 完整 changed set、unexpected_behavior 信号，执行必需本地门与 receipt validator；保留CI NOT_RUN。
- [ ] 自审、冻结生产／测试哈希并本地提交；由主会话安排独立spec后quality审查。

## Task 2: 主任务真实 macOS 验收及收尾

- [ ] 审查无未解决Important/Critical问题后，将干净任务测试checkout顺序更新到该source，不强制覆盖。
- [ ] 同一HOME公开 `rwb web start --no-open`；真实活跃 `rwb runtime use docker --stop-current`；记录实际等待与最终mode。
- [ ] 原accepted Docker公开start/Doctor，检查原fixture/control RAM/合成凭据；再活跃切Native并检查同一fixture/control。
- [ ] 正常删除合成凭据、停止本次实例、检查测试端口释放及日常实例未变；保留数据、旧state/container/image。
- [ ] 完整branch相对集成／原goal基线重规划，逐门记录新执行、仍适用的明确source-affinity复用、未执行项。
- [ ] 本地完成后再处理managed integration与macOS CI所需预算／当前visibility和独立远端授权，不自动push/dispatch/merge。
