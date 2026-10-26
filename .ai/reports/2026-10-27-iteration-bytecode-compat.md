# 再生字节码编码兼容修复

- 宿主：macOS；任务类型：既有资源收尾功能缺陷修复。验收范围为本机 Python 3.12 离线合同；Ubuntu 系统 Python 的最终 CI 由主控制任务重新绑定。无安装、push、部署或其他平台产品操作。
- 起点：PR243 集成候选 `8f5288ca76e12f5db0056320ef2608c10c2bca9d`。Project Constraints run `40384650499` 的资源模块15项通过，再生模块4项出现1 ERROR/1 FAIL，均先遭 `closeout_regenerated_bytecode_unknown`。全日志只确认 ubuntu-26.04、使用系统 `python3`；没有 Python 版本输出，不能认证实际为3.14。
- 本机原四项全部通过。Python3.12实验确认同一语义的可信 code 在 inline/stored 引用上下文下 marshal 首字节为 `63`/`e3`、字节不同而加载对象等价。CPython标准库的 py_compile 经 `_code_to_timestamp_pyc` 保持额外 code 引用；此机制支持调用上下文差异假设，但未捕获原 CI payload，不能宣称已确证该 CI 根因。
- 修复：只对可信重编译 code 使用 py_compile 同路标准库编码器生成预期 payload，仍与原缓存逐字节比较；编码器不可用时日志记录并拒绝。不加载不可信 marshal、不执行缓存、不改变源文件/头部/大小/路径/清单与未知文件拒绝门。
- 测试保留真实 py_compile 正例、伪造字节负例、未知文件竞态；新增编码器不可用拒绝，以及真实 py_compile 的另一源码 payload（相同 dfile）与尾随业务数据保留。未使用自造 canonical pyc 代替真实正例。

## 实际验证及证据

解释器：`/Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python`（3.12.13），没有安装任何依赖。

- `python -m unittest discover -s tests/research_web -p 'test_iteration_regeneration.py' -v`：RED 为新增编码器缺失负例未抛 ResourceError（5项中1 FAIL）；修改后6项全部通过。
- `python -m unittest discover -s tests/research_web -p 'test_iteration_resources.py' -v`：15项通过。
- 原始日志：`logs/seek-parity-ci-40384650499-full.log`、`logs/seek-parity-ci-40384650499-regeneration-failed.log`。
- 本机日志：`logs/seek-parity-regeneration-baseline-312.log`、`logs/seek-parity-regeneration-red.log`、`logs/seek-parity-regeneration-green.log`、`logs/seek-parity-regeneration-adjacent.log`、`logs/seek-parity-marshal-reference-variants.log`。
- 初次使用上述 venv 运行 black/isort/ruff 时模块缺失，未安装；随后使用既有 uv 缓存中的 black/isort 及 ruff binary，两个改动 Python 文件的 black/isort/ruff 检查全部通过，black未改字节。
- `node --test tests/javascript/iteration_closeout.test.mjs`：3项通过（`logs/seek-parity-regeneration-closeout-node.log`）。`node scripts/check_documentation_governance.mjs --project .`：零违规（`logs/seek-parity-regeneration-doc-governance.log`）。
- 另尝试 `python -m pytest` 时该 venv 缺 pytest，未安装；因此 pytest 未执行，不能宣称通过。原 CI 使用的 unittest 两模块已实际通过21项。

## 未完成项与风险

本机未发现可用 Python3.14，故该版本本地 NOT_RUN；原 CI 没有版本和 payload 诊断，具体失败机制保持假设。最终 Router、独立 SPEC/QUALITY 评审、原三CI及同候选Mac安装由主控制任务继续执行；此报告不把本机通过改写为 Ubuntu、跨平台或常驻验证。使用 CPython 私有标准库编码器是有界兼容依赖，缺失时明确拒绝，不回退到弱校验。

官方机制参考：[CPython py_compile](https://github.com/python/cpython/blob/3.14/Lib/py_compile.py)、[标准编码器](https://github.com/python/cpython/blob/3.14/Lib/importlib/_bootstrap_external.py)、[marshal 引用标记](https://github.com/python/cpython/blob/3.14/Python/marshal.c)。
