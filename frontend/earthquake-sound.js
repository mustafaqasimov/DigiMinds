// Bundled audio works on the local network and through the offline shell.
export const ALARM_AUDIO_URL=new URL('./audio/sos-alarm.mp3',import.meta.url).href;

export class AlarmSound {
 constructor(){this.context=null;this.buffer=null;this.loading=null;this.nodes=[];}
 async unlock(){
  try{
   const Audio=globalThis.AudioContext||globalThis.webkitAudioContext;
   if(!Audio)return false;
   this.context??=new Audio();
   // Resume during the user's click, before any network/decode await.
   await this.context.resume();
   if(!this.ready)return false;
   await this.load();
   return this.ready;
  }catch{return false;}
 }
 async load(){
  if(this.buffer)return;
  if(this.loading)return this.loading;
  this.loading=(async()=>{
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),3500);
   try{
    const response=await fetch(ALARM_AUDIO_URL,{signal:controller.signal});
    if(!response.ok)throw Error('Alarm audio unavailable');
    const buffer=await this.context.decodeAudioData(await response.arrayBuffer());
    if(!Number.isFinite(buffer.duration)||buffer.duration<=0)throw Error('Invalid alarm audio');
    this.buffer=buffer;
   }catch{
    // Missing/corrupt audio must not disable emergency demo sound.
    // A later user click retries the file; the existing tone remains available.
   }finally{clearTimeout(timer);}
  })();
  try{await this.loading;}finally{this.loading=null;}
 }
 get ready(){return this.context?.state==='running';}
 stop(){
  const nodes=this.nodes;this.nodes=[];
  for(const node of nodes){try{node.stop();}catch{}try{node.disconnect();}catch{}}
  try{globalThis.navigator?.vibrate?.(0);}catch{}
 }
 play(seconds=30,preview=false){
  this.stop();
  const duration=Number.isFinite(seconds)?Math.max(0,Math.min(60,seconds)):0;
  if(!this.ready||!duration)return false;
  const ctx=this.context,start=ctx.currentTime,end=start+duration;
  let source,gain;
  try{
   gain=ctx.createGain();
   gain.gain.setValueAtTime(0,start);
   if(this.buffer){
    source=ctx.createBufferSource();source.buffer=this.buffer;source.loop=true;
    const fade=Math.min(.02,duration/3),volume=preview ? .15 : .5;
    gain.gain.linearRampToValueAtTime(volume,start+fade);
    gain.gain.setValueAtTime(volume,end-fade);
    gain.gain.linearRampToValueAtTime(0,end);
   }else{
    source=ctx.createOscillator();source.type='sine';source.frequency.value=880;
    for(const pulse of pulseSchedule(duration)){
     const at=start+pulse.start,until=start+pulse.end,fade=Math.min(.012,(until-at)/3);
     gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(preview ? .055 : .16,at+fade);
     gain.gain.setValueAtTime(preview ? .055 : .16,until-fade);gain.gain.linearRampToValueAtTime(0,until);
    }
   }
   source.connect(gain);gain.connect(ctx.destination);
   this.nodes=[source,gain];
   source.onended=()=>{
    source.disconnect();gain.disconnect();
    // An old source ending must not clear a newer alarm's stop handles.
    if(this.nodes[0]===source)this.nodes=[];
   };
   source.start(start);source.stop(end);
   if(!preview)try{globalThis.navigator?.vibrate?.([300,150,300,150,300]);}catch{}
   return true;
  }catch{
   try{source?.stop();}catch{}
   try{source?.disconnect();gain?.disconnect();}catch{}
   this.nodes=[];return false;
  }
 }
}

// Paired short beeps are only a fallback if the bundled siren cannot load.
export function pulseSchedule(seconds){
 const end=Math.max(0,Math.min(60,Number.isFinite(seconds)?seconds:0)),pulses=[];
 for(let cycle=0;cycle<end;cycle+=1.2){
  for(const offset of [0,.3]){const start=cycle+offset;if(start<end)pulses.push({start,end:Math.min(end,start+.18)});}
 }
 return pulses;
}
