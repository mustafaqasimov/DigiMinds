import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {AlarmSound,ALARM_AUDIO_URL} from '../frontend/earthquake-sound.js';

function audioHarness(t){
 const sources=[],gains=[];
 class AudioContext {
  state='suspended';currentTime=10;destination={};
  async resume(){this.state='running';}
  async decodeAudioData(){return {duration:12};}
  createGain(){
   const events=[];
   const gain={events,gain:{setValueAtTime:(...args)=>events.push(args),linearRampToValueAtTime:(...args)=>events.push(args)},connect(){},disconnect(){this.disconnected=true;}};
   gains.push(gain);return gain;
  }
  source(kind){
   const source={kind,frequency:{},stops:[],connect(){},disconnect(){this.disconnected=true;},start(at){this.started=at;},stop(at){this.stops.push(at);}};
   sources.push(source);return source;
  }
  createBufferSource(){return this.source('recording');}
  createOscillator(){return this.source('fallback');}
 }
 const old=Object.getOwnPropertyDescriptor(globalThis,'AudioContext');
 Object.defineProperty(globalThis,'AudioContext',{configurable:true,writable:true,value:AudioContext});
 t.after(()=>{if(old)Object.defineProperty(globalThis,'AudioContext',old);else delete globalThis.AudioContext;});
 const fetch=t.mock.method(globalThis,'fetch',async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(8)}));
 return {sources,gains,fetch};
}

test('recorded siren loops for each alarm duration, previews quietly and stops immediately',async t=>{
 const h=audioHarness(t),sound=new AlarmSound();
 assert.equal(sound.play(30),false);
 assert.equal(await sound.unlock(),true);
 assert.equal(h.fetch.mock.calls[0].arguments[0],ALARM_AUDIO_URL);
 for(const duration of [15,30,60]){
  assert.equal(sound.play(duration),true);
  const source=h.sources.at(-1);
  assert.equal(source.kind,'recording');assert.equal(source.loop,true);
  assert.equal(source.stops[0]-source.started,duration);
  sound.stop();assert.equal(source.stops.at(-1),undefined);assert.ok(source.disconnected);
 }
 sound.play(2,true);const preview=h.gains.at(-1).events.map(e=>e[0]);
 sound.play(30);const alarm=h.gains.at(-1).events.map(e=>e[0]);
 assert.ok(Math.max(...preview)<Math.max(...alarm));
 await sound.unlock();assert.equal(h.fetch.mock.callCount(),1);
});

test('muting and restarting cannot leave an old loop playing or lose the new stop handle',async t=>{
 const h=audioHarness(t),sound=new AlarmSound();await sound.unlock();
 sound.play(60);const old=h.sources.at(-1);
 sound.stop();sound.play(15);const current=h.sources.at(-1);
 old.onended();assert.equal(sound.nodes[0],current);
 sound.stop();assert.ok(current.disconnected);
 current.onended();assert.equal(sound.nodes.length,0);
});

test('failed/corrupt audio keeps a bounded fallback and a later click retries the recording',async t=>{
 const h=audioHarness(t),sound=new AlarmSound();
 h.fetch.mock.mockImplementationOnce(async()=>{throw Error('offline');});
 assert.equal(await sound.unlock(),true);sound.play(15);
 assert.equal(h.sources.at(-1).kind,'fallback');
 assert.equal(h.sources.at(-1).stops[0]-h.sources.at(-1).started,15);
 sound.context.decodeAudioData=async()=>{throw Error('corrupt MP3');};
 assert.equal(await sound.unlock(),true);assert.equal(sound.buffer,null);
 sound.context.decodeAudioData=async()=>({duration:12});
 await sound.unlock();sound.play(30);
 assert.equal(h.sources.at(-1).kind,'recording');
 assert.equal(h.fetch.mock.callCount(),3);
});

test('invalid lengths and suspended audio never report playback; duration is capped',async t=>{
 const h=audioHarness(t),sound=new AlarmSound();await sound.unlock();
 for(const duration of [NaN,Infinity,-1,0])assert.equal(sound.play(duration),false);
 assert.equal(h.sources.length,0);
 sound.play(90);assert.equal(h.sources.at(-1).stops[0]-h.sources.at(-1).started,60);
 sound.context.state='suspended';assert.equal(sound.play(15),false);
});

test('autoplay rejection does not fetch or claim readiness',async t=>{
 const h=audioHarness(t),sound=new AlarmSound();
 sound.context=new AudioContext();sound.context.resume=async()=>{throw Error('NotAllowedError');};
 assert.equal(await sound.unlock(),false);assert.equal(sound.play(15),false);
 assert.equal(h.fetch.mock.callCount(),0);
});

test('offline shell bundles the same audio resource as the player',()=>{
 const bytes=fs.readFileSync(new URL(ALARM_AUDIO_URL));
 assert.ok(bytes.length>1000&&bytes.length<250000);
 assert.equal(bytes.subarray(0,3).toString(),'ID3');
 const worker=fs.readFileSync(new URL('../frontend/sw.js',import.meta.url),'utf8');
 assert.ok(worker.includes("'/audio/sos-alarm.mp3'"));
});
