import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { itemLink, readingLink } from '../../app/research_web/ui/aihot-common.mjs';
import { createAihotController, renderAihot } from '../../app/research_web/ui/aihot.mjs';
import { renderReadingTree, renderArticle, renderStory, renderTopic, articleMarkdown } from '../../app/research_web/ui/aihot-reading.mjs';

const id = '2f0270d6-fc22-4747-af7c-a4f488d3cd16';
const article = { id:'abc',title:'完整文章',source:{name:'来源'},body:{content:[{tag:'p',children:[{text:'正文内容'}]}],complete:true,zhKind:'translation'},outline:[{id:'sec-1',text:'目录',level:2}],relatedStories:[{publicId:id,title:'事件'}],topics:[{slug:'meta',name:'Meta'}],hasTranslation:true,bodyLanguage:'zh' };
test('article/story/topic routes validate identity and keep language and pagination',()=>{
 assert.equal(parseRoute('#/aihot/item/abc?lang=original').aihotId,'abc');
 assert.equal(parseRoute('#/aihot/item/abc?lang=original').aihotLanguage,'original');
 assert.equal(parseRoute(`#/aihot/story/${id}`).aihotTab,'story');
 assert.equal(parseRoute('#/aihot/topic/meta?page=2').aihotPage,2);
 assert.equal(parseRoute('#/aihot/item/a/b').aihotTab,'daily');
 assert.equal(parseRoute('#/aihot/item/%2fetc').aihotTab,'daily');
 assert.match(itemLink({itemId:'abc',title:'正文'}),/href="#\/aihot\/item\/abc"/);
 assert.match(readingLink('https://aihot.news/story/'+id,'事件'),/#\/aihot\/story\//);
});
test('reading tree never executes raw HTML or unsafe attributes',()=>{
 const html=renderReadingTree([{tag:'script',children:[{text:'evil'}]},{tag:'p',attrs:{onclick:'evil'},children:[{text:'<img onerror=evil>'}]},{tag:'a',attrs:{href:'javascript:evil'},children:[{text:'链接'}]}]);
 assert.doesNotMatch(html,/<script|onclick=|href="javascript:|<img/); assert.match(html,/&lt;img/);
});
test('article offers full body, translation, outline, metadata and local related reading',()=>{
 const html=renderArticle(article);for(const text of ['正文内容','完整文章','原文','目录','AI 翻译','#/aihot/story/','#/aihot/topic/meta','data-aihot-copy'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/target="_blank"[^>]*href="https:\/\/aihot.news\/(items|story|topics)/);
});
test('story filters/sorts all supplied reports and preserves complete overview',()=>{
 const story={publicId:id,title:'专题',digest:'全部综述',timeline:[{id:'one',title:'早',publishedAt:'2026-10-15',source:{name:'官方',firstParty:true}},{id:'two',title:'晚',publishedAt:'2026-10-16',source:{name:'媒体'},selected:true}],developments:[],officialReports:[],related:[],topics:[],heat:[],whyHot:{}};
 assert.match(renderStory(story,{filter:'official',order:'asc'}),/早/);assert.doesNotMatch(renderStory(story,{filter:'official',order:'asc'}),/>晚</);
 const html=renderStory(story,{filter:'all',order:'desc'});assert.ok(html.indexOf('>晚<')<html.indexOf('>早<'));assert.match(html,/全部综述/);
});
test('topic pagination and chronological context stay inside module',()=>{
 const html=renderTopic({topic:{slug:'meta',name:'Meta',definition:'定义'},items:[{id:'abc',title:'文章'}],page:2,pageCount:4,modules:{chronicle:{milestones:[{date:'2020',title:'成立'}]}}});
 for(const word of ['成立','#/aihot/item/abc','#/aihot/topic/meta?page=3','第 2 / 4 页'])assert.ok(html.includes(word),word);
});
test('controller handles original body, merge chains and late responses safely',async()=>{
 const calls=[];const controller=createAihotController({fetcher:async url=>{calls.push(url);return {ok:true,json:async()=>article};}});
 await controller.activate(parseRoute('#/aihot/item/abc?lang=original'));assert.match(calls[0],/items\/abc\/original$/);assert.match(renderAihot(controller.state),/完整文章/);
});
test('Markdown export retains body images, internal references and quoted text',()=>{
 const item={...article,body:{content:[{tag:'img',attrs:{src:'/api/research/aihot/media/'+'a'.repeat(64),alt:'关键图'}},{tag:'a',attrs:{href:'#/aihot/item/source'},children:[{text:'全文依据'}]}]},x:{quoted:{authorName:'作者',text:'关键引文'}}};
 const md=articleMarkdown(item);assert.match(md,/!\[关键图\]/);assert.match(md,/\[全文依据\]\([^)]*items\/source\)/);assert.match(md,/关键引文/);
});
test('late clipboard completion never mutates another page',async()=>{
 const oldNavigator=Object.getOwnPropertyDescriptor(globalThis,'navigator');let finish;
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:()=>new Promise(resolve=>{finish=resolve;})}}});
 try {
  const controller=createAihotController({fetcher:async url=>({ok:true,json:async()=>url.endsWith('hot')?{entries:[]}:article})});
  await controller.activate(parseRoute('#/aihot/item/abc'));const copying=controller.copy('markdown');
  await controller.activate(parseRoute('#/aihot/hot'));finish();await copying;assert.equal(controller.state.detail,null);
 } finally { if(oldNavigator)Object.defineProperty(globalThis,'navigator',oldNavigator);else delete globalThis.navigator; }
});
test('merged story chains remain local and fail on a cycle',async()=>{
 let calls=0;const controller=createAihotController({fetcher:async()=>({ok:true,json:async()=>{calls++;return {mergedInto:id};}})});
 await controller.activate(parseRoute(`#/aihot/story/${id}`));assert.match(controller.state.error,/合并链/);assert.equal(calls,1);
});
