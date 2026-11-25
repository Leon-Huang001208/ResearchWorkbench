## 要完成什么

选择适合研究任务的 Skill，先核对它的输入、版本和依赖，再开始执行。技能目录可发现，不代表该技能已启用或它依赖的数据已可用。

## 前置条件

- 已登录正确的 RWB 账号。
- 执行任务前，确认技能状态为 enabled，并查看 readiness 与所需资料。
- 使用模型、专业来源或文件工具时，另需对应配置与授权。

## 最小可运行示例

在 Research Web 主界面的开发者工具 Console 中查看技能目录：

```javascript
const response = await fetch("/api/research/capabilities?kind=skill");
if (!response.ok) throw new Error("HTTP " + response.status);
const result = await response.json();
console.table(result.items.map(item => ({
  id: item.id, name: item.name, status: item.status
})));
```

选一项返回的 id 查看详情，不要自行编造技能标识：

```javascript
const selected = result.items.find(item => item.status === "enabled");
if (!selected) throw new Error("当前没有已启用技能，请先查看依赖与配置");
const detailResponse = await fetch(
  "/api/research/capabilities/" + encodeURIComponent(selected.id)
);
if (!detailResponse.ok) throw new Error("HTTP " + detailResponse.status);
const detail = await detailResponse.json();
console.log(detail);
```

## 使用路径

1. 在能力中心查看该技能的说明、当前版本、输入、检查结果和依赖。
2. 例如完整公司研究应选择公司研究方法；单一公告事件不应被写成全面公司研究。
3. 在研究会话中给出对象、时间范围、已有资料和明确的任务；让运行环境发现并使用相应技能。
4. 确认需要的模型和数据操作后执行。检查实际使用的技能、来源和交付结果。

示例任务：

> 使用适合公司研究的已启用技能，分析我提供的资料。先列明还缺哪些财务与估值证据，不补齐未取得的数据；只在我要求时生成文件。

这条任务说明研究目标，不保证任意实例都已配置公司研究所需的数据。

## 预期结果

目录返回 items；详情中可检查 draft、checks、版本与 readiness。真正执行后的输出可能是聊天回答或已声明的文件，取决于该技能版本和当前工具环境。

## 常见错误

- draft / invalid / blocked_dependencies / disabled：先解决对应状态，不绕过启用条件。
- 内置技能需要修改：复制后编辑与发布，不覆盖内置版本。
- 没有文件：检查技能的输出约定和当前可用工具，不能只依据请求文字判断已生成。

## 相关参考

- [Skill 参考与开发入口](../../../outputs/research-web-architecture/reference-skills.html)
- [API：能力中心](../../../outputs/research-web-architecture/reference-api-capabilities.html)
- [数据依赖与权限](../../../outputs/research-web-architecture/reference-data.html)
