// Paired short beeps, separated by silence: the jury's audible "dut-dut" cue.
export function pulseSchedule(seconds){
 const end=Math.max(0,Math.min(60,Number.isFinite(seconds)?seconds:0)),pulses=[];
 for(let cycle=0;cycle<end;cycle+=1.2){
  for(const offset of [0,.3]){const start=cycle+offset;if(start<end)pulses.push({start,end:Math.min(end,start+.18)});}
 }
 return pulses;
}
