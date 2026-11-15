const VERSION='digiminds-v4-landing-real-map-r2';
const SHELL=['/','/index.html','/workspace.html','/landing.css','/landing.js','/map-base.js','/baku.geojson','/vendor/leaflet.js','/vendor/leaflet.css','/style.css','/app.js','/ui.js','/ui-i18n.js','/map.js','/fonts.css','/offline.js','/i18n.js','/demo-map.json','/icon.svg','/manifest.webmanifest'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(VERSION).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
 const u=new URL(event.request.url);
 // Never cache identities, private dashboards or mutation responses.
 if(event.request.method!=='GET'||u.origin!==self.location.origin||u.pathname.startsWith('/api')||u.pathname==='/ws')return;
 event.respondWith(fetch(event.request).catch(()=>caches.match(event.request).then(r=>r||(event.request.mode==='navigate'?caches.match(u.pathname==='/workspace.html'?'/workspace.html':'/'):Response.error()))));
});
