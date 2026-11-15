import {translations} from './i18n.js';
import {uiTranslations} from './ui-i18n.js';
import {renderLayout} from './ui.js';
import {mapView} from './map.js';
for (const locale of Object.keys(uiTranslations)) Object.assign(translations[locale], uiTranslations[locale]);
import {localRoutes,outbox,cache} from './offline.js';
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let lang=localStorage.getItem('dm_lang')||'az';if(!translations[lang])lang='az';
const t=k=>translations[lang][k]||translations.en[k]||k;
const paths={shield:'M12 3 20 6v6c0 5-8 9-8 9S4 17 4 12V6Z M9 12l2 2 4-5',map:'m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Z M9 3v16 M15 5v16',grid:'M3 3h7v7H3Z M14 3h7v7h-7Z M3 14h7v7H3Z M14 14h7v7h-7Z',pin:'M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0',bolt:'m13 2-9 12h7l-1 8 10-13h-7Z',fire:'M13 2c2 6-4 6-2 11 3-1 4-3 4-5 7 7 4 14-3 14S1 15 7 8c0 3 2 4 3 4-3-5 1-6 3-10Z',collapse:'M3 21h18 M4 21V9l6-6 4 5 6-2v15 M9 9l2 4-3 3 4 5 M16 11v3 M16 17v2',flood:'M2 11q3-4 6 0t6 0 8 0 M2 16q3-4 6 0t6 0 8 0 M2 21q3-4 6 0t6 0 8 0 M12 2v5',medical:'M9 3h6v6h6v6h-6v6H9v-6H3V9h6Z',home:'m3 11 9-8 9 8 M5 10v11h14V10 M9 21v-7h6v7',team:'M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a6 6 0 0 1 12 0v3 M18 5a3 3 0 0 1 0 6 M20 21v-4a4 4 0 0 0-2-3',bell:'M18 8a6 6 0 0 0-12 0c0 8-3 8-3 10h18c0-2-3-2-3-10 M9 21h6',check:'m5 12 4 4L19 6',arrow:'M4 12h16 M14 6l6 6-6 6',route:'M5 5h13v7H6v7h13 M3 3h4v4H3Z M17 17h4v4h-4Z',activity:'M2 12h5l3-8 4 16 3-8h5',settings:'M4 7h16 M4 17h16 M8 4v6 M16 14v6',clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 7v5l3 2',wifi:'M3 8a14 14 0 0 1 18 0 M6 12a9 9 0 0 1 12 0 M9 16a4 4 0 0 1 6 0 M12 20h.01'};
Object.assign(paths,{close:'m6 6 12 12M6 18 18 6',search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',chevron:'m9 5 7 7-7 7','chevron-down':'m6 9 6 6 6-6',layers:'m3 7 9-5 9 5-9 5Z M3 12l9 5 9-5 M3 17l9 5 9-5',warning:'m12 3 10 18H2Z M12 9v5 M12 17h.01',focus:'M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',plus:'M12 5v14 M5 12h14',minus:'M5 12h14',eye:'M2 12c5-10 15-10 20 0-5 10-15 10-20 0Z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',info:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 11v6 M12 7h.01',flask:'M9 3h6 M10 3v7L4 20h16l-6-10V3 M7 15h10',walk:'M14 4a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0 M8 13l2-5h3l3 5h3 M12 8l-2 8-4 5 M10 16h4l2 5',refresh:'M20 7v5h-5 M4 17v-5h5 M5 8a8 8 0 0 1 14-2l1 6 M4 12l1 6a8 8 0 0 0 14-2'});
const icon=name=>`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.shield}"/></svg>`;
const ui={panel:null,search:'',filter:'all',selected:null,dialog:null,layerMenu:false,layers:{shelters:true,incidents:true,teams:true,zones:false},zoom:1,pan:{x:0,y:0},chooseLocation:false,editRoads:false,sending:false};
let healthReady=false;
let dialogOpener=null,lastDialog=null,ignoreMapClickUntil=0;
let user=null,state=null,health={demo:false},view='citizen',connection='offline',ws=null,reconnectTimer=null,retries=0,route=null,routeSequence=0,mode=localStorage.getItem('dm_mode')||'local',origin={lat:40.37,lng:49.8385},pending=[],adminData=null,syncing=false,lastMapSignature='',autoRouteTimer=null;
const can=p=>user?.permissions?.includes(p), operator=()=>can('dashboard:read'), actionable=()=>can('incident:act');
const fmtTime=v=>new Date(v*1000).toLocaleTimeString(lang==='az'?'az-AZ':lang==='ru'?'ru-RU':'en-GB',{hour:'2-digit',minute:'2-digit'});
let toastTimer;function toast(message){$('#toast').textContent=message;$('#toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),4500);}
async function api(path,options={}){let r;try{r=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json','X-Requested-With':'DigiMinds',...(options.headers||{})},signal:options.signal||AbortSignal.timeout(7000)});}catch(e){throw Object.assign(Error('network'),{network:true});}let data;try{data=await r.json();}catch{data={detail:r.statusText};}if(!r.ok)throw Object.assign(Error(typeof data.detail==='string'?data.detail:'invalid_input'),{status:r.status});return data;}
function errorToast(e){toast(e.message==='outside_demo_area'?t('outOfArea'):e.status===429?t('rateLimit'):['no_available_team','no_reserve_shelter'].includes(e.message)?t('unavailable'):t('error')+' · '+e.message);}
function setConnection(next){if(connection!==next){connection=next;render();}}
function consume(s){const changed=!state||state.revision!==s.revision||s.shelters.some((v,i)=>v.stale!==state.shelters[i]?.stale);const roleChanged=s.viewer&&user?.role!==s.viewer.role;state=s;if(s.viewer){user=s.viewer;if(roleChanged)view=operator()?'dispatcher':can('assignment:read')?'responder':'citizen';if(view!=='citizen'&&!operator()&&!can('assignment:read'))view='citizen';}const pub={map:s.map,roads:s.roads,shelters:s.shelters,config:s.config,server_time:s.server_time,revision:s.revision,dataset:s.dataset,incidents:[],stats:s.stats};cache.put('map',pub).catch(()=>{});const signature=JSON.stringify([s.roads.filter(r=>r.blocked).map(r=>r.id),s.shelters.map(x=>[x.id,x.status,x.occupancy,x.capacity])]);if(lastMapSignature&&lastMapSignature!==signature&&route){clearTimeout(autoRouteTimer);autoRouteTimer=setTimeout(()=>findRoute(true),180);}lastMapSignature=signature;if(changed)render();}
async function refresh(){try{if(!healthReady){health=await api('/health');healthReady=true;}consume(await api('/state'));if(connection!=='live')setConnection('polling');if(user&&!ws&&!reconnectTimer)connect();await flush();}catch(e){if(e.network)setConnection('offline');else if(e.status===401){closeSocket();setConnection('offline');}}}
function closeSocket(){clearTimeout(reconnectTimer);reconnectTimer=null;if(ws){ws.onclose=null;ws.close();ws=null;}}
function connect(){closeSocket();if(!user)return;const socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);ws=socket;socket.onopen=()=>{retries=0;setConnection('live');flush();};socket.onmessage=event=>{try{const payload=JSON.parse(event.data);if(payload.type==='state')consume(payload.data);}catch{}};socket.onclose=()=>{if(ws!==socket)return;setConnection(navigator.onLine?'polling':'offline');reconnectTimer=setTimeout(connect,Math.min(12000,800*2**Math.min(retries++,4))+Math.random()*300);};socket.onerror=()=>socket.close();}
async function identity(){user=await api('/auth/me');if(user.role==='citizen')localStorage.setItem('dm_last_citizen',JSON.stringify({id:user.id,username:user.username,role:user.role}));view=operator()?'dispatcher':can('assignment:read')?'responder':'citizen';}
async function bootstrap(){
 if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
 pending=await outbox.all().catch(()=>[]);state=await cache.get('map').catch(()=>null);
 if(!state)state=await fetch('/demo-map.json').then(r=>r.json()).catch(()=>null);
 try{health=await api('/health');healthReady=true;try{await identity();}catch(e){if(e.status!==401)throw e;await api('/auth/guest',{method:'POST'});await identity();}consume(await api('/state'));setConnection('polling');connect();await findRoute();}
 catch(e){user=JSON.parse(localStorage.getItem('dm_last_citizen')||'null');view='citizen';connection='offline';if(state)await findRoute();}
 render();setInterval(()=>{if(connection!=='live')refresh();},4000);
}
// Keep drafts, keyboard focus, and panel scroll stable during live snapshots.
function render(){
 if(!state)return;
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
 $('#app').innerHTML=renderLayout({state,user,health,view,connection,route,origin,pending,mode,lang,ui,adminData,t,esc,icon,can,fmtTime});
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
function resetWorkspace(){ui.panel=null;ui.selected=null;ui.search='';ui.editRoads=false;ui.chooseLocation=false;ui.dialog=null;}
async function findRoute(automatic=false){const seq=++routeSequence;try{let result;if(connection==='offline'){result=localRoutes(state,origin);}else{result=(await api(`/routes?lat=${origin.lat}&lng=${origin.lng}&mode=${mode}`)).routes;}if(seq!==routeSequence)return;const previous=route;route=result[0]||null;render();if(automatic&&JSON.stringify(previous?.geometry)!==JSON.stringify(route?.geometry))toast(t('routeUpdated'));}catch(e){if(seq!==routeSequence)return;if(e.network){setConnection('offline');route=localRoutes(state,origin)[0]||null;render();}else{route=null;render();errorToast(e);}}}
async function sendSOS(type,incident_id){if(ui.sending)return;if(!can('sos:create')&&connection!=='offline'){toast(t('citizen')+' · '+t('login'));return;}ui.sending=true;render();const data={event_key:crypto.randomUUID(),type,...origin,client_time:Date.now()/1000,...(incident_id?{incident_id}:{})};try{if(connection==='offline')throw Object.assign(Error('network'),{network:true});await api('/sos',{method:'POST',body:JSON.stringify(data)});ui.dialog=null;toast(t('sent'));await refresh();}catch(e){if(e.network){if(!user){toast(t('login'));return;}if(pending.length>=50){toast(t('rateLimit'));return;}await outbox.put({...data,owner:user.id});pending=await outbox.all();ui.dialog=null;setConnection('offline');render();toast(t('queued'));}else errorToast(e);}finally{ui.sending=false;render();}}
async function flush(){if(syncing||!pending.length||connection==='offline'||!can('sos:create'))return;syncing=true;try{for(const item of pending){if(item.owner!==user.id)continue;const {owner,...data}=item;await api('/sos',{method:'POST',body:JSON.stringify(data)});await outbox.remove(item.event_key);}pending=await outbox.all();render();}catch(e){if(!e.network&&e.status!==429)errorToast(e);}finally{syncing=false;}}
async function signIn(username,password){try{await api('/auth/login',{method:'POST',body:JSON.stringify({username,password})});closeSocket();resetWorkspace();route=null;state=null;await identity();consume(await api('/state'));connect();if(can('role:write'))await loadAdmin();render();}catch(e){errorToast(e);}}
async function loadAdmin(){const [roles,users,audit]=await Promise.all([api('/roles'),api('/users'),api('/audit')]);adminData={roles,users,audit};render();}
document.addEventListener('change',async e=>{if(e.target.dataset.layer){ui.layers[e.target.dataset.layer]=e.target.checked;render();}if(e.target.id==='language'){lang=e.target.value;localStorage.setItem('dm_lang',lang);render();}if(e.target.id==='route-mode'){mode=e.target.value;localStorage.setItem('dm_mode',mode);await findRoute();}});
document.addEventListener('submit',async e=>{e.preventDefault();const form=e.target,data=new FormData(form);try{if(form.id==='occupancy-form'){await api('/shelters/'+form.dataset.id+'/occupancy',{method:'PATCH',body:JSON.stringify({occupancy:Number(data.get('occupancy')),source:'manual'})});toast(t('confirmed'));await refresh();}if(form.id==='login-form')await signIn(data.get('username'),data.get('password'));if(form.id==='role-form'){await api('/roles',{method:'POST',body:JSON.stringify({name:data.get('name'),permissions:[...(data.has('dashboard')?['dashboard:read']:[]),...(data.has('act')?['incident:act']:[])]})});await loadAdmin();toast(t('confirmed'));}if(form.id==='assign-form'){await api(`/users/${data.get('user')}/role`,{method:'PATCH',body:JSON.stringify({role:data.get('role')})});await loadAdmin();toast(t('confirmed'));}}catch(error){errorToast(error);}});
document.addEventListener('click',async e=>{
 const b=e.target.closest('button,[data-node],[data-select]');if(!b)return;if(performance.now()<ignoreMapClickUntil&&b.closest('#city-map'))return;
 try{
  if(b.dataset.panel){ui.dialog=null;ui.panel=b.dataset.panel;ui.search='';ui.filter='all';render();return;}
  if(b.dataset.filter){ui.filter=b.dataset.filter;render();return;}
  if(b.dataset.select){ui.selected={kind:b.dataset.select,id:b.dataset.id};ui.layerMenu=false;render();return;}
  if(b.dataset.view){resetWorkspace();if(b.dataset.view==='citizen'){if(user?.role!=='citizen'){await api('/auth/logout',{method:'POST'});await api('/auth/guest',{method:'POST'});await identity();connect();}view='citizen';await refresh();await findRoute();}else if(operator()){view='dispatcher';render();}else if(can('assignment:read')){view='responder';render();}else{ui.dialog='login';render();}return;}
  if(b.dataset.login){await signIn('demo-'+b.dataset.login,'demo');return;}
  if(b.dataset.node){const n=state.map.nodes.find(n=>n.id===b.dataset.node);origin={lat:n.lat,lng:n.lng};ui.chooseLocation=false;await findRoute();return;}
  if(b.dataset.road){const r=state.roads.find(r=>r.id===b.dataset.road);await api('/roads/'+r.id,{method:'PATCH',body:JSON.stringify({enabled:!r.blocked})});await refresh();return;}
  if(b.dataset.sos){await sendSOS(b.dataset.sos);return;}
  if(b.dataset.support){await sendSOS(b.dataset.type,b.dataset.support);return;}
  if(b.dataset.alert){await api(`/alerts/${b.dataset.alert}/${b.dataset.command}`,{method:'POST'});toast(t('confirmed'));await refresh();return;}
  if(b.dataset.occupancy){const s=state.shelters.find(s=>s.id===b.dataset.occupancy);await api(`/shelters/${s.id}/occupancy`,{method:'PATCH',body:JSON.stringify({occupancy:Math.ceil(s.capacity*Number(b.dataset.percent)/100),source:'manual'})});await refresh();return;}
  if(b.dataset.team){await api('/teams/'+b.dataset.team,{method:'PATCH',body:JSON.stringify({status:b.dataset.status})});await refresh();return;}
  if(b.dataset.scenario){const k=b.dataset.scenario;await api('/demo/'+k,{method:'POST',body:JSON.stringify({enabled:k==='sos_wave'?true:!state.failures?.[k]})});await refresh();return;}
  switch(b.dataset.action){
   case'login':ui.dialog='login';render();break;
   case'close-modal':ui.dialog=null;render();break;
   case'logout':resetWorkspace();await api('/auth/logout',{method:'POST'});closeSocket();await api('/auth/guest',{method:'POST'});await identity();await refresh();connect();await findRoute();break;
   case'route':await findRoute();break;
   case'zoom-in':ui.zoom=Math.min(3,ui.zoom+.25);render();break;
   case'zoom-out':ui.zoom=Math.max(.75,ui.zoom-.25);render();break;
   case'close-detail':ui.selected=null;render();break;
   case'layers':ui.layerMenu=!ui.layerMenu;render();break;
   case'clear-search':ui.search='';render();break;
   case'map':ui.selected=null;ui.panel=null;render();break;
   case'reset-map':ui.pan={x:0,y:0};ui.zoom=1;render();break;
   case'choose-location':ui.chooseLocation=!ui.chooseLocation;ui.selected=null;render();break;
   case'edit-roads':if(can('road:write'))ui.editRoads=!ui.editRoads;ui.selected=null;render();break;
   case'stop-edit':ui.chooseLocation=false;ui.editRoads=false;render();break;
   case'sos':ui.dialog='sos';render();break;
   case'lab':if(can('demo:write')){ui.dialog='lab';render();}break;
   case'admin':if(can('role:write')){ui.dialog='admin';await loadAdmin();}break;
   case'about':ui.dialog='about';render();break;
   case'admin-refresh':await loadAdmin();break;
   case'sync':await flush();if(pending.length)toast(t('pendingLogin'));break;
   case'safe':if(connection==='offline'||pending.length){toast(t('offlineSafe'));break;}await api('/me/safe',{method:'POST'});toast(t('safeDone'));await refresh();break;
   case'gps':navigator.geolocation.getCurrentPosition(p=>{origin={lat:p.coords.latitude,lng:p.coords.longitude};findRoute();},()=>toast(t('chooseMap')),{timeout:8000});break;
  }
 }catch(error){errorToast(error);}
});
window.addEventListener('online',()=>{refresh();connect();});window.addEventListener('offline',()=>{closeSocket();setConnection('offline');});
bootstrap().catch(errorToast);

document.addEventListener('input',event=>{if(event.target.id==='workspace-search'){ui.search=event.target.value;render();}});
document.addEventListener('keydown',event=>{
 const dialog=document.querySelector('[role="dialog"]');
 if(event.key==='Escape'){ui.dialog=null;ui.selected=null;ui.layerMenu=false;ui.chooseLocation=false;ui.editRoads=false;render();return;}
 if(dialog&&event.key==='Tab'){
   const items=[...dialog.querySelectorAll('button:not([disabled]),input,select,[tabindex="0"]')].filter(el=>el.getClientRects().length);
   if(!items.length)return;
   const first=items[0],last=items[items.length-1];
   if(event.shiftKey&&(document.activeElement===first||!dialog.contains(document.activeElement))){event.preventDefault();last.focus();}
   else if(!event.shiftKey&&(document.activeElement===last||!dialog.contains(document.activeElement))){event.preventDefault();first.focus();}
 }
 if(event.target.matches('#city-map [role="button"]')&&['Enter',' '].includes(event.key)){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
 if(event.target.id==='city-map'){
   if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','+','-','='].includes(event.key)){event.preventDefault();
     if(event.key==='ArrowUp')ui.pan.y-=45/ui.zoom;if(event.key==='ArrowDown')ui.pan.y+=45/ui.zoom;
     if(event.key==='ArrowLeft')ui.pan.x-=45/ui.zoom;if(event.key==='ArrowRight')ui.pan.x+=45/ui.zoom;
     if(['+','='].includes(event.key))ui.zoom=Math.min(3,ui.zoom+.25);if(event.key==='-')ui.zoom=Math.max(.75,ui.zoom-.25);
     ui.pan.x=Math.max(-400,Math.min(400,ui.pan.x));ui.pan.y=Math.max(-300,Math.min(300,ui.pan.y));render();
   }
 }
});
let drag=null;
document.addEventListener('pointerdown',event=>{
 const svg=event.target.closest('#city-map');
 if(!svg||event.target.closest('[data-select],[data-node]')||event.button!==0)return;
 const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());
 drag={id:event.pointerId,svg,point,pan:{...ui.pan},x:event.clientX,y:event.clientY,moved:false};svg.setPointerCapture(event.pointerId);
});
document.addEventListener('pointermove',event=>{
 if(!drag||drag.id!==event.pointerId)return;
 if(Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<5&&!drag.moved)return;
 drag.moved=true;
 const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(drag.svg.getScreenCTM().inverse());
 ui.pan.x=Math.max(-400,Math.min(400,ui.pan.x+drag.point.x-point.x));
 ui.pan.y=Math.max(-300,Math.min(300,ui.pan.y+drag.point.y-point.y));
 drag.svg.setAttribute('viewBox',mapView(ui));
});
function endDrag(){if(drag?.moved)ignoreMapClickUntil=performance.now()+250;drag=null;}
document.addEventListener('pointerup',endDrag);document.addEventListener('pointercancel',endDrag);
document.addEventListener('wheel',event=>{if(!event.target.closest('#city-map'))return;event.preventDefault();ui.zoom=Math.max(.75,Math.min(3,ui.zoom+(event.deltaY<0?.15:-.15)));document.getElementById('city-map').setAttribute('viewBox',mapView(ui));},{passive:false});
