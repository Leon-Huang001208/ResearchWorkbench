# AI 问答前端

问答组件从 AlphaDesk 的固定提交 `1c946b9a0930d3070da7263ffcffe5e8831077c3` 迁入 RWB。迁移范围已获用户授权提交至公开仓库。

| 上游文件 | RWB 适配 |
| --- | --- |
| `src/pages/Chat.tsx` | 保留三种模式、问答消息和参考面板，使用 Host 会话投影和 RWB 输入区。 |
| `src/components/chat/AiAnswer.tsx` | 保留回答、研究拆解、执行步骤和引用标记，正式文件由 Host 报告接口交付。 |
| `src/components/chat/AiWorkspace.tsx` | 保留按来源和笔记分组及引用联动，只展示实际登记的来源和工作笔记。 |
| `src/lib/aiStream.ts` | 保留事件归并，使用 RWB 持久会话快照分轮投影。 |
| `src/lib/aiLabels.ts`、`src/lib/useStickyBottom.ts` | 复用模式文案与跟随滚动。 |

源码位于静态目录外。独立 Node 24 构建产出 `qa.js`、`qa.css` 与第三方许可清单。运行时同源懒加载。RWB 输入区负责草稿、幂等提交、附件和报告选项。
