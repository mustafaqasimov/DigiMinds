const labels={
 az:{navigation:'Əsas menyu',map:'Xəritə',profile:'Təhlükəsizlik profilim',vision:'YOLO analiz',demo:'Jüri demosu'},
 en:{navigation:'Main navigation',map:'Map',profile:'Safety profile',vision:'YOLO analysis',demo:'Jury demo'},
 ru:{navigation:'Главное меню',map:'Карта',profile:'Профиль безопасности',vision:'YOLO анализ',demo:'Демо'}
};

export function productHeader({active,lang='az',demo=true}={}){
 const t=labels[lang]||labels.az;
 const links=[['map','/workspace.html'],['profile','/workspace.html#profile'],['vision','/vision.html'],...(demo?[['demo','/presentation.html']]:[])];
 return `<header class="dm-header"><a class="dm-brand" href="/" aria-label="DigiMinds"><span class="dm-brand-mark" aria-hidden="true"></span>DIGIMINDS</a><nav class="dm-nav" aria-label="${t.navigation}">${links.map(([key,url])=>`<a href="${url}"${key===active?' aria-current="page"':''}>${t[key]}</a>`).join('')}</nav></header>`;
}
