import {MapCircuit} from './map-circuit.js';
// Leaflet is vendored. OSM raster tiles are requested only for visible maps;
// offline use reads the bundled OSM extract, never a bulk tile download.
export const attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
let dataPromise;
export function offlineData(){return dataPromise??=fetch('/baku.geojson',{signal:AbortSignal.timeout(4000)}).then(r=>{if(!r.ok)throw Error('offline_map_unavailable');return r.json();}).catch(error=>{dataPromise=null;throw error;});}
export function addBase(map,{offline=false,onStatus=()=>{}}={}){
 const L=window.L;
 const raster=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,minZoom:3,attribution,keepBuffer:1});
 if(!map.getPane('offlineBase'))map.createPane('offlineBase').style.zIndex='190';
 const vectors=L.layerGroup().addTo(map);
 // Warm only our bundled local extract, so tile failure can reveal it promptly.
 offlineData().catch(()=>{});
 let forced=null,disposed=false,vectorLoad=null,vectorUnavailable=false,retryTimer=null,probeTimer=null,probeImage=null;
 const gate=new MapCircuit({onOpen:()=>{if(disposed)return;loadVectors();if(map.hasLayer(raster))map.removeLayer(raster);onStatus('fallback');scheduleProbe();}});
 function stopProbe(){clearTimeout(probeTimer);if(probeImage){probeImage.onload=null;probeImage.onerror=null;probeImage.src='';probeImage=null;}}
 function scheduleProbe(){clearTimeout(retryTimer);if(disposed||forced||!navigator.onLine)return;retryTimer=setTimeout(probe,Math.max(0,gate.retryAt-Date.now()));}
 function probe(){
  if(disposed||forced||!navigator.onLine||!gate.allowProbe())return;
  // Probe exactly one tile within the visible viewport; no offline tile prefetch.
  const z=Math.min(19,Math.max(3,Math.round(map.getZoom()))),p=map.project(map.getCenter(),z);
  const img=probeImage=new Image();
  const finish=ok=>{stopProbe();if(disposed)return;if(ok){gate.recovered();if(!forced&&navigator.onLine)raster.addTo(map);status();}else gate.fail('map_probe_failed');};
  img.onload=()=>finish(true);img.onerror=()=>finish(false);probeTimer=setTimeout(()=>finish(false),5000);
  img.src=`https://tile.openstreetmap.org/${z}/${Math.floor(p.x/256)}/${Math.floor(p.y/256)}.png`;
 }
 function status(){onStatus((forced||!navigator.onLine||gate.state!=='closed')&&vectorUnavailable?'unavailable':forced||!navigator.onLine?'offline':gate.state!=='closed'?'fallback':'online');}
 function setOffline(value){
  if(forced!==value){if(vectorUnavailable){vectorUnavailable=false;vectorLoad=null;}stopProbe();clearTimeout(retryTimer);if(!value)gate.recovered();}forced=value;
  if(forced||!navigator.onLine||gate.state!=='closed'){loadVectors();if(map.hasLayer(raster))map.removeLayer(raster);if(!forced)scheduleProbe();}
  else if(!map.hasLayer(raster))raster.addTo(map);
  status();
 }
 function loadVectors(){return vectorLoad??=offlineData().then(data=>{
  if(disposed)return;
  L.geoJSON(data,{pane:'offlineBase',style:f=>{const p=f.properties;
   if(p.kind==='water')return{color:'#9dcada',fillColor:'#a8d9e9',weight:1,fillOpacity:1};
   if(p.kind==='park')return{color:'#b6cda0',fillColor:'#c5dfad',weight:1,fillOpacity:1};
   if(p.kind==='building')return{color:'#d3c9be',fillColor:'#e1d9d0',weight:.5,fillOpacity:.8};
   const major=['primary','secondary','trunk'].includes(p.highway);
   return{color:major?'#eac677':p.highway==='footway'||p.highway==='pedestrian'?'#f4e9ce':'#fff',weight:major?5:2.2,opacity:1};
  },interactive:false}).addTo(vectors);
  const names=new Set();
  for(const f of data.features){const name=f.properties.name;if(!name||names.has(name)||!['primary','secondary','tertiary'].includes(f.properties.highway))continue;names.add(name);const points=f.geometry.coordinates,p=points[Math.floor(points.length/2)];L.marker([p[1],p[0]],{pane:'offlineBase',interactive:false,keyboard:false,icon:L.divIcon({className:'offline-street-label',html:String(name).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),iconSize:[130,16],iconAnchor:[65,8]})}).addTo(vectors);}
  map.attributionControl.addAttribution(attribution);
 }).catch(()=>{vectorUnavailable=true;if(forced||!navigator.onLine||gate.state!=='closed')onStatus('unavailable');});}
 raster.on('tileloadstart',event=>gate.watch(event.tile));
 raster.on('tileerror',()=>gate.fail('map_unavailable'));
 raster.on('tileload',event=>gate.loaded(event.tile));
 raster.on('tileunload',event=>gate.loaded(event.tile));
 const online=()=>{if(vectorUnavailable){vectorUnavailable=false;vectorLoad=null;}setOffline(forced);};
 window.addEventListener('online',online);window.addEventListener('offline',online);setOffline(offline);
 return{setOffline,dispose(){disposed=true;gate.clear();clearTimeout(retryTimer);stopProbe();window.removeEventListener('online',online);window.removeEventListener('offline',online);}};
}
