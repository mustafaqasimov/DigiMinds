import {productHeader} from './product-ui.js';
const $=id=>document.getElementById(id);
const errors={vision_not_installed:'YOLO hazır deyil. Layihə qovluğunda YOLO_BASLAT.cmd faylını aç.',vision_busy:'Hazırda başqa video analiz olunur. Bir az sonra yenidən başlat.',vision_upload_too_large:'Video 100 MB-dan böyükdür.',vision_video_only:'MP4, MOV, WebM və ya AVI video seç.',vision_invalid_filename:'Videonun adını sadələşdirib yenidən seç.',vision_empty_video:'Seçilmiş fayl boşdur.',vision_invalid_video:'Video oxunmadı. İşlək MP4 video ilə yenidən yoxla.',vision_incomplete_video:'Videonun bəzi kadrları oxunmadı. Faylı yenidən MP4 kimi saxlayıb yoxla.',vision_resolution_limit:'Maksimum Full HD video seç: 1920 × 1080 və ya 1080 × 1920.',vision_duration_limit:'Video ən çox 60 saniyə və 60 FPS olmalıdır.',vision_timeout:'Analiz vaxt limitini keçdi. Daha qısa video ilə yenidən yoxla.',vision_upload_timeout:'Yükləmə çox uzun çəkdi. Bağlantını yoxlayıb yenidən cəhd et.',vision_failed:'Analiz tamamlana bilmədi. Server pəncərəsini yoxla və yenidən cəhd et. İlk analizdə modelin yüklənməsi üçün internet lazımdır.',vision_encoding_failed:'Nəticə videosu yaradıla bilmədi. YOLO_BASLAT.cmd ilə paketləri yoxla.',vision_not_found:'Nəticə artıq əlçatan deyil. Videonu yenidən yüklə.',authentication_required:'Sessiya bitib. Yenidən daxil ol.',permission_denied:'Bu hesabın video analizi icazəsi yoxdur.',invalid_credentials:'İstifadəçi adı və ya şifrə yanlışdır.',rate_limited:'Çox sayda sorğu göndərilib. Bir az sonra yenidən yoxla.'};
const states={queued:'Növbədə',loading:'Model hazırlanır',processing:'Analiz gedir',encoding:'Video hazırlanır',completed:'Analiz tamamlandı',cancelled:'Dayandırıldı',failed:'Analiz alınmadı'};
let config=null,authorized=false,file=null,sourceURL=null,jobId=null,busy=false,timer=null,generation=0;
function notice(message=''){$('notice').hidden=!message;$('notice').textContent=message;}
function errorMessage(error){return errors[error.message]||error.message||'Bağlantı alınmadı. Serverin açıq olduğunu yoxla.';}
async function api(path,options={}){
 const response=await fetch(path,{...options,headers:{'X-Requested-With':'DigiMinds',...options.headers}});
 const body=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(body.detail||(response.status===413?'vision_upload_too_large':response.status===401?'authentication_required':`Server xətası (${response.status})`));
 return body;
}
function controls(){
 $('analyze').disabled=busy||!file||!authorized||!config?.available;
 $('video-file').disabled=busy;$('remove-file').disabled=busy;
 $('cancel').hidden=!busy||!jobId;
}
function showView(kind){for(const id of ['empty-view','source-video','live-preview','result-video'])$(id).hidden=id!==kind;}
function resetResults(){
 for(const id of ['count-current','count-mean','count-max','frame-count'])$(id).textContent='—';
 $('current-label').textContent='Cari kadr';$('result-actions').hidden=true;$('progress-panel').hidden=true;
 $('result-video').pause();$('result-video').removeAttribute('src');$('result-video').load();
 $('state-badge').className='state-badge';$('state-badge').textContent=file?'Analizə hazır':'Video gözlənilir';
}
function chooseFile(selected){
 if(busy||!selected)return;
 if(!/\.(mp4|mov|webm|avi)$/i.test(selected.name)){notice(errors.vision_video_only);return;}
 if(!selected.size||selected.size>(config?.max_upload_bytes||104857600)){notice(selected.size?errors.vision_upload_too_large:errors.vision_empty_video);return;}
 notice();clearTimeout(timer);generation++;jobId=null;sessionStorage.removeItem('dm-vision-job');file=selected;
 if(sourceURL)URL.revokeObjectURL(sourceURL);sourceURL=URL.createObjectURL(file);
 $('source-video').src=sourceURL;$('selected-file').hidden=false;$('file-name').textContent=file.name;
 $('file-detail').textContent=`${(file.size/1048576).toFixed(1)} MB`;
 resetResults();showView('source-video');$('viewer-label').hidden=false;$('viewer-label').textContent='SEÇİLMİŞ VİDEO';controls();
}
$('source-video').addEventListener('loadedmetadata',()=>{
 const v=$('source-video');if(!file)return;
 $('file-detail').textContent=`${(file.size/1048576).toFixed(1)} MB · ${v.duration.toFixed(1)} san. · ${v.videoWidth} × ${v.videoHeight}`;
 if(v.duration>60.05||v.videoWidth*v.videoHeight>1920*1080||Math.max(v.videoWidth,v.videoHeight)>1920){notice(v.duration>60.05?errors.vision_duration_limit:errors.vision_resolution_limit);file=null;controls();}
});
$('source-video').addEventListener('error',()=>{if(file)notice('Brauzer bu videonu göstərə bilmir. Fayl işləkdirsə, yenə də analizə göndərə bilərsən.');});
$('video-file').addEventListener('change',event=>chooseFile(event.target.files[0]));
for(const type of ['dragenter','dragover'])$('dropzone').addEventListener(type,event=>{event.preventDefault();if(!busy)$('dropzone').classList.add('dragging');});
for(const type of ['dragleave','drop'])$('dropzone').addEventListener(type,event=>{event.preventDefault();$('dropzone').classList.remove('dragging');if(type==='drop')chooseFile(event.dataTransfer.files[0]);});
$('remove-file').addEventListener('click',()=>{file=null;$('video-file').value='';$('selected-file').hidden=true;$('source-video').pause();$('source-video').removeAttribute('src');$('source-video').load();if(sourceURL)URL.revokeObjectURL(sourceURL);sourceURL=null;$('viewer-label').hidden=true;showView('empty-view');resetResults();controls();notice();});
function progress(title,percent,detail=''){$('progress-panel').hidden=false;$('progress-title').textContent=title;$('progress').value=percent;$('progress-value').textContent=`${percent}%`;$('progress-detail').textContent=detail;}
function renderJob(job){
 $('state-badge').textContent=states[job.state]||job.state;
 $('state-badge').className='state-badge'+(job.state==='completed'?' done':!['failed','cancelled'].includes(job.state)?' active':'');
 $('count-current').textContent=job.count??'—';$('frame-count').textContent=job.frames_processed||'—';
 progress(states[job.state]||'Analiz hazırlanır',job.progress||0,job.total_frames?`${job.frames_processed} / ${job.total_frames} kadr`:'İlk açılışda modelin yüklənməsi bir az vaxt ala bilər.');
 if(job.frames_processed>0&&job.state!=='completed'){
  $('live-preview').src=`/api/vision/jobs/${job.id}/preview?t=${job.frames_processed}`;
  showView('live-preview');$('viewer-label').hidden=true;
 }
 if(job.state==='completed'){
  const s=job.summary;busy=false;$('current-label').textContent='Son kadr';$('count-mean').textContent=s.count_mean;$('count-max').textContent=s.count_max;
  $('result-video').src=`/api/vision/jobs/${job.id}/video`;$('result-video').poster=`/api/vision/jobs/${job.id}/preview`;
  showView('result-video');$('viewer-label').hidden=true;$('result-actions').hidden=false;
  $('download-video').href=`/api/vision/jobs/${job.id}/video?download=true`;
  $('download-report').href=`/api/vision/jobs/${job.id}/report?download=true`;
  $('completed-detail').textContent=`${s.duration_seconds} san. video · ${s.elapsed_seconds} san. emal · səssiz nəticə`;
  progress('Bütün kadrlar analiz edildi',100,`${s.frames_processed} kadr · ən az ${s.count_min}, ən çox ${s.count_max} nəfər`);
  if(s.warnings?.length)notice('Bəzi kadrlarda aşkarlama limitinə çatılıb. Say natamam ola bilər.');
 }else if(job.state==='failed'||job.state==='cancelled'){
  busy=false;sessionStorage.removeItem('dm-vision-job');
  if(job.state==='failed')notice(errors[job.error]||errors.vision_failed);
 }
 controls();
}
async function poll(id,version){
 if(version!==generation)return;
 try{const job=await api(`/api/vision/jobs/${id}`);if(version!==generation)return;renderJob(job);
  if(!['completed','failed','cancelled'].includes(job.state))timer=setTimeout(()=>poll(id,version),1800);
 }catch(error){
  if(version!==generation)return;notice(errorMessage(error));
  if(['authentication_required','permission_denied','vision_not_found'].includes(error.message)){busy=false;sessionStorage.removeItem('dm-vision-job');controls();if(error.message==='authentication_required'){authorized=false;await checkAccess();}}
  else timer=setTimeout(()=>poll(id,version),4000);
 }
}
function upload(selected){return new Promise((resolve,reject)=>{
 const xhr=new XMLHttpRequest();xhr.open('POST',`/api/vision/jobs?filename=${encodeURIComponent(selected.name)}`);xhr.setRequestHeader('X-Requested-With','DigiMinds');xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.timeout=120000;
 xhr.upload.onprogress=event=>{if(event.lengthComputable)progress('Video yüklənir',Math.round(event.loaded/event.total*100),'Yükləmə tamamlandıqda analiz başlayacaq.');};
 xhr.onload=()=>{let body={};try{body=JSON.parse(xhr.responseText);}catch{}if(xhr.status>=200&&xhr.status<300)resolve(body);else reject(new Error(body.detail||(xhr.status===413?'vision_upload_too_large':xhr.status===401?'authentication_required':'vision_failed')));};
 xhr.onerror=()=>reject(new Error('Serverlə bağlantı kəsildi. Bağlantını yoxlayıb yenidən cəhd et.'));xhr.ontimeout=()=>reject(new Error('vision_upload_timeout'));xhr.send(selected);
});}
$('analyze').addEventListener('click',async()=>{
 if(!file||busy)return;notice();busy=true;jobId=null;generation++;const version=generation;clearTimeout(timer);resetResults();controls();$('source-video').pause();progress('Video yüklənir',0);$('state-badge').textContent='Yüklənir';
 try{const job=await upload(file);jobId=job.id;sessionStorage.setItem('dm-vision-job',job.id);renderJob(job);poll(job.id,version);}
 catch(error){busy=false;notice(errorMessage(error));$('state-badge').textContent='Yükləmə alınmadı';controls();if(error.message==='authentication_required')await checkAccess();}
});
$('cancel').addEventListener('click',async()=>{if(!jobId)return;$('cancel').disabled=true;try{const job=await api(`/api/vision/jobs/${jobId}`,{method:'DELETE'});clearTimeout(timer);generation++;renderJob(job);}catch(error){notice(errorMessage(error));}finally{$('cancel').disabled=false;}});
async function checkAccess(){
 try{const me=await api('/api/auth/me');authorized=me.permissions?.includes('dashboard:read')||false;}catch{authorized=false;}
 $('access').hidden=authorized;$('demo-login').hidden=!config?.demo;$('login-form').hidden=!!config?.demo;controls();
}
async function login(username,password){
 notice();try{await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,cookie_session:true})});await checkAccess();if(!authorized)notice(errors.permission_denied);else restore();}catch(error){notice(errorMessage(error));}
}
$('demo-login').addEventListener('click',async()=>{$('demo-login').disabled=true;await login('demo-dispatcher','demo');$('demo-login').disabled=false;});
$('login-form').addEventListener('submit',async event=>{event.preventDefault();const data=new FormData(event.target);await login(data.get('username'),data.get('password'));});
function restore(){const saved=sessionStorage.getItem('dm-vision-job');if(saved&&authorized&&!busy){jobId=saved;busy=true;generation++;controls();poll(saved,generation);}}
async function init(){
 try{config=await api('/api/vision/status');$('product-header').innerHTML=productHeader({active:'vision',demo:config.demo});$('setup').hidden=config.available;await checkAccess();restore();}
 catch(error){notice(errorMessage(error));}
}
$('check-setup').addEventListener('click',init);
$('product-header').innerHTML=productHeader({active:'vision'});
window.addEventListener('pagehide',()=>clearTimeout(timer));
window.addEventListener('pageshow',event=>{if(event.persisted&&jobId&&busy){generation++;poll(jobId,generation);}});
init();
