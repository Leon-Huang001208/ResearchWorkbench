(function(){
  'use strict'; const app=window.AlphaPrototype;
  const journeys={
    J01:{name:'发现到研究沉淀',steps:['/market-home','/themes?pack=gold','/assets/AU-DEMO','/fingpt?view=result','/research-library?tab=notes']},
    J02:{name:'事件验证',steps:['/market-home?focus=events','/assets/AU-DEMO?tab=events','/fingpt?view=result','/research-library?tab=claims']},
    J03:{name:'观察到提醒',steps:['/assets/AU-DEMO','/watchlists?action=add','/watchlists?action=create-rule','/watchlists?tab=inbox']},
    J04:{name:'Claw 多 Agent 任务',steps:['/claw?action=new','/claw?view=run','/claw?view=blackboard','/research-library?tab=artifacts']},
    J05:{name:'运行时阻塞与恢复',steps:['/capabilities?tab=schedules','/claw?state=blocked_runtime','/capabilities?tab=runtimes','/claw?state=running']},
  };
  function start(id){if(!journeys[id])return;app.setState({activeJourneyId:id,journeyStep:0});app.router.navigate(journeys[id].steps[0]);}
  function go(delta){const id=app.state.activeJourneyId;if(!id)return;const journey=journeys[id];const next=Math.max(0,Math.min(journey.steps.length-1,app.state.journeyStep+delta));app.setState({journeyStep:next});app.router.navigate(journey.steps[next]);}
  function exit(){app.setState({activeJourneyId:null,journeyStep:0});render();}
  function render(){const root=document.querySelector('#journey-bar');if(!root)return;const id=app.state.activeJourneyId;if(!id){root.innerHTML='';return;}const journey=journeys[id];const step=app.state.journeyStep;root.innerHTML=`<div class="journey-panel"><strong>${id}</strong><span class="journey-label">${journey.name} · ${step+1}/${journey.steps.length}</span><button class="button small" data-journey="prev" ${step===0?'disabled':''}>上一步</button><button class="button small" data-journey="next" ${step===journey.steps.length-1?'disabled':''}>下一步</button><button class="button small" data-journey="exit">退出</button></div>`;}
  document.addEventListener('click',(event)=>{const id=event.target.closest('[data-start-journey]')?.dataset.startJourney;if(id)start(id);const action=event.target.closest('[data-journey]')?.dataset.journey;if(action==='prev')go(-1);if(action==='next')go(1);if(action==='exit')exit();});
  window.AlphaJourneys={journeys,start,render}; app.subscribe(render);
})();
