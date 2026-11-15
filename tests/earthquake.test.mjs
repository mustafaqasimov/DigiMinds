import test from 'node:test';
import assert from 'node:assert/strict';
import {alarmLifetime,rememberEvent,normalizeRoom} from '../frontend/earthquake-state.js';
import {quakeMessages} from '../frontend/earthquake-i18n.js';
import {pulseSchedule} from '../frontend/earthquake-sound.js';

test('alarm duration uses server time, rejects stale or non-simulation messages, and is bounded',()=>{
 const event={simulated:true,expires_at:1030};
 assert.equal(alarmLifetime(event,1000),30000);
 assert.equal(alarmLifetime(event,1031),0);
 assert.equal(alarmLifetime({...event,cancelled:true},1000),0);
 assert.equal(alarmLifetime({...event,simulated:false},1000),0);
 assert.equal(alarmLifetime({...event,expires_at:Infinity},1000),0);
 assert.equal(alarmLifetime(event,undefined),0);
 assert.equal(alarmLifetime({...event,expires_at:1000000},1000),60000);
});
test('event history deduplicates and is bounded; room codes normalize consistently',()=>{
 assert.deepEqual(rememberEvent(['a','b'],'a'),['b','a']);
 assert.equal(rememberEvent(Array.from({length:50},(_,i)=>String(i)),'next').length,50);
 assert.equal(normalizeRoom(' digi26 '),'DIGI26');
});
test('all drill copy is translated in each supported language',()=>{
 for(const language of ['en','ru'])assert.deepEqual(Object.keys(quakeMessages[language]).sort(),Object.keys(quakeMessages.az).sort());
});
test('audible cue contains two separate short beeps per cycle and never exceeds duration',()=>{
 const pulses=pulseSchedule(2.4);
 assert.equal(pulses.length,4);
 assert.ok(pulses[1].start>pulses[0].end);
 assert.ok(pulses[2].start-pulses[1].end>.5);
 assert.ok(pulseSchedule(90).every(p=>p.start>=0&&p.end<=60&&p.start<p.end));
 assert.deepEqual(pulseSchedule(NaN),[]);
 assert.equal(pulseSchedule(.1)[0].end,.1);
});
