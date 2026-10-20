import test from 'node:test';
import assert from 'node:assert/strict';
import { openComposerMenu } from '../../app/research_web/ui/composer-menu.mjs';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';
const models=[{provider:'first',models:[{id:'same',name:'First model'}]},{provider:'second',models:[{id:'same',name:'Second model'},{id:'other',name:'<script>unsafe</script>'}]}];
test('Claw model popup uses actual catalog, one provider-aware check and escaped names',()=>{
 const html=renderComposer({page:'claw',models,model:'same',modelProvider:'second',composerMenu:openComposerMenu('add','models')});
 assert.match(html,/composer-command-panel/); assert.equal((html.match(/aria-checked="true"/g)||[]).length,1);
 assert.match(html,/aria-checked="true"[^>]*>.*Second model/);
 assert.match(html,/&lt;script&gt;unsafe/); assert.doesNotMatch(html,/<script>/);
 assert.match(html,/id="model-select"/); assert.match(html,/data-cm-row=/);
});
test('stopping disables model choices and execution sessions keep their fixed model',()=>{
 const html=renderComposer({page:'claw',models,stopping:true,composerMenu:openComposerMenu('add','models')});
 assert.match(html,/data-cm-row=[^>]+disabled/);
 assert.doesNotMatch(renderComposer({page:'claw',models,detail:{execution_context:{definition_snapshot:{}}}}),/composer-model-menu/);
 assert.doesNotMatch(renderComposer({page:'fingpt',models}),/composer-model-menu/);
});
test('Claw uses one primary send-or-stop control with truthful transition states',()=>{
 const render=(extra={})=>renderComposer({page:'claw',models,...extra});
 const running=render({detail:{status:'running',can_cancel:true},taskPending:true});
 assert.equal((running.match(/data-cancel/g)||[]).length,1); assert.equal((running.match(/composer-send/g)||[]).length,1);
 assert.doesNotMatch(running,/<button type="submit"/); assert.match(running,/aria-label="停止生成"/); assert.doesNotMatch(running,/danger-outline/);
 const stopping=render({detail:{status:'running',can_cancel:true},stopping:true});
 assert.match(stopping,/data-cancel[^>]*aria-busy="true"[^>]*disabled/); assert.match(stopping,/composer-button-spinner/);
 const acknowledged=render({detail:{status:'cancelling',can_cancel:true}}); assert.match(acknowledged,/aria-busy="true"[^>]*disabled/);
 const unknown=render({detail:{status:'idle',can_recheck_stop:true}}); assert.match(unknown,/aria-label="重新核对停止"/);
 const offline=render({detail:{status:'running'},runtimeReady:false}); assert.match(offline,/data-cancel[^>]*disabled/);
 const completed=render({detail:{status:'completed'}}); assert.doesNotMatch(completed,/data-cancel/); assert.match(completed,/<button type="submit"/);
 assert.match(render({busy:true}),/composer-button-spinner/);
});
