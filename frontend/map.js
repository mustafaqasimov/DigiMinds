import {addBase} from './map-base.js';
import {LEVEL_COLORS} from './events-i18n.js';
let map,overlays,base,context,lastSelection,container;
export function renderMap({t}){return `<div id="city-map" class="real-map" aria-label="${t('mapTitle')}" tabindex="0"></div>`;}
export function mountMap(c,{onLocation}){
 const L=window.L;if(!L)return;
 context=c;
 const element=document.getElementById('city-map');if(!element)return;
 if(!map||container!==element){
  if(map){base?.dispose();map.remove();}
  container=element;
  map=L.map(element,{zoomControl:false,attributionControl:true,minZoom:11,maxZoom:19,zoomSnap:.5}).setView([40.374,49.847],15);
  base=addBase(map,{offline:!!c.ui.offlineMap,onStatus:status=>{element.dataset.mapStatus=status;queueMicrotask(()=>document.dispatchEvent(new CustomEvent('map-status',{detail:{status}})));}});
  overlays=L.layerGroup().addTo(map);
  L.control.scale({imperial:false,position:'bottomleft'}).addTo(map);
  map.on('click',event=>{if(context.ui.chooseLocation)onLocation(event.latlng);});
 }
 base.setOffline(!!c.ui.offlineMap);map.invalidateSize({pan:false});overlays.clearLayers();
 const {state,ui,route,origin,view,esc,icon,t}=c,isCitizen=view==='citizen',lookup=Object.fromEntries(state.map.nodes.map(n=>[n.id,n]));
 const pos=n=>[n.lat,n.lng];
 function select(kind,id){document.dispatchEvent(new CustomEvent('map-select',{detail:{kind,id}}));}
 function pin(kind,id,point,color,glyph,label,sub){
  if(!point)return;
  const html=`<button class="geo-pin ${ui.selected?.id===id?'selected':''}" style="--pin-color:${color}" data-select="${kind}" data-id="${esc(id)}" aria-label="${esc(label)}${sub?' · '+esc(sub):''}"><span>${icon(glyph)}</span>${sub?`<b>${esc(sub)}</b>`:''}</button>`;
  L.marker(pos(point),{icon:L.divIcon({className:'geo-marker',html,iconSize:[48,63],iconAnchor:[24,24]}),keyboard:false}).addTo(overlays);
 }
 if(ui.layers.zones){
  const b=state.map.bounds||[49.828,40.365,49.856,40.38],mid=(b[0]+b[2])/2;
  L.rectangle([[b[1],b[0]],[b[3],mid]],{color:'#c58240',weight:1,dashArray:'5 6',fillColor:'#f8c86e',fillOpacity:.07,interactive:false}).addTo(overlays);
  L.rectangle([[b[1],mid],[b[3],b[2]]],{color:'#437f9a',weight:1,dashArray:'5 6',fillColor:'#82c4dc',fillOpacity:.05,interactive:false}).addTo(overlays);
 }
 for(const r of state.roads){if(!r.blocked&&!ui.editRoads)continue;const a=lookup[r.a],b=lookup[r.b];if(!a||!b)continue;L.polyline([pos(a),pos(b)],{color:r.blocked?'#e04a39':'#f48427',weight:r.blocked?6:4,dashArray:r.blocked?'7 7':null,opacity:r.blocked?1:.5}).on('click',()=>select('road',r.id)).addTo(overlays);}
 if(isCitizen&&route?.geometry?.length)L.polyline(route.geometry.map(([lng,lat])=>[lat,lng]),{color:'#3b6ed8',weight:5,opacity:.9,dashArray:state.map.dataset?.includes('synthetic')?'8 7':null,interactive:false}).addTo(overlays);
 if(ui.layers.shelters)for(const s of state.shelters)pin('shelter',s.id,lookup[s.node],s.status!=='open'?'#919b91':s.percent>95?'#ce4e36':s.percent>=90?'#c18c18':'#2d936f','home',s.name,s.status==='standby'?t('standby'):Math.round(s.percent)+'%');
 if(ui.layers.teams&&!isCitizen)for(const team of state.teams||[])pin('team',team.id,lookup[team.node],team.status==='available'?'#557795':'#3e68c0','team',team.name,'');
 if(ui.layers.incidents)for(const i of state.incidents||[]){if(!i.lat||i.status==='resolved'||!(i.active_count>0||ui.selected?.id===i.id))continue;L.circle([i.lat,i.lng],{radius:180,color:'#e77135',weight:1,fillColor:'#f79759',fillOpacity:.1,dashArray:'4 5',interactive:false}).addTo(overlays);pin('incident',i.id,i,'#e36629',i.type,t(i.type),i.count+' SOS');}
 if(ui.layers.events)for(const e of state.events||[]){
  if(!e.lat||e.phase==='ended')continue;
  const chosen=ui.selected?.kind==='event'&&ui.selected.id===e.id,color=e.worst>100?'#ce4e36':e.worst>=70?'#d9772b':'#7b5cc4';
  // Crowd footprint grows with the square root of attendance (12 000 people ≈ 330 m).
  L.circle([e.lat,e.lng],{radius:Math.sqrt(e.attendance)*3,color,weight:1.5,dashArray:e.phase==='upcoming'?'6 6':null,fillColor:color,fillOpacity:e.phase==='live'?.16:.07,interactive:false}).addTo(overlays);
  if(chosen)for(const r of e.shelters){const s=state.shelters.find(x=>x.id===r.id),p=s&&lookup[s.node];if(p)L.polyline([[e.lat,e.lng],pos(p)],{color:LEVEL_COLORS[r.level],weight:3,dashArray:'4 6',interactive:false}).bindTooltip(`+${r.incoming} · ${Math.round(r.potential_percent)}%`,{permanent:true,direction:'center',className:'event-flow-label'}).addTo(overlays);}
  pin('event',e.id,e,color,'ticket',e.name,(e.attendance>=1000?Math.round(e.attendance/1000)+'k':e.attendance)+'');
 }
 if(isCitizen){L.circleMarker([origin.lat,origin.lng],{radius:9,color:'white',weight:4,fillColor:'#316cdb',fillOpacity:1}).bindTooltip(t('currentLocation'),{direction:'bottom'}).addTo(overlays);}
 if(ui.selected&&lastSelection!==ui.selected.id){const item=ui.selected.kind==='shelter'?state.shelters.find(s=>s.id===ui.selected.id):ui.selected.kind==='team'?(state.teams||[]).find(s=>s.id===ui.selected.id):ui.selected.kind==='incident'?(state.incidents||[]).find(s=>s.id===ui.selected.id):ui.selected.kind==='event'?(state.events||[]).find(s=>s.id===ui.selected.id):null;const point=item?.node?lookup[item.node]:item;if(point?.lat)map.panTo(pos(point));lastSelection=ui.selected.id;}
}
export function mapCommand(command){if(!map)return;if(command==='zoom-in')map.zoomIn();if(command==='zoom-out')map.zoomOut();if(command==='reset-map')map.setView([40.374,49.847],15);}
