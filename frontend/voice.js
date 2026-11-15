import {loadFeatureStyle} from './ui-assets.js';
import {voiceText} from './voice-i18n.js';

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const mic='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0Z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3 M8 22h8"/></svg>';
const categories=['fire','collapse','flood','medical'];
export function recordingMime(Recorder=globalThis.MediaRecorder){
 return ['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus','audio/webm'].find(t=>Recorder?.isTypeSupported(t))||'';
}
export function voiceNote(result,text){
 const unchanged=text===result.text;
 return {text:text.trim(),suggested_type:unchanged?result.suggested_type:null,
  speech_seconds:unchanged?result.speech_seconds:null,words_per_minute:unchanged?result.words_per_minute:null};
}
export function createVoiceUI({api,language,position,beforeOpen,onManual,onSend}){
 loadFeatureStyle('./voice.css');
 let dialog=null,stage='ready',status=null,error='',result=null,selected=null,edited=false;
 let recorder=null,stream=null,timer=null,controller=null,sequence=0,objectURL=null,started=0,point=null,sending=false;
 const tr=k=>voiceText[language()]?.[k]||voiceText.en[k]||k;
 const button=(action,label,cls='v-secondary',extra='')=>`<button type="button" class="${cls}" data-voice="${action}" ${extra}>${label}</button>`;
 function clearAudio(){if(objectURL)URL.revokeObjectURL(objectURL);objectURL=null;}
 function releaseMic(){clearInterval(timer);timer=null;stream?.getTracks().forEach(track=>track.stop());stream=null;}
 function close(){++sequence;controller?.abort();controller=null;if(recorder&&recorder.state!=='inactive'){recorder.onstop=null;recorder.stop();}recorder=null;releaseMic();clearAudio();dialog?.close();dialog?.remove();dialog=null;}
 function shell(title){
  close();beforeOpen?.();dialog=document.createElement('dialog');dialog.id='voice-dialog';dialog.className='voice-dialog';dialog.setAttribute('aria-labelledby','voice-title');
  dialog.innerHTML=`<header class="v-header"><span class="v-brand">${mic} DigiMinds <b>VOICE SOS</b></span>${button('close','×','v-close',`aria-label="${tr('close')}"`)}</header><div id="voice-body"></div>`;
  document.body.append(dialog);dialog.addEventListener('cancel',e=>{e.preventDefault();if(!sending)close();});dialog.showModal();
 }
 function notice(){return error?`<div class="v-notice" role="alert">${esc(error)}</div>`:'';}
 function paint(){if(!dialog)return;
  const busy=['permission','processing'].includes(stage),recording=stage==='recording',review=stage==='review';
  const body=dialog.querySelector('#voice-body');
  body.innerHTML=`<div class="v-heading"><span class="v-eyebrow">AZƏRBAYCAN DİLİ · 20 SAN.</span><h2 id="voice-title">${tr(review?'review':'title')}</h2><p>${tr(review?'confirm':'subtitle')}</p></div><ol class="v-steps">${['step1','step2','step3'].map((k,i)=>`<li class="${(review?1:0)===i?'active':''}"><span>${i+1}</span>${tr(k)}</li>`).join('')}</ol>${notice()}
  ${review?reviewBody():`<section class="v-recorder ${recording?'recording':''}"><div class="v-bars" aria-hidden="true">${Array.from({length:17},(_,i)=>`<i style="--n:${i};--bar:${14+(i*19%43)}px"></i>`).join('')}</div>${button(recording?'stop':'record',recording?'<span class="v-stop-square"></span>':mic,'v-record',`aria-label="${tr(recording?'stop':'record')}" ${busy||!status?.available?'disabled':''}`)}<h3 role="status">${tr(recording?'recording':stage==='processing'?'processing':stage==='permission'?'checking':'record')}</h3><span id="voice-timer" class="v-timer">${recording?'00:00 / 00:20':busy?tr('wait'):tr('hint')}</span>${recording?button('stop',tr('stop'),'v-primary'):''}${stage==='processing'?`<div class="v-progress" aria-hidden="true"><i></i></div>${button('cancel',tr('cancel'),'v-text')}`:''}</section>${!recording&&!busy?`<div class="v-upload-row">${button('upload',tr('upload'),'v-secondary',!status?.available?'disabled':'')}<small>${tr('limits')}</small><input id="voice-file" type="file" accept="audio/*,.webm,.m4a" hidden></div><p class="v-service ${status?.available?'ready':''}" role="status">${tr(status===null?'checking':status.available?'ready':'missing')}</p>`:''}`}
  ${`<div class="v-footer">${button('manual',tr('manual'),'v-text',sending?'disabled':'')}<p>${tr('privacy')}</p></div>`}`;
  dialog.querySelector('[data-voice="close"]').disabled=sending;
  if(review){body.querySelector('#voice-text').addEventListener('input',()=>{
   edited=true;selected=null;body.querySelector('#voice-review-hint').textContent=tr('edited');body.querySelector('[data-voice="send"]').disabled=true;
   body.querySelectorAll('[data-voice-type]').forEach(b=>b.setAttribute('aria-pressed','false'));
   const tempo=body.querySelector('.v-pace');if(tempo)tempo.hidden=true;
  });}
 }
 function reviewBody(){
  const hint=result.warning==='uncertain'?'uncertain':edited?'edited':result.ambiguous?'ambiguous':selected?'suggested':'unknown';
  return `<section class="v-review"><label for="voice-text">${tr('transcript')}</label><textarea id="voice-text" maxlength="2000" rows="3" ${sending?'disabled':''}>${esc(result.text)}</textarea>${objectURL?`<audio controls preload="metadata" src="${objectURL}" aria-label="${tr('audio')}"></audio>`:''}<div class="v-review-meta"><p id="voice-review-hint" role="status">${tr(hint)}</p>${button('classify',tr('classify'),'v-text',sending?'disabled':'')}</div><fieldset class="v-types"><legend>${tr('type')}</legend>${categories.map(type=>`<button type="button" data-voice-type="${type}" aria-pressed="${selected===type}" ${sending?'disabled':''}><span class="v-type-dot ${type}"></span>${tr(type)}<span class="v-selected-mark" aria-hidden="true">✓</span></button>`).join('')}</fieldset><div class="v-pace"><span>${tr('pace')}</span><strong>${result.words_per_minute!=null?result.words_per_minute+' <small>'+tr('wpm')+'</small>':'—'}</strong><small>${tr(result.words_per_minute!=null?'paceNote':'paceEmpty')}</small></div><div class="v-location"><strong>${tr('location')}</strong><span>${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}</span><small>${tr('locationNote')}</small></div><div class="v-actions">${button('retry',tr('retry'),'v-secondary',sending?'disabled':'')}${button('send',tr(sending?'sending':'send'),'v-send',!selected||sending?'disabled':'')}</div></section>`;
 }
 async function open(){shell();stage='ready';status=null;error='';result=null;selected=null;edited=false;sending=false;point={...position()};paint();const seq=sequence;
  try{const value=await api('/voice/status');if(seq!==sequence)return;status=value;}catch{if(seq!==sequence)return;status={available:false};error=tr('unavailable');}paint();
 }
 function message(error){const codes={voice_not_installed:'missing',voice_busy:'busy',voice_too_long:'long',voice_too_large:'large',voice_invalid_audio:'invalid',voice_audio_only:'invalid',voice_timeout:'timeout',voice_upload_timeout:'timeout',rate_limited:'rate'};return tr(codes[error.message]||'failed');}
 async function analyze(blob){if(!blob.size||blob.size>8*1024*1024){error=tr(blob.size?'large':'empty');stage='ready';paint();return;}
  clearAudio();objectURL=URL.createObjectURL(blob);stage='processing';error='';paint();const seq=sequence;controller=new AbortController();const deadline=setTimeout(()=>controller?.abort(),165000);
  try{
   const response=await fetch('/api/voice/transcribe',{method:'POST',headers:{'Content-Type':blob.type||'application/octet-stream','X-Requested-With':'DigiMinds'},body:blob,signal:controller.signal});
   const value=await response.json();if(!response.ok)throw Error(typeof value.detail==='string'?value.detail:'voice_failed');if(seq!==sequence)return;
   if(!value.text||value.warning==='no_speech'){error=tr('empty');stage='ready';clearAudio();}
   else{result=value;selected=value.suggested_type;edited=false;stage='review';}
  }catch(e){if(seq!==sequence)return;error=e.name==='AbortError'?tr('timeout'):message(e);stage='ready';clearAudio();}
  finally{clearTimeout(deadline);if(seq===sequence){controller=null;paint();dialog?.querySelector('#voice-text')?.focus();}}
 }
 async function record(){
  if(!window.isSecureContext){error=tr('secure');paint();return;}
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){error=tr('unsupported');paint();return;}
  const seq=sequence;stage='permission';error='';paint();
  try{
   const media=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
   if(seq!==sequence){media.getTracks().forEach(t=>t.stop());return;}
   stream=media;const mime=recordingMime();recorder=new MediaRecorder(media,mime?{mimeType:mime}:{});const parts=[];let bytes=0;
   recorder.ondataavailable=e=>{if(e.data.size){parts.push(e.data);bytes+=e.data.size;if(bytes>8*1024*1024&&recorder?.state==='recording')recorder.stop();}};
   recorder.onerror=()=>{if(seq!==sequence)return;recorder.onstop=null;releaseMic();error=tr('noMic');stage='ready';paint();};
   recorder.onstop=()=>{const type=recorder.mimeType;recorder=null;releaseMic();if(seq===sequence)analyze(new Blob(parts,{type}));};
   recorder.start(250);started=performance.now();stage='recording';paint();
   timer=setInterval(()=>{const seconds=Math.floor((performance.now()-started)/1000);const node=dialog?.querySelector('#voice-timer');if(node)node.textContent=`00:${String(Math.min(seconds,20)).padStart(2,'0')} / 00:20`;if(seconds>=20&&recorder?.state==='recording')recorder.stop();},100);
  }catch(e){if(seq!==sequence)return;releaseMic();stage='ready';error=tr(e.name==='NotAllowedError'?'permission':'noMic');paint();}
 }
 async function notes(id){shell();const seq=sequence;dialog.querySelector('#voice-body').innerHTML=`<div class="v-heading"><h2 id="voice-title">${tr('notes')}</h2><p role="status">…</p></div>`;
  try{const data=await api('/incidents/'+encodeURIComponent(id)+'/voice-notes');if(seq!==sequence)return;dialog.querySelector('#voice-body').innerHTML=`<div class="v-heading"><h2 id="voice-title">${tr('notes')}</h2><p>${tr('confirmed')}</p></div><div class="v-note-list">${data.notes.length?data.notes.map(n=>`<article><time>${new Date(n.created_at*1000).toLocaleString()}</time><p>${esc(n.text)}</p>${n.words_per_minute!=null?`<small>${tr('pace')}: ${n.words_per_minute} ${tr('wpm')}. ${tr('paceNote')}</small>`:''}</article>`).join(''):`<p>${tr('noNotes')}</p>`}</div>`;}catch{if(seq===sequence)dialog.querySelector('#voice-body p').textContent=tr('errorNotes');}
 }
 document.addEventListener('click',async event=>{
  const target=event.target.closest('#voice-dialog button');if(!target)return;event.preventDefault();event.stopImmediatePropagation();
  if(sending)return;
  if(target.dataset.voiceType){selected=target.dataset.voiceType;dialog.querySelectorAll('[data-voice-type]').forEach(b=>b.setAttribute('aria-pressed',b===target));dialog.querySelector('[data-voice="send"]').disabled=!dialog.querySelector('#voice-text').value.trim();return;}
  switch(target.dataset.voice){
   case'close':close();break;
   case'manual':close();onManual();break;
   case'record':await record();break;
   case'stop':if(recorder?.state==='recording')recorder.stop();break;
   case'upload':dialog.querySelector('#voice-file').click();break;
   case'cancel':case'retry':close();await open();break;
   case'classify':{const text=dialog.querySelector('#voice-text').value,seq=sequence;target.disabled=true;try{const suggestion=await api('/voice/classify',{method:'POST',body:JSON.stringify({text})});if(seq!==sequence)return;if(dialog.querySelector('#voice-text').value!==text||sending){target.disabled=false;return;}const changed=text!==result.text;result={...result,...suggestion,text,warning:null,...(changed?{words_per_minute:null,speech_seconds:null}:{})};edited=false;selected=suggestion.suggested_type;paint();}catch(e){if(seq===sequence){error=message(e);if(text!==result.text){result.words_per_minute=null;result.speech_seconds=null;}result.text=text;paint();}}break;}
   case'send':{const text=dialog.querySelector('#voice-text').value;if(!selected||!text.trim())return;const note=voiceNote(result,text);sending=true;result.text=text;paint();try{if(await onSend(selected,note,point)){close();return;}error=tr('failed');}catch{error=tr('failed');}finally{sending=false;if(dialog)paint();}break;}
  }
 });
 document.addEventListener('change',event=>{if(event.target.id!=='voice-file')return;const file=event.target.files[0];if(file)analyze(file);});
 window.addEventListener('pagehide',close);
 return {open,close,notes};
}
