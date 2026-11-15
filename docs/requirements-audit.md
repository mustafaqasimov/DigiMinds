# Digital Challenge: əsas tapşırığın yoxlanması

15 noyabr 2026. Mənbə: komandanın təqdim etdiyi iki modul tələbi; kod, API və avtomatlaşdırılmış testlər üzrə yoxlama.

## Tələb → tətbiq → sübut

| Tələb | Prototipdə tətbiq | Yoxlama |
| --- | --- | --- |
| Koordinata görə ən yaxın uyğun toplanış məntəqəsi | Xəritədə başlanğıc seçimi/GPS; `/api/routes?lat=...&lng=...`; bağlı yolları çıxaran Dijkstra ilə yol məsafəsinə görə sıralama | `test_engine.py`, `offline.test.mjs` |
| Park, stadion, sığınacaq və cari doluluq | Xəritə və siyahıda insan sayı, tutum, faiz, ölçmə mənbəyi və vaxtı | `Store.snapshot`, `ui.js`, sensor müqaviləsi testləri |
| Bir seçimlə 4 növ SOS | Yanğın, dağıntı, su basması, tibbi yardım; eyni hadisəyə fərqli şəxslərin hesabatları +1 kimi birləşdirilir | `test_engine.py` idempotency, tip ayrılığı və +1 testləri |
| “Təhlükəsizəm” | Şəxsin aktiv yardım ehtiyacını bağlayır; daxil olmuş siqnalların tarixçəsi saxlanır | `test_safe_preserves_historical_signal_count` |
| Yol bağlananda alternativ marşrut | Yol idarəetməsi; WebSocket/polling yenilənməsindən sonra avtomatik marşrut hesablanması; bağlı kənarlar istifadə edilmir | `test_closed_road_never_in_path_and_all_closed_no_route`, browser script |
| 90% doluluqda avtomatik alternativ | `occupancy/capacity >= 0.90` məntəqəni yeni marşrutlardan çıxarır; digər açıq, həddən aşağı, çatımlı məntəqə seçilir | dəqiq 89.75%, 90%, 95%, 95.25% sərhəd testləri; browser script |
| 90%-də ehtiyat məntəqəni açmaq | Əlavə edilmiş sarı xəbərdarlıq; ən yaxın uyğun və yolu açıq ehtiyat məntəqə təklifi; bir kliklə açılma | `test_capacity_response.py`, `ui.test.mjs` |
| Dispetçer canlı paneli | Zona üzrə SOS hadisələri/sayları, məntəqələrin doluluğu, mövcud və göndərilmiş briqadalar; rol üzrə süzülmüş WebSocket və HTTP polling | `test_engine.py` WebSocket/RBAC; `ui.js` |
| 5 dəqiqə, eyni zona VƏ YA 500 m, ən az 4 SOS | Sürüşən 300 saniyə; zona və sərhədlərarası radius qaydaları; təkrar hesabat say artırmır | pəncərə sərhədi, rayon sərhədi və deduplikasiya testləri |
| Doluluq 95%-i keçdikdə qırmızı həyəcan | Dəqiq 95% sarı; yalnız `>95%` qırmızı; SOS şərti bundan müstəqildir | `test_thresholds_preparation_escalation_and_new_episode` |
| “Əlavə briqada göndər və yeni məntəqə aç” bir kliklə | Yeni `/api/alerts/{id}/respond`; iki resurs eyni tranzaksiyada ayrılır; çatışmayan resurs olduqda heç biri qismən icra edilmir | paralel klik, idempotency, resurs çatışmazlığı və RBAC testləri |
| Kəsintilərə uyğunlaşma | Xarici marşrut üçün circuit breaker, 4.5 s vaxt həddi, lokal/offline marşrut, görünən ehtiyat rejimi bildirişi | `test_routing_fallback.py`, `routing-fallback.test.mjs` |

## Düzəldilən boşluqlar

- Əvvəl 90%-də marşrut dəyişirdi, ehtiyat məntəqə açılması yalnız >95% kritik həyəcan və ya tədbir proqnozu üzərindən mümkün idi. İndi 90% xəbərdarlığı həm xəbərdarlıqlar panelində, həm məntəqənin detalında görünür.
- Əvvəl “briqada göndər” və “məntəqə aç” yalnız ayrı əməliyyatlar idi. İndi uyğun iki resurs olduqda birgə təsdiq də var. Ayrı əməliyyatlar da saxlanılıb; resurs çatışmazlığı göstərilir.
- Doluluq 90%-dən aşağı düşüb yenidən qalxanda yeni xəbərdarlıq ID-si yaranır. Köhnə əməliyyatın idempotency qeydi yeni müdaxiləni bloklamır. Eyni qayda müddəti bitib yenidən yaranan SOS dalğasına da tətbiq olunur.
- 90%-də açılmış ehtiyat məntəqə eyni dalğada >95%-ə keçəndə yenidən açılmır; yalnız çatışmayan briqada əməliyyatı icra edilir.
- İcra edilmiş resursların adları görünür. Bitmiş xəbərdarlıq yeni resurs ayıra bilməz; artıq icra edilmiş əməliyyatın təkrarı əvvəlki nəticəni qaytarır.
- Dolmuş və ya yolu bağlı ehtiyat məntəqə seçilmir. Briqada hadisənin hədəf tipinə uyğun seçilir. Məntəqəni açmaq köhnə doluluq ölçməsini süni şəkildə təzələmir.
- Vətəndaş məntəqə siyahısını açanda cari marşrut kartı da görünür.

## YOLO barədə dəqiq vəziyyət

YOLO video analizi və məntəqəyə sensor ölçməsi göndərən worker mövcuddur. Saytdan təsadüfi video yükləmək məntəqənin doluluğunu dəyişmir. Canlı doluluq üçün `vision.worker` konkret məntəqəyə bağlanmalı, `SENSOR_KEY`, `--shelter`, `--coverage full` və `--publish` verilməlidir. Tam sahəni əhatə etməyən görüntü ümumi məntəqə insan sayı kimi qəbul edilmir. Faiz `insan sayı / tutum × 100` ilə hesablanır. Bu yoxlamada sensorun API-yə ölçmə ötürməsi sınaqdan keçirilib; real kamera və YOLO modelinin sahədəki dəqiqliyi ölçülməyib.

## Jüri üçün sınaq

1. Bir brauzer sessiyasında vətəndaş xəritəsini, ayrıca sessiyada dispetçeri açın. Vətəndaşın başlanğıc nöqtəsi standart `40.37, 49.8385` olduqda ilkin marşrut Mərkəz Parkına gedir.
2. Dispetçerdə **Məntəqələr → Mərkəz Parkı** seçin. İnsan sayını **360 / 400** edin. Vətəndaşın marşrutu yenilənməli, dispetçerdə sarı 90% xəbərdarlığı görünməlidir.
3. **Yeni məntəqə aç** düyməsini basın. Açılan məntəqənin adı görünməli, məntəqə vətəndaş üçün marşrut namizədlərinə daxil olmalıdır. Bu mərhələdə briqada avtomatik göndərilmir.
4. İnsan sayını **240**, sonra **384** edin. Yeni qırmızı həyəcan yaranır. **Briqada göndər və məntəqə aç** ilə hər iki əməliyyatı bir dəfə icra edin.
5. Alternativ yoxlama: **Sınaqlar → 4 SOS dalğası**. Kritik siqnalı açın, resursları və təsdiq düymələrini yoxlayın. Bütün ehtiyat məntəqələr artıq açıqdırsa, yeni məntəqə ayrılmaması normaldır; boş resurs olmadığı yazılır.
6. Yol idarəetməsindən marşrut üzərində bir yolu bağlayın. Vətəndaşın marşrutunda həmin yol qalmamalıdır. Bütün yolları bağlamaq mümkün marşrut olmadığını göstərməlidir.

## Testlər və sərhədlər

- Yerli yoxlama: **165 Python testi keçdi, 2 test asılılıqlara görə buraxıldı; 47 JavaScript testi keçdi**. Buraxılan testlər OpenCV ilə video kodlama və ffmpeg/numpy audio işlənməsidir.
- `tools/verify_capacity.mjs`: iki ayrı brauzer konteksti, canlı 90% alternativ marşrut, ehtiyat məntəqə açılması, >95% birgə müdaxilə, təkrar klik, mobil ölçü və yol bağlanması. GitHub Actions-da ayrıca `capacity-browser` job-u var. Yerli mühit Chromium socket əməliyyatına icazə vermədiyindən brauzer sınağı yerli olaraq tamamlanmayıb; CI nəticəsi ayrıca yoxlanmalıdır.
- Əsas testlər: `python -m pytest -q` və `node --test tests/*.test.mjs`.
- Brauzer sınağı üçün Playwright və Chromium quraşdırılmış mühitdə: `node tools/verify_capacity.mjs`. İstəyə görə `DM_PYTHON`, `DM_CHROMIUM`, `DM_SCREENSHOT_DIR` istifadə edilir.
- Bu işlək **simulyasiya prototipidir**: yollar/toplanış məntəqələri sintetikdir, koordinat əhatəsi demo sahə ilə məhduddur. Şəhərin bütün rayonları üzrə rəsmi məntəqə və yol bazası yoxdur. Xarici marşrut API-si opsionaldır; lokal və simulyasiya endpointi tələb olunan alternativdir.
- 500 m qaydası hesabat koordinatlarını dairə mərkəzi kimi yoxlayır; bir-birindən uzaq hesabatları zəncirlə birləşdirmir. Hədd 4 fərqli qəbul edilmiş hesabat üçündür, 4 fərqli təhlükə növü tələb olunmur.
- Yeni subtasklar əvvəlcədən məlum deyil. Mövcud modullar və testlər kəsinti ssenarilərini genişləndirməyə imkan verir; gələcək hər subtaskın artıq yerinə yetirildiyi iddia edilmir.
