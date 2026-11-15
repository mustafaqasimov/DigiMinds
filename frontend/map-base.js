// Leaflet is vendored. OSM raster tiles are requested only for visible maps;
// offline use reads the bundled OSM extract, never a bulk tile download.
export const attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
let dataPromise;
export function offlineData(){return dataPromise??=fetch('/baku.geojson').then(r=>{if(!r.ok)throw Error('offline_map_unavailable');return r.json();});}
export function addBase(map,{offline=false,onStatus=()=>{}}={}){
 const L=window.L;
 const raster=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,minZoom:3,attribution,keepBuffer:1});
 if(!map.getPane('offlineBase'))map.createPane('offlineBase').style.zIndex='190';
 const vectors=L.layerGroup().addTo(map);
 let forced=null,errors=0,disposed=false,providerFailed=false,vectorLoad=null;
 function status(){onStatus(forced||!navigator.onLine?'offline':providerFailed?'fallback':'online');}
 function setOffline(value){if(forced!==value)providerFailed=false;forced=value;if(forced||!navigator.onLine||providerFailed){loadVectors();if(map.hasLayer(raster))map.removeLayer(raster);}else if(!map.hasLayer(raster))raster.addTo(map);status();}
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
 }).catch(()=>{if(forced||!navigator.onLine||providerFailed)onStatus('unavailable');});}
 raster.on('tileerror',()=>{if(++errors===3){providerFailed=true;loadVectors();if(map.hasLayer(raster))map.removeLayer(raster);onStatus('fallback');}});
 raster.on('tileload',()=>{errors=0;});
 const online=()=>{errors=0;providerFailed=false;setOffline(forced);};
 window.addEventListener('online',online);window.addEventListener('offline',online);setOffline(offline);
 return{setOffline,dispose(){disposed=true;window.removeEventListener('online',online);window.removeEventListener('offline',online);}};
}
