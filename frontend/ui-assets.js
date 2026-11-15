// Each feature loads its own CSS, including when opened from a new HTML entry.
// Revisioned URLs also recover installations with an older cached index.html.
export function loadFeatureStyle(file){
 const url=new URL(file,import.meta.url);url.searchParams.set('v','unified-4');
 let link=[...document.querySelectorAll('link[rel="stylesheet"]')].find(el=>new URL(el.href).pathname===url.pathname);
 if(link?.href===url.href)return;
 if(!link){link=document.createElement('link');link.rel='stylesheet';document.head.append(link);}
 link.href=url.href;
}
