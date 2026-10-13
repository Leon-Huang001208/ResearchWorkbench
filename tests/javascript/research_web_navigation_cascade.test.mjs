import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// Evaluate the actual compound-class grid rules and media conditions in source
// order. This catches a surviving older selector with greater specificity;
// browser geometry remains a separate integration check.
function gridCascade(css, classes, width) {
  const winning = new Map();
  let order = 0;
  function visit(source, active = true) {
    let cursor = 0;
    while (cursor < source.length) {
      const opening = source.indexOf('{', cursor); if (opening < 0) break;
      const header = source.slice(cursor, opening).trim();
      let depth = 1, closing = opening + 1;
      while (closing < source.length && depth) { if (source[closing] === '{') depth++; if (source[closing] === '}') depth--; closing++; }
      const body = source.slice(opening + 1, closing - 1); cursor = closing;
      if (header.startsWith('@media')) {
        const maximum = /max-width:\s*(\d+)px/.exec(header);
        const minimum = /min-width:\s*(\d+)px/.exec(header);
        visit(body, active && (!maximum || width <= Number(maximum[1])) && (!minimum || width >= Number(minimum[1])));
        continue;
      }
      order++;
      if (!active) continue;
      for (const selector of header.split(',').map(value => value.trim())) {
        if (!/^\.app-shell(?:\.[\w-]+)*$/.test(selector)) continue;
        const selected = selector.slice(1).split('.');
        if (!selected.every(name => classes.includes(name))) continue;
        for (const match of body.matchAll(/(grid-template-(?:areas|columns))\s*:\s*([^;]+);/g)) {
          const previous = winning.get(match[1]);
          if (!previous || selected.length > previous.specificity || selected.length === previous.specificity && order >= previous.order) {
            winning.set(match[1], {value:match[2].trim(),specificity:selected.length,order});
          }
        }
      }
    }
  }
  visit(css.replace(/\/\*[\s\S]*?\*\//g,''));
  return Object.fromEntries([...winning].map(([property,result])=>[property,result.value]));
}

test('actual navigation grid cascade covers desktop, collapsed, context and mobile states', async()=>{
  const css=await readFile(new URL('../../app/research_web/ui/appearance.css',import.meta.url),'utf8');
  for (const mode of ['', 'claw-shell']) {
    for (const secondary of ['', 'has-secondary']) {
      for (const context of ['', 'context-open']) {
        for (const collapsed of ['', 'sidebar-collapsed']) {
          const classes=['app-shell',mode,secondary,context,collapsed,...(!context?['wide-page']:[])].filter(Boolean);
          const desktop=gridCascade(css,classes,1280);
          assert.equal(desktop['grid-template-areas'],context?"'navigation top top' 'navigation main context'":"'navigation top' 'navigation main'",classes.join(' '));
          for (const width of [1050,390]) {
            const mobile=gridCascade(css,classes,width);
            assert.equal(mobile['grid-template-areas'],"'top' 'main'",`${width}: ${classes.join(' ')}`);
            assert.equal(mobile['grid-template-columns'],'minmax(0,1fr)',`${width}: ${classes.join(' ')}`);
          }
        }
      }
    }
  }
});
