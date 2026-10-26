import test from 'node:test';
import assert from 'node:assert/strict';
import {intradayOption} from '../../app/research_web/ui/asset-intraday-option.mjs';

const input = {asset:'603986.SH',trading_date:'2026-10-23',previous_close:10,rows:[
  {time:'09:31',price:10,mean:null,volume_shares:0,volume_lots:0,amount:0},
  {time:'09:32',price:10,mean:10,volume_shares:100,volume_lots:1,amount:1000},
]};

test('intraday preserves minute labels, zeros and missing mean; shared time axis only at bottom',()=>{
  const option=intradayOption(input);
  assert.equal(option.xAxis[0].data.length,241);
  assert.deepEqual(option.xAxis[0].data.slice(0,3),['09:25','09:31','09:32']);
  assert.equal(option.xAxis[0].axisLabel.show,false);
  assert.equal(option.xAxis[1].axisLabel.interval(0,'09:25'),true);
  assert.equal(option.xAxis[1].axisLabel.interval(240,'15:00'),true);
  assert.deepEqual(option.series[1].data.slice(0,3),[null,null,10]);
  assert.equal(option.series[2].data[1].value,0);
  assert.equal(option.series[2].data[2].value,1);
  assert.equal(option.series[2].data[240],null);
  assert.ok(option.yAxis[0].max>10 && option.yAxis[0].min<10);
  assert.equal(option.series[0].markLine.data[0].yAxis,10);
});

test('flat prices retain finite symmetric price and percent axes in both themes',()=>{
  for(const dark of [true,false]){
    const option=intradayOption(input,{dark});
    assert.equal(option.backgroundColor,'transparent');
    assert.equal(option.yAxis[1].min,-option.yAxis[1].max);
    assert.ok(Number.isFinite(option.yAxis[0].min));
  }
});

test('hover emits selected minute readout and escapes supplied date/time',()=>{
  let selected;
  const option=intradayOption({...input,trading_date:'<unsafe>'},{updateReadout:i=>selected=i});
  const text=option.tooltip.formatter([{dataIndex:2}]);
  assert.equal(selected,1);
  assert.ok(text.includes('&lt;unsafe&gt;'));
  assert.ok(text.includes('09:32'));
});
