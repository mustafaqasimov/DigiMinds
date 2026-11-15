// A server timestamp avoids relying on the handset clock. Bound every alarm.
export function alarmLifetime(event, serverTime) {
 if(!event?.simulated||event.cancelled||!Number.isFinite(event.expires_at)||!Number.isFinite(serverTime))return 0;
 return Math.max(0,Math.min(60,event.expires_at-serverTime))*1000;
}
export function rememberEvent(seen,id){return [...seen.filter(x=>x!==id),id].slice(-50);}
export function normalizeRoom(value){return value.trim().toUpperCase();}
