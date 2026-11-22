# FinGPT 供应商根 object 兼容性修复

宿主macOS/arm64，功能修复；本平台Native和GitHub macOS安装验收，Windows/Linux产品验证另行交接，未冒充通过。

真实失败记录来自本任务唯一Flash请求，session 2ef0a17e-ec14-487b-a128-c52a967403fa，约5.24秒，供应商拒绝research_run_script根schema type=null。无工具执行、无产物、usage不可得，不追加真实请求。

RED：固定DSH转换通过原union，但新增供应商根object断言失败。GREEN：参数恢复根object，code/report_plan互斥仍由执行边界在准入前拒绝；没有放宽研究质量门、计算声明绑定或预算。

测试扩展到实际固定DSH toPiContext、pi-ai normalizeContext和OpenAI请求序列化；fake fetch接收请求并返回本地SSE夹具，断言所有工具根object和schema完整保留。无新依赖、真实密钥、外部请求或模型探针。验证结果与最终SHA、CI另存任务私有回执；未执行项目不得称通过。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"仅调整原DSH工具参数根object与离线供应商序列化回归，原execute互斥、准入、沙箱、预算与Host质量链不变，无新增组件或研究循环。","diagrams":[]} -->
