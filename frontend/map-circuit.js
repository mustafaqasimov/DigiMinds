// A tile load error (including HTTP 503) or a 5 s stalled tile opens this gate.
export class MapCircuit {
 constructor({timeoutMs=5000,cooldownMs=30000,clock=()=>Date.now(),onOpen=()=>{}}={}){this.timeoutMs=timeoutMs;this.cooldownMs=cooldownMs;this.clock=clock;this.onOpen=onOpen;this.state='closed';this.retryAt=0;this.pending=new Map();}
 watch(tile){if(this.state!=='closed')return;this.loaded(tile);this.pending.set(tile,setTimeout(()=>this.fail('map_timeout'),this.timeoutMs));}
 loaded(tile){clearTimeout(this.pending.get(tile));this.pending.delete(tile);}
 clear(){for(const timer of this.pending.values())clearTimeout(timer);this.pending.clear();}
 fail(reason){if(this.state==='open')return;this.clear();this.state='open';this.retryAt=this.clock()+this.cooldownMs;this.onOpen(reason);}
 allowProbe(){if(this.state!=='open'||this.clock()<this.retryAt)return false;this.state='half_open';return true;}
 recovered(){this.clear();this.state='closed';this.retryAt=0;}
}
