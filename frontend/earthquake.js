import {quakeMessages} from './earthquake-i18n.js';
import {alarmLifetime,rememberEvent,normalizeRoom} from './earthquake-state.js';
import {loadFeatureStyle} from './ui-assets.js';
import {pulseSchedule} from './earthquake-sound.js';

const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const glyph=`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M3 16V9a9 9 0 0 1 18 0v7M1 16h6v5H1zM17 16h6v5h-6zM8 12h2l2-5 2 10 2-5h2"/></svg>`;

class AlarmSound {
 constructor(){this.context=null;this.nodes=[];}
 async unlock(){
  const Audio=window.AudioContext||window.webkitAudioContext;
  if(!Audio)return false;
  this.context??=new Audio();
  try{await this.context.resume();return this.ready;}catch{return false;}
 }
 get ready(){return this.context?.state==='running';}
 stop(){for(const node of this.nodes){try{node.stop();}catch{}try{node.disconnect();}catch{}}this.nodes=[];try{navigator.vibrate?.(0);}catch{}}
 play(seconds=30,preview=false){
  this.stop();if(!this.ready)return false;
  const ctx=this.context,start=ctx.currentTime,end=start+Math.min(60,seconds);
  if(end<=start)return false;
  const gain=ctx.createGain();gain.gain.setValueAtTime(0,start);
  for(const pulse of pulseSchedule(end-start)){
   const at=start+pulse.start,until=start+pulse.end,fade=Math.min(.012,(until-at)/3);
   gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(preview ? .055 : .16,at+fade);
   gain.gain.setValueAtTime(preview ? .055 : .16,until-fade);gain.gain.linearRampToValueAtTime(0,until);
  }
  const osc=ctx.createOscillator();osc.type='sine';osc.frequency.value=880;
  osc.connect(gain);gain.connect(ctx.destination);osc.start();osc.stop(end);
  osc.onended=()=>{gain.disconnect();osc.disconnect();};this.nodes=[osc,gain];
  if(!preview)try{navigator.vibrate?.([300,150,300,150,300]);}catch{}
  return true;
 }
}

export function createEarthquakeDemo({api,onSOS,beforeOpen,initialRoom='DIGI26',initialLabel='',onStatus=()=>{}}) {
 loadFeatureStyle('./product-theme.css');
 loadFeatureStyle('./earthquake.css');
 let ctx={user:null,enabled:false,lang:'az'},member=null,socket=null,retryAt=0,lastPacket=0,lastBeat=0,busy=false,ticking=false;
 let active=null,deadline=0,alarmTimer=null,muted=false,playing=false,status=null,room=initialRoom,draftKey=null,packet=null;
 let seen=[];try{seen=JSON.parse(sessionStorage.getItem('dm_quake_seen')||'[]');if(!Array.isArray(seen))seen=[];}catch{}
 // A fresh id for each page avoids treating duplicated tabs as one physical device.
 let deviceId=makeId();
 const sound=new AlarmSound();
 const root=document.createElement('section');root.id='earthquake-root';
 root.innerHTML='<dialog id="quake-control" aria-labelledby="quake-heading"></dialog><dialog id="quake-alert" aria-labelledby="quake-alert-heading" aria-describedby="quake-alert-description"></dialog>';
 document.body.append(root);
 const control=root.querySelector('#quake-control'),alert=root.querySelector('#quake-alert');
 const t=key=>(quakeMessages[ctx.lang]||quakeMessages.az)[key];
 const operator=()=>ctx.user?.permissions?.includes('demo:write');
 const error=err=>{const node=control.querySelector('#quake-error');if(node)node.textContent=t(err.message==='drill_already_active'?'activeError':err.status===429||err.status===503?'capacityError':err.status===401||err.message==='device_not_found'?'joinError':'error');};
 function makeId(){if(crypto.randomUUID)return crypto.randomUUID();const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const h=[...bytes].map(x=>x.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;}
 function closeSocket(){if(socket){socket.onclose=null;socket.close();socket=null;}}
 function stopAlarm(){clearTimeout(alarmTimer);alarmTimer=null;sound.stop();playing=false;}
 function finish(){stopAlarm();active=null;deadline=0;alert.close();refreshIndicators();}
 async function receipt(kind){const event=active;if(!member||!event)return;try{await api(`/drills/earthquake/${event.id}/receipts`,{method:'POST',body:JSON.stringify({device_id:deviceId,status:kind})});}catch{/* Metrics must never prevent muting. */}}
 function mute(){stopAlarm();muted=true;void receipt('muted');refreshAlert();}
 function showAlert(event,lifetime){
  stopAlarm();active=event;deadline=performance.now()+lifetime;
  muted=seen.includes(event.id);seen=rememberEvent(seen,event.id);
  try{sessionStorage.setItem('dm_quake_seen',JSON.stringify(seen));}catch{}
  if(!muted){playing=sound.play(lifetime/1000);if(playing)void receipt('audio_started');}
  void receipt('received');
  beforeOpen();control.close();renderAlert();alert.showModal();
  // The audio graph and this local timer both stop without a server connection.
  alarmTimer=setTimeout(finish,lifetime);
 }
 function consume(next){
  if(!member||next.room!==member.room)return;
  lastPacket=Date.now();packet=next;
  const lifetime=alarmLifetime(next.event,next.server_time);
  if(!lifetime){if(active)finish();}
  else if(next.event.id!==active?.id)showAlert(next.event,lifetime);
  else deadline=Math.min(deadline,performance.now()+lifetime);
  refreshIndicators();
 }
 function connect(){
  if(!member||socket)return;
  const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/drills?device_id=${deviceId}`);socket=ws;
  ws.onmessage=e=>{if(socket!==ws)return;try{consume(JSON.parse(e.data));}catch{}};
  ws.onclose=()=>{if(socket===ws){socket=null;retryAt=Date.now()+4000;refreshIndicators();}};
  ws.onerror=()=>ws.close();
 }
 async function enroll(){
  const current=member;
  const next=await api('/drills/devices',{method:'POST',body:JSON.stringify({device_id:deviceId,...current,audio_ready:sound.ready})});
  if(member!==current)return;
  lastBeat=Date.now();consume(next);connect();
 }
 async function tick(){
  if(!member||!ctx.enabled||!ctx.user||ticking)return;
  ticking=true;const current=member;
  try{
   if(Date.now()-lastBeat>20000)await enroll();
   else if(!socket||socket.readyState!==WebSocket.OPEN||Date.now()-lastPacket>7000){
    const next=await api(`/drills/poll?device_id=${deviceId}`);if(member===current)consume(next);
   }
   if(member===current&&!socket&&Date.now()>retryAt)connect();
   if(operator()&&control.open){const next=await api(`/drills/rooms/${current.room}`);if(member===current){status=next;renderDevices();}}
  }catch(err){
   if(member!==current)return;
   if(err.status===401||err.status===404){stopAlarm();closeSocket();member=null;finish();renderControl();error(err);}
   else error(err);
  }finally{ticking=false;refreshIndicators();}
 }
 function renderControl(){
  const roomValue=member?.room||room;
  control.innerHTML=`<div class="quake-header"><span class="quake-brand"><span class="dm-brand-mark" aria-hidden="true"></span>DIGIMINDS <small>ALERT LINK</small></span><button type="button" class="quake-close" data-q="close" aria-label="${t('close')}">×</button></div>
   <div class="quake-intro"><span class="quake-badge">${t('badge')}</span><h2 id="quake-heading">${t('title')}</h2><p>${t('intro')}</p></div>
   <div class="quake-steps">${['step1','step2','step3'].map((key,i)=>`<span><b>${i+1}</b>${t(key)}</span>`).join('')}</div>
   <div class="quake-columns"><section class="quake-setup"><form id="quake-join"><label for="quake-room">${t('room')}</label><input id="quake-room" name="room" pattern="[A-Za-z0-9-]{3,16}" maxlength="16" required value="${escape(roomValue)}" ${member?'disabled':''} autocomplete="off" spellcheck="false"><label for="quake-device">${t('device')}</label><input id="quake-device" name="label" maxlength="40" required value="${escape(member?.label||initialLabel||t('deviceDefault'))}" ${member?'disabled':''}>${member?`<div class="quake-ready" id="quake-ready"></div><div class="quake-button-pair"><button type="button" class="quake-secondary" data-q="enable">${t('tone')}</button><button type="button" class="quake-link" data-q="leave">${t('leave')}</button></div>`:`<button type="submit" class="quake-primary">${glyph}${t('join')}</button>`}</form><p class="quake-note">${t('note')}</p><div class="quake-room-stats"><div><strong id="quake-connected">0</strong><span>${t('connected')}</span></div><div><strong id="quake-audio-ready">0</strong><span>${t('soundReady')}</span></div></div><div class="quake-transport" id="quake-transport"></div></section>
   <section class="quake-dispatch"><span class="quake-eyebrow">${operator()?t('operator'):t('waiting')}</span>${operator()?`<form id="quake-send"><label for="quake-location">${t('location')}</label><input id="quake-location" name="location" maxlength="80" required value="Bakı · İçərişəhər"><div class="quake-fields"><div><label for="quake-magnitude">${t('magnitude')}</label><input id="quake-magnitude" name="magnitude" type="number" min="2" max="9" step="0.1" value="5.8" required></div><div><label for="quake-duration">${t('duration')}</label><select id="quake-duration" name="duration"><option value="15">15 ${t('seconds')}</option><option value="30" selected>30 ${t('seconds')}</option><option value="60">60 ${t('seconds')}</option></select></div></div><button type="submit" class="quake-primary quake-send-button" ${!member?'disabled':''}>${t('send')} <span>↗</span></button><button type="button" class="quake-stop-all" data-q="stop" hidden>${t('stopAll')}</button></form><div id="quake-delivery"></div>`:`<div class="quake-waiting">${glyph}<p>${t('onlyOperator')}</p></div>`}<p class="quake-source">${t('source')}<br>${t('notGoogle')}</p></section></div>
   <p id="quake-error" role="status" aria-live="polite"></p>${operator()?`<section class="quake-devices"><h3>${t('deviceList')}</h3><div id="quake-devices-list"></div><p class="quake-note">${t('receiptNote')}</p></section>`:''}`;
  refreshIndicators();renderDevices();
 }
 function refreshIndicators(){
  onStatus({joined:!!member,online:!!member&&Date.now()-lastPacket<8000,connected:packet?.connected||0,audioReady:sound.ready});
  if(!control.innerHTML)return;
  const q=id=>control.querySelector('#quake-'+id);
  if(q('connected'))q('connected').textContent=packet&&member?packet.connected:0;
  if(q('audio-ready'))q('audio-ready').textContent=packet&&member?packet.audio_ready:0;
  if(q('ready')){q('ready').textContent=(sound.ready?'● ':'○ ')+t(sound.ready?'ready':'blocked');q('ready').classList.toggle('not-ready',!sound.ready);}
  if(q('transport'))q('transport').textContent=!member?'—':Date.now()-lastPacket>8000?t('offline'):socket?.readyState===WebSocket.OPEN?'● '+t('live'):'◌ '+t('polling');
  const stop=control.querySelector('[data-q="stop"]');if(stop)stop.hidden=!active;
  const send=control.querySelector('#quake-send button[type="submit"]');if(send)send.disabled=!member||!!active||busy;
 }
 function renderDevices(){
  const list=control.querySelector('#quake-devices-list'),delivery=control.querySelector('#quake-delivery');if(!list)return;
  const devices=status?.devices||[];
  list.innerHTML=devices.length?devices.map(d=>{const receipt=d.receipt||{},state=receipt.acknowledged?'confirmed':receipt.muted?'muted':receipt.audio_started?'playing':receipt.received?'delivered':d.audio_ready?'ready':'blocked';return `<div class="quake-device-row"><span class="quake-device-symbol">▯</span><span><b>${escape(d.label)}</b><small>${d.device_id.slice(0,6).toUpperCase()} · ${t(d.online?'live':'offline')}</small></span><span class="quake-device-state ${receipt.audio_started?'success':''}">${t(state)}</span></div>`;}).join(''):`<p class="quake-note">${t('none')}</p>`;
  if(delivery)delivery.innerHTML=`<div class="quake-delivery"><div><strong>${devices.filter(d=>d.receipt.received).length}</strong><span>${t('delivered')}</span></div><div><strong>${devices.filter(d=>d.receipt.audio_started).length}</strong><span>${t('playing')}</span></div></div>`;
 }
 function renderAlert(){
  if(!active)return;
  alert.innerHTML=`<div class="quake-alarm-top"><span class="quake-badge">${t('badge')}</span><span class="quake-alarm-room">${escape(active.room)}</span></div><div class="quake-alarm-body"><div class="quake-alarm-symbol">${glyph}</div><p class="quake-eyebrow">DIGIMINDS · ALERT LINK</p><h2 id="quake-alert-heading">${t('alarmTitle')}</h2><p id="quake-alert-description">${t('alarmSub')}</p><blockquote class="quake-message">${escape(active.message||t('alarmSub'))}</blockquote><div class="quake-event"><div><strong>${Number(active.magnitude).toFixed(1)}</strong><span>${t('magnitude')}</span></div><div><b>${escape(active.location)}</b><span>${t('source')}</span></div></div><p id="quake-audio-status" role="status"></p><button type="button" class="quake-primary" data-q="unblock" hidden>${t('enable')}</button><button type="button" class="quake-mute" data-q="mute">${t('mute')}</button><div class="quake-button-pair"><button type="button" class="quake-secondary" data-q="ack">${t('ack')}</button>${ctx.user?.permissions?.includes('sos:create')?`<button type="button" class="quake-sos" data-q="sos">${t('sos')}</button>`:''}</div><p class="quake-note">${t('noSOS')}</p></div><div class="quake-alarm-footer"><span>${t('expires')} <b id="quake-countdown"></b> ${t('seconds')}</span><button type="button" class="quake-link" data-q="monitor">${t('close')}</button></div>`;
  refreshAlert();
 }
 function refreshAlert(){
  if(!active)return;
  const state=alert.querySelector('#quake-audio-status');if(state)state.textContent=t(muted?'soundOff':playing&&sound.ready?'soundOn':'soundBlocked');
  const enable=alert.querySelector('[data-q="unblock"]');if(enable)enable.hidden=muted||(playing&&sound.ready);
  const muteButton=alert.querySelector('[data-q="mute"]');if(muteButton)muteButton.hidden=muted;
  const countdown=alert.querySelector('#quake-countdown');if(countdown)countdown.textContent=Math.max(0,Math.ceil((deadline-performance.now())/1000));
 }
 root.addEventListener('submit',async e=>{
  e.preventDefault();e.stopPropagation();if(busy)return;
  busy=true;const form=e.target,data=new FormData(form);
  try{
   if(form.id==='quake-join'){
    await sound.unlock();room=normalizeRoom(data.get('room'));member={room,label:String(data.get('label')).trim()||t('deviceDefault')};
    try{await enroll();}catch(err){member=null;throw err;}
    renderControl();if(!active)sound.play(.8,true);await tick();
   }else if(form.id==='quake-send'){
    if(!member)throw Error('join_first');
    // Reuse this key after a network timeout; never create two drills on retry.
    const fields={room:member.room,location:String(data.get('location')).trim(),magnitude:Number(data.get('magnitude')),duration:Number(data.get('duration'))};
    const signature=JSON.stringify(fields);if(draftKey?.signature!==signature)draftKey={signature,key:makeId()};
    await api('/drills/earthquake',{method:'POST',body:JSON.stringify({event_key:draftKey.key,...fields})});draftKey=null;await tick();
   }
  }catch(err){error(err);}finally{busy=false;refreshIndicators();}
 });
 root.addEventListener('click',async e=>{
  const action=e.target.closest('[data-q]')?.dataset.q;if(!action)return;e.stopPropagation();
  try{
   if(action==='close')control.close();
   if(action==='enable'||action==='unblock'){
    await sound.unlock();
    if(action==='unblock'&&active){muted=false;playing=sound.play(Math.max(0,(deadline-performance.now())/1000));if(playing)void receipt('audio_started');}
    else if(!active)sound.play(.8,true);
    if(member)await enroll();refreshIndicators();refreshAlert();
   }
   if(action==='leave'){
    if(member)await api(`/drills/devices/${deviceId}`,{method:'DELETE'});
    member=null;packet=null;status=null;closeSocket();finish();renderControl();
   }
   if(action==='mute')mute();
   if(action==='ack'){mute();void receipt('acknowledged');alert.close();}
   if(action==='sos'){mute();alert.close();control.close();onSOS();}
   if(action==='monitor'){mute();alert.close();renderControl();control.showModal();await tick();}
   if(action==='stop'&&active){await api(`/drills/earthquake/${active.id}/cancel`,{method:'POST'});finish();await tick();}
  }catch(err){error(err);}
 });
 // Native dialogs own focus and Escape; don't let the map's keyboard handler run.
 root.addEventListener('keydown',e=>e.stopPropagation());
 alert.addEventListener('cancel',()=>mute());
 const interval=setInterval(()=>{void tick();if(active){if(performance.now()>=deadline)finish();else refreshAlert();}},1000);
 window.addEventListener('pagehide',()=>{stopAlarm();closeSocket();});
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){if(active&&performance.now()>=deadline)finish();void tick();}});
 return {
  update(next){
   const identityChanged=next.user?.id!==ctx.user?.id,languageChanged=next.lang!==ctx.lang;
   ctx=next;
   if(identityChanged||!next.enabled){member=null;packet=null;status=null;deviceId=makeId();closeSocket();finish();control.close();}
   if(languageChanged&&control.open)renderControl();if(languageChanged&&active)renderAlert();
  },
  open(){if(!ctx.enabled||!ctx.user)return;beforeOpen();renderControl();if(!control.open)control.showModal();void tick();},
  destroy(){clearInterval(interval);stopAlarm();closeSocket();root.remove();}
 };
}
