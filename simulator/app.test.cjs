const test = require('node:test');
const assert = require('node:assert/strict');
const {frameIndex,outcomeText,reviewMatches} = require('./app.js');
test('replay uses only windows already completed on the clock',()=>{
  const frames=[{t_ms:64},{t_ms:128},{t_ms:192}];
  assert.equal(frameIndex(frames,0),-1);assert.equal(frameIndex(frames,63.99),-1);
  assert.equal(frameIndex(frames,64),0);assert.equal(frameIndex(frames,127.99),0);
  assert.equal(frameIndex(frames,192),2);assert.equal(frameIndex(frames,300),2);assert.equal(frameIndex([],10),-1);
});
test('general warnings and misses are not reported as correct direction',()=>{
  assert.equal(outcomeText({critical:true,detected:false}),'No accepted warning');
  assert.equal(outcomeText({critical:true,detected:true,nondirectional:true}),'General warning');
  assert.equal(outcomeText({critical:true,detected:true,wrong_direction:true}),'Wrong direction');
  assert.equal(outcomeText({critical:false,false_alerts:1}),'Unexpected alert');
});
test('review checks require the intended warning behavior rather than a low error rate',()=>{
  assert.equal(reviewMatches('dropout',{deda:{detected:true,nondirectional:true,first_alert:{motors:15}}}),true);
  assert.equal(reviewMatches('horn',{deda:{detected:true,nondirectional:true,correct_class:true}}),false);
  assert.equal(reviewMatches('ambient',{deda:{critical:false},alerts:[{}]}),false);
  assert.equal(reviewMatches('weak',{deda:{critical:true,detected:false},alerts:[]}),true);
});
