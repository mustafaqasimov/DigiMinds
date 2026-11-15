import {resolveRoute} from './routing-client.js';
import {resilienceMessages} from './resilience-i18n.js';
import {translations} from './i18n.js';
import {uiTranslations} from './ui-i18n.js';
import {renderLayout} from './ui.js';
import {mountMap,mapCommand} from './map.js';
import {createProfileUI} from './profile.js';
import {createVoiceUI} from './voice.js';
import {voiceText} from './voice-i18n.js';
for(const locale of Object.keys(voiceText))translations[locale].voiceSOS=voiceText[locale].launch;
import {createEarthquakeDemo} from './earthquake.js';
import {quakeMessages} from './earthquake-i18n.js';
import {eventMessages} from './events-i18n.js';
import {seismicMessages} from './seismic-i18n.js';
for (const locale of Object.keys(resilienceMessages)) Object.assign(translations[locale],resilienceMessages[locale]);
for (const locale of Object.keys(uiTranslations)) Object.assign(translations[locale], uiTranslations[locale]);
for (const locale of Object.keys(eventMessages)) Object.assign(translations[locale],eventMessages[locale]);
for (const locale of Object.keys(seismicMessages)) Object.assign(translations[locale],seismicMessages[locale]);
for (const locale of Object.keys(quakeMessages)) translations[locale].earthquakeDemo=quakeMessages[locale].launch;
import {localRoutes,outbox,cache} from './offline.js';
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let lang=localStorage.getItem('dm_lang')||'az';if(!translations[lang])lang='az';
const t=k=>translations[lang][k]||translations.en[k]||k;
const paths={shield:'M12 3 20 6v6c0 5-8 9-8 9S4 17 4 12V6Z M9 12l2 2 4-5',map:'m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Z M9 3v16 M15 5v16',grid:'M3 3h7v7H3Z M14 3h7v7h-7Z M3 14h7v7H3Z M14 14h7v7h-7Z',pin:'M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0',bolt:'m13 2-9 12h7l-1 8 10-13h-7Z',fire:'M13 2c2 6-4 6-2 11 3-1 4-3 4-5 7 7 4 14-3 14S1 15 7 8c0 3 2 4 3 4-3-5 1-6 3-10Z',collapse:'M3 21h18 M4 21V9l6-6 4 5 6-2v15 M9 9l2 4-3 3 4 5 M16 11v3 M16 17v2',flood:'M2 11q3-4 6 0t6 0 8 0 M2 16q3-4 6 0t6 0 8 0 M2 21q3-4 6 0t6 0 8 0 M12 2v5',medical:'M9 3h6v6h6v6h-6v6H9v-6H3V9h6Z',home:'m3 11 9-8 9 8 M5 10v11h14V10 M9 21v-7h6v7',team:'M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a6 6 0 0 1 12 0v3 M18 5a3 3 0 0 1 0 6 M20 21v-4a4 4 0 0 0-2-3',bell:'M18 8a6 6 0 0 0-12 0c0 8-3 8-3 10h18c0-2-3-2-3-10 M9 21h6',check:'m5 12 4 4L19 6',arrow:'M4 12h16 M14 6l6 6-6 6',route:'M5 5h13v7H6v7h13 M3 3h4v4H3Z M17 17h4v4h-4Z',activity:'M2 12h5l3-8 4 16 3-8h5',settings:'M4 7h16 M4 17h16 M8 4v6 M16 14v6',clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 7v5l3 2',wifi:'M3 8a14 14 0 0 1 18 0 M6 12a9 9 0 0 1 12 0 M9 16a4 4 0 0 1 6 0 M12 20h.01'};
Object.assign(paths,{menu:'M4 6h16 M4 12h16 M4 18h16','chevron-left':'m15 5-7 7 7 7',cloud:'M6 18a5 5 0 1 1 0-10 7 7 0 0 1 13-1 5 5 0 0 1-1 11Z M9 13l2 2 5-5',account:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M15 9a3 3 0 1 1-6 0 3 3 0 0 1 6 0 M6 19a6 6 0 0 1 12 0',navigation:'m3 10 18-7-7 18-3-8Z',close:'m6 6 12 12M6 18 18 6',search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',chevron:'m9 5 7 7-7 7','chevron-down':'m6 9 6 6 6-6',layers:'m3 7 9-5 9 5-9 5Z M3 12l9 5 9-5 M3 17l9 5 9-5',warning:'m12 3 10 18H2Z M12 9v5 M12 17h.01',focus:'M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',mic:'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0Z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3 M8 22h8',plus:'M12 5v14 M5 12h14',minus:'M5 12h14',eye:'M2 12c5-10 15-10 20 0-5 10-15 10-20 0Z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',info:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 11v6 M12 7h.01',flask:'M9 3h6 M10 3v7L4 20h16l-6-10V3 M7 15h10',walk:'M14 4a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0 M8 13l2-5h3l3 5h3 M12 8l-2 8-4 5 M10 16h4l2 5',refresh:'M20 7v5h-5 M4 17v-5h5 M5 8a8 8 0 0 1 14-2l1 6 M4 12l1 6a8 8 0 0 0 14-2'});
Object.assign(paths,{ticket:'M3 7h18v3a2 2 0 0 0 0 4v3H3v-3a2 2 0 0 0 0-4Z M14 7v10',phone:'M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z'});
const icon=name=>`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.shield}"/></svg>`;
const ui={drawer:null,legend:false,panel:null,search:'',filter:'all',selected:null,dialog:null,layerMenu:false,layers:{shelters:true,incidents:true,teams:true,zones:true,events:true,heat:true},zoom:1,pan:{x:0,y:0},chooseLocation:false,editRoads:false,sending:false,offlineMap:location.hash==='#offline'};
let profileOpen=location.hash==='#profile';
let healthReady=false;
let dialogOpener=null,lastDialog=null,ignoreMapClickUntil=0;
let user=null,state=null,health={demo:false},view='citizen',connection='offline',ws=null,reconnectTimer=null,retries=0,route=null,routing=null,routeSequence=0,mode=localStorage.getItem('dm_mode')||'auto',origin={lat:40.37,lng:49.8385},pending=[],adminData=null,syncing=false,lastMapSignature='',autoRouteTimer=null;
const can=p=>user?.permissions?.includes(p), operator=()=>can('dashboard:read'), actionable=()=>can('incident:act');
const fmtTime=v=>new Date(v*1000).toLocaleTimeString(lang==='az'?'az-AZ':lang==='ru'?'ru-RU':'en-GB',{hour:'2-digit',minute:'2-digit'});
let toastTimer;function toast(message){$('#toast').textContent=message;$('#toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),4500);}
async function api(path,options={}){let r;try{r=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json','X-Requested-With':'DigiMinds',...(options.headers||{})},signal:options.signal||AbortSignal.timeout(7000)});}catch(e){throw Object.assign(Error('network'),{network:true});}let data;try{data=await r.json();}catch{data={detail:r.statusText};}if(!r.ok)throw Object.assign(Error(typeof data.detail==='string'?data.detail:'invalid_input'),{status:r.status});return data;}
function errorToast(e){toast(e.message==='profile_requires_accessible_route'?t('profileRequiresAccessible'):e.message==='outside_demo_area'?t('outOfArea'):e.status===429?t('rateLimit'):['no_available_team','no_reserve_shelter'].includes(e.message)?t('unavailable'):t('error')+' · '+e.message);}
const profileUI=createProfileUI({api,language:()=>lang,toast,online:()=>connection!=='offline',demo:()=>health.demo});
const voiceUI=createVoiceUI({api,language:()=>lang,position:()=>origin,beforeOpen:()=>{ui.dialog=null;render();},onManual:()=>{ui.dialog='sos';render();},onSend:(type,note,point)=>sendSOS(type,null,note,point)});
const quake=createEarthquakeDemo({api,beforeOpen:()=>{ui.dialog=null;render();},onSOS:()=>{ui.dialog='sos';render();}});
function setConnection(next){if(connection!==next){connection=next;render();}}
// Event attendance moves with the clock, not with the store revision.
const eventSignature=s=>JSON.stringify((s?.events||[]).map(e=>[e.id,e.phase,e.on_site]));
// undefined until the first snapshot, so an old warning is not replayed on page load.
let seenSeismic;
function notifySeismic(s){const e=s.seismic?.[0];if(e&&e.id!==seenSeismic&&(seenSeismic!==undefined||s.server_time-e.created<30)){navigator.vibrate?.([400,150,400]);ui.drawer=true;setTimeout(()=>toast(t('seismicAlert')+' · '+t('seismicAdvice')),0);}if(e)seenSeismic=e.id;else if(seenSeismic===undefined)seenSeismic=null;}
function consume(s){notifySeismic(s);const changed=!state||state.revision!==s.revision||s.shelters.some((v,i)=>v.stale!==state.shelters[i]?.stale)||eventSignature(state)!==eventSignature(s);const roleChanged=s.viewer&&user?.role!==s.viewer.role;state=s;if(s.viewer){user=s.viewer;if(['citizen','priority_citizen'].includes(user.role))localStorage.setItem('dm_last_citizen',JSON.stringify({id:user.id,username:user.username,role:user.role,accessible_required:user.accessible_required}));if(roleChanged)view=operator()?'dispatcher':can('assignment:read')?'responder':'citizen';if(view!=='citizen'&&!operator()&&!can('assignment:read'))view='citizen';}const pub={map:s.map,roads:s.roads,shelters:s.shelters,config:s.config,server_time:s.server_time,revision:s.revision,dataset:s.dataset,incidents:[],stats:s.stats};cache.put('map',pub).catch(()=>{});const signature=JSON.stringify([user?.accessible_required,s.roads.filter(r=>r.blocked).map(r=>r.id),s.shelters.map(x=>[x.id,x.status,x.occupancy,x.capacity])]);if(lastMapSignature&&lastMapSignature!==signature){route=null;routing=null;++routeSequence;clearTimeout(autoRouteTimer);autoRouteTimer=setTimeout(()=>findRoute(true),180);}lastMapSignature=signature;if(changed)render();}
async function refresh(){try{if(!healthReady){health=await api('/health');healthReady=true;}consume(await api('/state'));if(connection!=='live')setConnection('polling');if(user&&!ws&&!reconnectTimer)connect();await flush();}catch(e){if(e.network)setConnection('offline');else if(e.status===401){closeSocket();setConnection('offline');}}}
function closeSocket(){clearTimeout(reconnectTimer);reconnectTimer=null;if(ws){ws.onclose=null;ws.close();ws=null;}}
function connect(){closeSocket();if(!user)return;const socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);ws=socket;socket.onopen=()=>{retries=0;setConnection('live');flush();};socket.onmessage=event=>{try{const payload=JSON.parse(event.data);if(payload.type==='state')consume(payload.data);}catch{}};socket.onclose=()=>{if(ws!==socket)return;setConnection(navigator.onLine?'polling':'offline');reconnectTimer=setTimeout(connect,Math.min(12000,800*2**Math.min(retries++,4))+Math.random()*300);};socket.onerror=()=>socket.close();}
async function identity(){user=await api('/auth/me');if(['citizen','priority_citizen'].includes(user.role))localStorage.setItem('dm_last_citizen',JSON.stringify({id:user.id,username:user.username,role:user.role,accessible_required:user.accessible_required}));view=operator()?'dispatcher':can('assignment:read')?'responder':'citizen';}
async function bootstrap(){
 if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
 pending=await outbox.all().catch(()=>[]);state=await cache.get('map').catch(()=>null);
 if(!state)state=await fetch('/demo-map.json').then(r=>r.json()).catch(()=>null);
 try{health=await api('/health');healthReady=true;try{await identity();}catch(e){if(e.status!==401)throw e;await api('/auth/guest',{method:'POST'});await identity();}consume(await api('/state'));setConnection('polling');connect();await findRoute();}
 catch(e){user=JSON.parse(localStorage.getItem('dm_last_citizen')||'null');view='citizen';connection='offline';if(state)await findRoute();}
 applyEntry();render();setInterval(()=>{if(connection!=='live')refresh();},4000);
}
// Keep drafts, keyboard focus, and panel scroll stable during live snapshots.
function render(forceProfile=false){
 quake.update({user,enabled:health.demo,lang});
 if(!state)return;
 if(profileOpen&&['citizen','priority_citizen'].includes(user?.role)){if(!$('#profile-root')){$('#app').innerHTML='<main id="profile-root"></main>';profileUI.mount(user.id);}else if(forceProfile)profileUI.paint();return;}
 if(ui.dialog==='lab'&&!can('demo:write')||ui.dialog==='admin'&&!can('role:write'))ui.dialog=null;
 document.documentElement.lang=lang;
 if(view==='responder'&&!ui.panel)ui.panel='teams';
 if(!can('road:write'))ui.editRoads=false;
 if(!can('dashboard:read')&&ui.panel==='alerts')ui.panel=null;
 if(view==='citizen'&&ui.panel==='teams')ui.panel=null;
 const active=document.activeElement;
 const focusId=active?.id, selectionStart=active?.selectionStart, selectionEnd=active?.selectionEnd;
 const focusAction=active?.getAttribute?.('data-action');
 const focusSelect=active?.getAttribute?.('data-select'),focusItem=active?.getAttribute?.('data-id');
 const scrolls=Object.fromEntries([...document.querySelectorAll('[data-scroll]')].map(el=>[el.dataset.scroll,el.scrollTop]));
 const drafts=[...document.querySelectorAll('form input,form select')].map(el=>({form:el.form?.id,item:el.form?.dataset.id,name:el.name,value:el.value,checked:el.checked}));
 if(ui.dialog&&!lastDialog)dialogOpener={id:focusId,action:focusAction};
 const retainedMap=document.getElementById('city-map');
 $('#app').innerHTML=renderLayout({state,user,health,view,connection,route,routing,origin,pending,mode,lang,ui,adminData,t,esc,icon,can,fmtTime});
 if(retainedMap)document.getElementById('city-map')?.replaceWith(retainedMap);
 mountMap({state,user,view,connection,route,origin,ui,t,esc,icon},{onLocation:async point=>{origin={lat:point.lat,lng:point.lng};ui.chooseLocation=false;await findRoute();}});
 for(const el of document.querySelectorAll('[data-scroll]'))el.scrollTop=scrolls[el.dataset.scroll]||0;
 for(const draft of drafts){const form=document.getElementById(draft.form);const input=form?.elements.namedItem(draft.name);if(input&&input.tagName&&form.dataset.id===draft.item){input.value=draft.value;if(input.type==='checkbox')input.checked=draft.checked;}}
 let focus=focusId&&document.getElementById(focusId);
 if(!focus&&focusAction)focus=document.querySelector(`[data-action="${CSS.escape(focusAction)}"]`);
 if(!focus&&focusSelect&&focusItem)focus=document.querySelector(`[data-select="${CSS.escape(focusSelect)}"][data-id="${CSS.escape(focusItem)}"]`);
 if(ui.dialog&&!lastDialog)focus=document.querySelector('[role="dialog"] button');
 if(!ui.dialog&&lastDialog){focus=dialogOpener?.id&&document.getElementById(dialogOpener.id)||dialogOpener?.action&&document.querySelector(`[data-action="${CSS.escape(dialogOpener.action)}"]`);}
 if(focus){focus.focus({preventScroll:true});if(selectionStart!=null&&focus.setSelectionRange)try{focus.setSelectionRange(selectionStart,selectionEnd);}catch{}}
 lastDialog=ui.dialog;
}
function resetWorkspace(){voiceUI.close();clearTimeout(routeRecoveryTimer);++routeSequence;routing=null;route=null;ui.routeLoading=false;profileOpen=false;profileUI.reset();ui.drawer=null;ui.panel=null;ui.selected=null;ui.search='';ui.editRoads=false;ui.chooseLocation=false;ui.dialog=null;}
let routeRecoveryTimer=null;
async function findRoute(automatic=false){
 const seq=++routeSequence;clearTimeout(routeRecoveryTimer);ui.routeLoading=true;render();
 try{
  const result=await resolveRoute({request:api,getState:()=>({...state,viewer:user}),origin:{...origin},mode,online:connection!=='offline'});
  if(seq!==routeSequence)return;
  const previous=route;route=result.routes[0]||null;routing={...result.routing,local_error:result.local_error,no_route:!route};
  ui.routeLoading=false;render();
  if(result.local_error)toast(t(result.local_error==='outside_demo_area'?'outOfArea':'routeDataMissing'));
  if(automatic&&JSON.stringify(previous?.geometry)!==JSON.stringify(route?.geometry))toast(t('routeUpdated'));
  if(routing.mode==='fallback'&&connection!=='offline'&&mode==='auto'){
   const seconds=Math.max(5,routing.circuit?.retry_after_seconds||30);
   routeRecoveryTimer=setTimeout(()=>findRoute(true),(seconds+Math.random())*1000);
  }
 }catch(error){if(seq!==routeSequence)return;route=null;routing=null;ui.routeLoading=false;render();errorToast(error);}
}
async function sendSOS(type,incident_id,voice_note=null,locationOverride=null){if(ui.sending)return;if(!can('sos:create')&&connection!=='offline'){toast(t('citizen')+' · '+t('login'));return;}ui.sending=true;render();const data={event_key:crypto.randomUUID(),type,...(locationOverride||origin),...(voice_note?{voice_note}:{}),client_time:Date.now()/1000,...(incident_id?{incident_id}:{})};try{if(connection==='offline')throw Object.assign(Error('network'),{network:true});const result=await api('/sos',{method:'POST',body:JSON.stringify(data)});ui.dialog=null;toast(t(result.report?.priority===1?'prioritySent':'sent'));await refresh();return true;}catch(e){if(e.network){if(!user){toast(t('login'));return;}if(pending.length>=50){toast(t('rateLimit'));return;}await outbox.put({...data,owner:user.id});pending=await outbox.all();ui.dialog=null;setConnection('offline');render();toast(t('queued'));return true;}else errorToast(e);}finally{ui.sending=false;render();}}
async function flush(){if(syncing||!pending.length||connection==='offline'||!can('sos:create'))return;syncing=true;try{for(const item of pending){if(item.owner!==user.id)continue;const {owner,...data}=item;await api('/sos',{method:'POST',body:JSON.stringify(data)});await outbox.remove(item.event_key);}pending=await outbox.all();render();}catch(e){if(!e.network&&e.status!==429)errorToast(e);}finally{syncing=false;}}
async function signIn(username,password){try{await api('/auth/login',{method:'POST',body:JSON.stringify({username,password})});closeSocket();resetWorkspace();route=null;state=null;await identity();consume(await api('/state'));connect();if(can('role:write'))await loadAdmin();if(view==='citizen')await findRoute();render();}catch(e){errorToast(e);}}
async function loadAdmin(){const [roles,users,audit]=await Promise.all([api('/roles'),api('/users'),api('/audit')]);adminData={roles,users,audit};render();}
document.addEventListener('change',async e=>{if(e.target.dataset.layer){ui.layers[e.target.dataset.layer]=e.target.checked;render();}if(e.target.id==='language'){lang=e.target.value;localStorage.setItem('dm_lang',lang);render(true);}if(e.target.id==='route-mode'){mode=e.target.value;localStorage.setItem('dm_mode',mode);await findRoute();}});
document.addEventListener('submit',async e=>{e.preventDefault();const form=e.target,data=new FormData(form);try{if(form.id==='event-form'){const start=new Date(data.get('start')).getTime()/1000;await api('/events',{method:'POST',body:JSON.stringify({name:data.get('name'),kind:data.get('kind'),node:data.get('node'),description:String(data.get('description')||'').trim(),attendance:Number(data.get('attendance')),start,end:start+Number(data.get('hours'))*3600})});form.reset();toast(t('confirmed'));await refresh();}if(form.id==='occupancy-form'){await api('/shelters/'+form.dataset.id+'/occupancy',{method:'PATCH',body:JSON.stringify({occupancy:Number(data.get('occupancy')),source:'manual'})});toast(t('confirmed'));await refresh();}if(form.id==='login-form')await signIn(data.get('username'),data.get('password'));if(form.id==='role-form'){await api('/roles',{method:'POST',body:JSON.stringify({name:data.get('name'),permissions:[...(data.has('dashboard')?['dashboard:read']:[]),...(data.has('act')?['incident:act']:[])]})});await loadAdmin();toast(t('confirmed'));}if(form.id==='assign-form'){await api(`/users/${data.get('user')}/role`,{method:'PATCH',body:JSON.stringify({role:data.get('role')})});await loadAdmin();toast(t('confirmed'));}}catch(error){errorToast(error);}});
document.addEventListener('click',async e=>{
 const b=e.target.closest('button,[data-node],[data-select]');if(!b)return;if(performance.now()<ignoreMapClickUntil&&b.closest('#city-map'))return;
 try{
  if(b.dataset.profileAction==='back'){profileOpen=false;history.replaceState(null,'',location.pathname+location.search);render();return;}
  if(b.dataset.voiceNotes){await voiceUI.notes(b.dataset.voiceNotes);return;}
  if(b.dataset.assistance){await profileUI.assistance(b.dataset.assistance);return;}
  if(b.dataset.panel){ui.drawer=true;ui.selected=null;ui.dialog=null;ui.panel=b.dataset.panel;ui.search='';ui.filter='all';render();return;}
  if(b.dataset.filter){ui.filter=b.dataset.filter;render();return;}
  if(b.dataset.select){ui.drawer=true;ui.selected={kind:b.dataset.select,id:b.dataset.id};ui.layerMenu=false;render();return;}
  if(b.dataset.view){resetWorkspace();if(b.dataset.view==='citizen'){if(!['citizen','priority_citizen'].includes(user?.role)){await api('/auth/logout',{method:'POST'});await api('/auth/guest',{method:'POST'});await identity();connect();}view='citizen';await refresh();await findRoute();}else if(operator()){view='dispatcher';render();}else if(can('assignment:read')){view='responder';render();}else{ui.dialog='login';render();}return;}
  if(b.dataset.priorityMode){await api('/me/priority',{method:'PUT',body:JSON.stringify({enabled:b.dataset.priorityMode==='on'})});await identity();await refresh();await findRoute();return;}
  if(b.dataset.login){await signIn('demo-'+b.dataset.login,'demo');return;}
  if(b.dataset.node){const n=state.map.nodes.find(n=>n.id===b.dataset.node);origin={lat:n.lat,lng:n.lng};ui.chooseLocation=false;await findRoute();return;}
  if(b.dataset.checkin){await api(`/seismic/${b.dataset.alertId}/checkin`,{method:'POST',body:JSON.stringify({status:b.dataset.checkin,lat:origin.lat,lng:origin.lng})});toast(t('checkinSaved'));await refresh();return;}
  if(b.dataset.seismic){await api('/demo/seismic',{method:'POST',body:JSON.stringify({devices:Number(b.dataset.seismic)})});await refresh();return;}
  if(b.dataset.eventPrepare){await api(`/events/${b.dataset.eventPrepare}/prepare`,{method:'POST'});toast(t('prepared'));await refresh();return;}
  if(b.dataset.eventDelete){await api('/events/'+b.dataset.eventDelete,{method:'DELETE'});ui.selected=null;toast(t('confirmed'));await refresh();return;}
  if(b.dataset.road){const r=state.roads.find(r=>r.id===b.dataset.road);await api('/roads/'+r.id,{method:'PATCH',body:JSON.stringify({enabled:!r.blocked})});await refresh();return;}
  if(b.dataset.sos){await sendSOS(b.dataset.sos);return;}
  if(b.dataset.support){await sendSOS(b.dataset.type,b.dataset.support);return;}
  if(b.dataset.alert){await api(`/alerts/${b.dataset.alert}/${b.dataset.command}`,{method:'POST'});toast(t('confirmed'));await refresh();return;}
  if(b.dataset.occupancy){const s=state.shelters.find(s=>s.id===b.dataset.occupancy);await api(`/shelters/${s.id}/occupancy`,{method:'PATCH',body:JSON.stringify({occupancy:Math.ceil(s.capacity*Number(b.dataset.percent)/100),source:'manual'})});await refresh();return;}
  if(b.dataset.team){await api('/teams/'+b.dataset.team,{method:'PATCH',body:JSON.stringify({status:b.dataset.status})});await refresh();return;}
  if(b.dataset.providerScenario){await api('/demo/routing-provider',{method:'POST',body:JSON.stringify({mode:b.dataset.providerScenario})});mode='auto';await findRoute();return;}
  if(b.dataset.scenario){const k=b.dataset.scenario;await api('/demo/'+k,{method:'POST',body:JSON.stringify({enabled:k==='sos_wave'?true:!state.failures?.[k]})});await refresh();return;}
  switch(b.dataset.action){
   case'profile':if(['citizen','priority_citizen'].includes(user?.role)){profileOpen=true;history.pushState(null,'','#profile');render();}break;
   case'earthquake':quake.open();break;
   case'login':ui.dialog='login';render();break;
   case'close-modal':ui.dialog=null;render();break;
   case'logout':resetWorkspace();await api('/auth/logout',{method:'POST'});closeSocket();await api('/auth/guest',{method:'POST'});await identity();await refresh();connect();await findRoute();break;
   case'route':await findRoute();break;
   case'route-test':mode='auto';await findRoute();break;
   case'zoom-in':mapCommand('zoom-in');break;
   case'zoom-out':mapCommand('zoom-out');break;
   case'close-detail':ui.selected=null;render();break;
   case'layers':ui.layerMenu=!ui.layerMenu;ui.legend=false;render();break;
   case'drawer':ui.drawer=!(ui.drawer??view!=='citizen');render();break;
   case'search':ui.drawer=true;render();document.getElementById('workspace-search')?.focus();break;
   case'legend':ui.legend=!ui.legend;ui.layerMenu=false;render();break;
   case'clear-search':ui.search='';render();break;
   case'map':ui.drawer=true;ui.selected=null;ui.panel=null;render();break;
   case'reset-map':mapCommand('reset-map');break;
   case'offline-map':ui.offlineMap=!ui.offlineMap;render();break;
   case'choose-location':ui.chooseLocation=!ui.chooseLocation;ui.drawer=false;ui.selected=null;render();break;
   case'edit-roads':ui.drawer=false;if(can('road:write'))ui.editRoads=!ui.editRoads;ui.selected=null;render();break;
   case'stop-edit':ui.chooseLocation=false;ui.editRoads=false;render();break;
   case'sos':ui.dialog='sos';render();break;
   case'voice-sos':if(can('sos:create'))await voiceUI.open();else{ui.dialog='login';render();}break;
   case'lab':if(can('demo:write')){ui.dialog='lab';render();}break;
   case'admin':if(can('role:write')){ui.dialog='admin';await loadAdmin();}break;
   case'about':ui.dialog='about';render();break;
   case'seismic-reset':if(can('demo:write')){await api('/demo/seismic/reset',{method:'POST'});toast(t('confirmed'));await refresh();}break;
   case'demo-events':if(can('demo:write')){await api('/demo/events',{method:'POST'});toast(t('confirmed'));await refresh();}break;
   case'admin-refresh':await loadAdmin();break;
   case'sync':await flush();if(pending.length)toast(t('pendingLogin'));break;
   case'safe':if(connection==='offline'||pending.length){toast(t('offlineSafe'));break;}await api('/me/safe',{method:'POST'});toast(t('safeDone'));await refresh();break;
   case'gps':navigator.geolocation.getCurrentPosition(p=>{origin={lat:p.coords.latitude,lng:p.coords.longitude};findRoute();},()=>toast(t('chooseMap')),{timeout:8000});break;
  }
 }catch(error){errorToast(error);}
});
window.addEventListener('online',()=>{refresh();connect();findRoute(true);});window.addEventListener('offline',()=>{closeSocket();setConnection('offline');findRoute(true);});
bootstrap().catch(errorToast);

document.addEventListener('input',event=>{if(['workspace-search','panel-search'].includes(event.target.id)){ui.search=event.target.value;ui.drawer=true;ui.selected=null;render();}});
document.addEventListener('keydown',event=>{
 if(document.querySelector('#earthquake-root dialog[open],#profile-dialog[open],#voice-dialog[open]'))return;
 const dialog=document.querySelector('[role="dialog"]');
 if(event.key==='Escape'){ui.dialog=null;ui.selected=null;ui.layerMenu=false;ui.legend=false;ui.chooseLocation=false;ui.editRoads=false;render();return;}
 if(dialog&&event.key==='Tab'){
   const items=[...dialog.querySelectorAll('button:not([disabled]),input,select,[tabindex="0"]')].filter(el=>el.getClientRects().length);
   if(!items.length)return;
   const first=items[0],last=items[items.length-1];
   if(event.shiftKey&&(document.activeElement===first||!dialog.contains(document.activeElement))){event.preventDefault();last.focus();}
   else if(!event.shiftKey&&(document.activeElement===last||!dialog.contains(document.activeElement))){event.preventDefault();first.focus();}
 }
});
document.addEventListener('map-select',event=>{ui.drawer=true;ui.selected=event.detail;render();});

function applyEntry(){const entry=location.hash.slice(1);profileOpen=entry==='profile';if(entry==='sos')ui.dialog='sos';if(entry==='voice'){if(can('sos:create'))voiceUI.open();else ui.dialog='login';}if(['shelters','safe','route'].includes(entry)){ui.drawer=true;ui.panel='shelters';}if(entry==='dispatcher'){if(operator()){view='dispatcher';ui.drawer=true;}else ui.dialog='login';}if(entry==='offline'){ui.offlineMap=true;mode='local';findRoute();}}
window.addEventListener('hashchange',()=>{applyEntry();render();});

document.addEventListener('map-status',event=>{const status=event.detail.status;if(ui.mapStatus!==status){ui.mapStatus=status;render();}});
