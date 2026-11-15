import {createEarthquakeDemo} from './earthquake.js';
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const deviceIcon='<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 18h4M10 5h4"/></svg>';
const screenIcon='<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 22h8M12 17v5"/></svg>';
const roomParam=new URLSearchParams(location.search).get('room')?.toUpperCase();
let room=/^[A-Z0-9-]{3,16}$/.test(roomParam||'')?roomParam:'DIGI26',user=null,health=null,latest=null,busy=false,key=null,polling=false,connected=0,remoteToken=null;
const remote=document.body.dataset.jury==='remote';
async function api(path,options={}){
 const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json','X-Requested-With':'DigiMinds',...(remoteToken?{Authorization:'Bearer '+remoteToken}:{})},signal:AbortSignal.timeout(7000)});
 const data=await response.json();if(!response.ok)throw Object.assign(Error(typeof data.detail==='string'?data.detail:'invalid_input'),{status:response.status});return data;
}
function error(err){$('#jury-error').textContent=err.status===429?'Çox tez göndərildi. Bir az gözləyib yenidən sınayın.':err.message==='drill_already_active'?'Əvvəlki təlim davam edir. Əvvəlcə onu dayandırın.':err.status===401||err.status===403?'Pultu açmaq üçün demo hesabına daxil olun.':'Bağlantı alınmadı. Eyni Wi-Fi və server ünvanını yoxlayın.';}
function uuid(){const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const h=[...bytes].map(x=>x.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;}
function allowed(){return health?.demo&&user?.permissions?.includes('demo:write');}
function frame(){
 $('#jury').innerHTML=`<header class="jury-header"><a class="jury-brand" href="/"><span class="jury-mark">D</span>DIGIMINDS</a><span class="jury-tag">TƏLİM REJİMİ</span><a class="jury-map" href="/workspace.html">Xəritəyə qayıt</a></header>
 <div class="jury-body"><div class="jury-heading"><p class="jury-eyebrow">${remote?'TELEFON PULTU':'CANLI TƏQDİMAT'}</p><h1>${remote?'Bir mesaj göndər.<br>Siqnalı başlat.':'Bir mesaj.<br>Vaxtında xəbərdarlıq.'}</h1><p>${remote?'Buradan göndərdiyiniz sınaq mesajı eyni otaqdakı hazır cihazlarda görünəcək və “dut-dut” siqnalını başladacaq.':'Telefondan bir mesaj göndərin. Noutbukda və qoşulmuş cihazlarda xəbərdarlığın və səsin başladığını göstərin.'}</p></div>
 ${remote?remotePanel():screenPanel()}<p id="jury-error" role="alert"></p><footer class="jury-footer"><span>Google xəbərdarlığına qoşulmayıb. Real hadisə deyil.</span><span>DIGITAL CHALLENGE · 2026</span></footer></div>`;
}
function remotePanel(){return `<section class="remote-card"><div class="remote-top"><span>${deviceIcon} MESAJ GÖNDƏRƏN</span><span id="remote-connection">Qoşulur…</span></div><div id="remote-login"><p>Sınaq mesajını göndərmək üçün demo dispetçer pultunu açın.</p><button id="remote-login-button" class="jury-primary">Demo pultunu aç</button><small>Yalnız təqdimat üçün hazır demo hesabı.</small></div><form id="remote-form" hidden><label for="remote-room">Otaq kodu</label><input id="remote-room" pattern="[A-Za-z0-9-]{3,16}" maxlength="16" required value="${esc(room)}" autocomplete="off"><label for="remote-message">Göndərəcəyiniz mesaj</label><textarea id="remote-message" maxlength="240" rows="4" required>Zəlzələ xəbərdarlığı: Bakı. Bu, DigiMinds təqdimatı üçün sınaq mesajıdır.</textarea><div class="remote-count"><span>Yalnız təlim otağına göndərilir</span><span id="remote-length">0 / 240</span></div><details class="remote-settings"><summary>Təlim parametrləri</summary><label for="remote-location">Sınaq məkanı</label><input id="remote-location" value="Bakı · İçərişəhər" maxlength="80" required><div class="remote-fields"><div><label for="remote-magnitude">Maqnituda</label><input id="remote-magnitude" type="number" min="2" max="9" step="0.1" value="5.8" required></div><div><label for="remote-duration">Səs müddəti</label><select id="remote-duration"><option value="15">15 saniyə</option><option value="30" selected>30 saniyə</option><option value="60">60 saniyə</option></select></div></div></details><button id="remote-send" class="jury-primary" type="submit">Mesajı göndər <span aria-hidden="true">→</span></button><button id="remote-stop" class="jury-stop" type="button" hidden>Bütün cihazlarda dayandır</button></form><div id="remote-result" role="status" aria-live="polite"></div><div class="remote-metrics"><div><b id="remote-devices">0</b><span>bağlı cihaz</span></div><div><b id="remote-delivered">0</b><span>mesaj çatdı</span></div><div><b id="remote-audio">0</b><span>səs başladı</span></div></div><p class="jury-tip">Əvvəl noutbukda “Ekranı hazırla” → “Qoşul və səsi aktivləşdir” basın. Telefonun özü siqnal vermək üçün otağa qoşulmur.</p></section>`;}
function screenPanel(){return `<div class="jury-grid"><section class="receiver-card"><div class="receiver-top"><span class="receiver-live"><i></i> QƏBUL EKRANI</span><span>${screenIcon}</span></div><div class="receiver-illustration"><span class="receiver-ring"></span><span class="receiver-ring second"></span><div>${screenIcon}</div><span class="beep one"></span><span class="beep two"></span></div><h2>Mesajı gözləyən ekran.</h2><p>Bir dəfə səsi aktivləşdirin. Sonra telefondan göndərilən mesaj səsi avtomatik başladacaq.</p><div class="receiver-room"><span>ORTAQ OTAQ</span><b>${esc(room)}</b></div><button id="screen-prepare" class="jury-primary" disabled>Ekranı hazırla ${screenIcon}</button><p class="receiver-status" id="screen-state">Serverə qoşulur…</p></section>
 <section class="jury-setup"><p class="jury-eyebrow">60 SANİYƏDƏ HAZIRLA</p><ol><li><span>01</span><div><h3>Noutbukda səsi aç.</h3><p>“Ekranı hazırla” seçin, sonra otağa qoşulun. İki qısa yoxlama səsi eşidilməlidir.</p></div></li><li><span>02</span><div><h3>Telefonda pultu aç.</h3><p>Eyni Wi-Fi və ya hotspot-a qoşulun. Aşağıdakı ünvanı telefonun brauzerində açın.</p></div></li><li><span>03</span><div><h3>Mesajı göndər, nəticəni göstər.</h3><p>Pultda mesajı yazıb göndərin. Bu ekranda bildiriş açılır, “dut-dut” səsi başlayır.</p></div></li></ol><div class="phone-link-card"><label for="phone-origin">Telefondan əlçatan server ünvanı</label><input id="phone-origin" type="url" value="${esc(location.origin)}" spellcheck="false"><a id="phone-link" href="/remote.html?room=${encodeURIComponent(room)}">Telefon pultu</a><div class="link-actions"><button id="copy-link" type="button">Ünvanı köçür</button><a id="test-remote" href="/remote.html?room=${encodeURIComponent(room)}" target="_blank" rel="noopener">Pultu bu cihazda aç</a></div><small id="phone-hint">Ünvan hazırlanır…</small></div><p class="jury-tip">Jüriyə: “Hazırda real zəlzələ gözləmirik. Telefonda sınaq mesajı göndərirəm; sistem bunu qoşulmuş cihazlara çatdırır və xəbərdarlıq səsini başladır.”</p></section></div>`;}
const quake=!remote?createEarthquakeDemo({api,beforeOpen:()=>{},onSOS:()=>{location.href='/workspace.html#sos';},initialRoom:room,initialLabel:'Jüri ekranı',onStatus:state=>{if($('#screen-state'))$('#screen-state').textContent=state.joined?(state.online?`Hazır · ${state.connected} bağlı cihaz · ${state.audioReady?'səs aktivdir':'səs üçün toxunun'}`:'Bağlantı kəsilib · serveri yoxlayın'):'Otağa qoşulmaq üçün ekranı hazırlayın.';}}):null;
function updateRemote(){
 const ready=allowed();$('#remote-login').hidden=ready;$('#remote-form').hidden=!ready;
 if(!ready)return;
 $('#remote-connection').textContent='Pult hazırdır';$('#remote-send').disabled=busy||!!latest;
 $('#remote-stop').hidden=!latest;$('#remote-stop').disabled=busy;
 $('#remote-length').textContent=`${$('#remote-message').value.length} / 240`;
}
async function refreshRemote(){
 if(!allowed()||polling)return;polling=true;
 const requested=room;
 try{const result=await api('/drills/rooms/'+room);if(requested!==room)return;
  latest=result.event&&!result.event.cancelled&&result.event.expires_at>result.server_time?result.event:null;
  connected=result.devices.filter(d=>d.online).length;
  $('#remote-devices').textContent=connected;$('#remote-delivered').textContent=result.devices.filter(d=>d.receipt.received).length;$('#remote-audio').textContent=result.devices.filter(d=>d.receipt.audio_started).length;
  updateRemote();
 }catch(err){$('#remote-connection').textContent='Bağlantı yoxdur';if(err.status===401||err.status===403){user=null;latest=null;updateRemote();}error(err);}finally{polling=false;}
}
function updatePhoneLink(){
 try{const origin=new URL($('#phone-origin').value);if(!['http:','https:'].includes(origin.protocol)||origin.username||origin.password)throw Error();
  const url=new URL('/remote.html',origin.origin);url.searchParams.set('room',room);$('#phone-link').href=url.href;$('#phone-link').textContent=url.href;
  $('#phone-hint').textContent=['127.0.0.1','localhost','[::1]','0.0.0.0'].includes(origin.hostname)?'Bu ünvan yalnız noutbukda işləyir. JURI_DEMO.cmd başladın və terminaldakı Wi-Fi IP ünvanını daxil edin.':'Telefon bu serverə çatmalıdır. Açılmırsa, Wi-Fi, IP ünvanı və firewall icazəsini yoxlayın.';
 }catch{$('#phone-hint').textContent='http:// və ya https:// ilə düzgün server ünvanı yazın.';$('#phone-link').removeAttribute('href');}
}
frame();
document.addEventListener('input',event=>{
 if(event.target.id==='phone-origin')updatePhoneLink();
 if(event.target.id==='remote-message')updateRemote();
 if(event.target.id==='remote-room'){
  const value=event.target.value.trim().toUpperCase();if(/^[A-Z0-9-]{3,16}$/.test(value)){room=value;latest=null;key=null;void refreshRemote();}
 }
});
document.addEventListener('click',async event=>{
 const id=event.target.closest('button')?.id;try{
  if(id==='screen-prepare')quake.open();
  if(id==='remote-login-button'){
   if(!health?.demo)return;event.target.disabled=true;
   const auth=await api('/auth/login',{method:'POST',body:JSON.stringify({username:'demo-dispatcher',password:'demo',cookie_session:false})});remoteToken=auth.token;user=await api('/auth/me');updateRemote();await refreshRemote();
  }
  if(id==='remote-stop'&&latest){busy=true;updateRemote();await api(`/drills/earthquake/${latest.id}/cancel`,{method:'POST'});latest=null;$('#remote-result').textContent='Təlim dayandırıldı.';await refreshRemote();}
  if(id==='copy-link'){
   const link=$('#phone-link');if(!link.hasAttribute('href'))return;
   if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(link.href);event.target.textContent='Köçürüldü';}
   else{const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(link);selection.removeAllRanges();selection.addRange(range);event.target.textContent='Seçildi · köçürün';}
  }
 }catch(err){error(err);}finally{busy=false;if(remote){$('#remote-login-button').disabled=!health?.demo;updateRemote();}}
});
document.addEventListener('submit',async event=>{
 if(event.target.id!=='remote-form')return;event.preventDefault();if(busy||!allowed())return;
 busy=true;updateRemote();$('#jury-error').textContent='';
 const payload={room:$('#remote-room').value.trim().toUpperCase(),message:$('#remote-message').value.trim(),location:$('#remote-location').value.trim(),magnitude:Number($('#remote-magnitude').value),duration:Number($('#remote-duration').value)};
 const signature=JSON.stringify(payload);if(key?.signature!==signature)key={signature,id:uuid()};
 try{const result=await api('/drills/earthquake',{method:'POST',body:JSON.stringify({...payload,event_key:key.id})});latest=result;key=null;$('#remote-result').textContent='Mesaj göndərildi. Cihazların qəbul təsdiqi gözlənilir.';await refreshRemote();}
 catch(err){error(err);}finally{busy=false;updateRemote();}
});
async function boot(){
 try{
  health=await api('/health');if(!health.demo){$('#jury-error').textContent='Təlim rejimi bu serverdə söndürülüb.';if(remote)$('#remote-login-button').disabled=true;return;}
  try{user=await api('/auth/me');}catch(err){if(err.status!==401)throw err;await api('/auth/guest',{method:'POST'});user=await api('/auth/me');}
  if(remote){updateRemote();await refreshRemote();setInterval(refreshRemote,2000);}
  else{quake.update({user,enabled:true,lang:'az'});$('#screen-prepare').disabled=false;
   updatePhoneLink();const connection=await api('/drills/connection').catch(()=>({lan_addresses:[]}));if(['localhost','127.0.0.1'].includes(location.hostname)&&connection.lan_addresses.length)$('#phone-origin').value=`${location.protocol}//${connection.lan_addresses[0]}:${location.port||connection.port}`;updatePhoneLink();}
 }catch(err){error(err);}
}
void boot();
