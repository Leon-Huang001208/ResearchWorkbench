import { escapeHTML as e } from './markdown.mjs';

// Product explanations of existing methods. They grant no tools or source access.
export const dossierMethods = Object.freeze([
  { action: 'company', title: '公司研究', skills: ['company-research'], inputs: '规范证券身份、期间、业务与财务资料、现有观点和反证', outputs: '业务与财务判断、可比基线、风险、证据缺口、下一验证', rule: '没有来源的数字不补造；沿用原报告质量核验。' },
  { action: 'industry', title: '行业研究', skills: ['industry-research', 'industry-chain-research', 'industry-prosperity'], inputs: '行业或主题边界、分类代码、时间范围、可定位的供需与关系证据', outputs: '供需与竞争格局、产业交叉证据、关系出处、待核查指标', rule: '产业关系必须有来源定位；财务数据不足时省略量化判断。' },
  { action: 'research_prep', title: '调研准备', skills: ['company-research'], inputs: '研究对象、已知事实、历史观点、催化剂与待核验问题', outputs: '调研问题清单、每题依据、反向问题、所需材料与验证节点', rule: '把事实、假设和待问问题分开；不虚构已完成访谈。' },
  { action: 'update_view', title: '研报增量与观点修订', skills: ['sell-side-report-reader'], inputs: '可读取的完整研报、可核验旧基线、首次公开时点与截止日期', outputs: '本篇新增、相对基线变化、证据与反证、观点修订候选', rule: '摘要不当原文；没有历史基线时不宣称市场新增。' },
  { action: 'check_risk', title: '风险检查', skills: ['company-research', 'earnings-report-monitor'], inputs: '关注对象、公告与财务证据、观察窗口、既有风险及解除依据', outputs: '风险事实、触发条件、覆盖缺口、验证或解除所需证据', rule: '无信号与资料缺失分开；不会自动解除风险或改写观点。' },
  { action: 'earnings_gap', title: '预期差观察', skills: ['earnings-consensus-research', 'earnings-preview-monitor'], inputs: '证券身份、报告期、披露时点、披露前预期版本与样本口径', outputs: '实际与预期差、指引变化、机构分歧、来源和验证节点', rule: '缺可靠一致预期时标记无法判断，不用事后数据补作历史预期。' },
]);
export const dossierActions = dossierMethods.map(method => [method.action, method.title]);
export function renderDossierMethodGuide({ action, capabilityID } = {}) {
  const methods = dossierMethods.filter(method => action ? method.action === action : method.skills.includes(capabilityID));
  if (!methods.length) return '';
  return `<section class="dossier-method-guide"><h3>档案研究方法</h3>${methods.map(method => `<details><summary>${e(method.title)} · 方法与成果要求</summary><p><strong>输入：</strong>${e(method.inputs)}</p><p><strong>输出结构：</strong>${e(method.outputs)}</p><p class="muted small">${e(method.rule)}</p></details>`).join('')}<p class="muted small">使用当前能力的已发布版本，版本内容与变更从原“查看版本”入口核对。研究结果先经原质量链，再预览归入档案。</p><a href="#/assets?view=dossiers">进入长期研究档案</a></section>`;
}
