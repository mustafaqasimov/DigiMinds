# Saytdan YOLO video analizi

## İstifadə

1. Reponun son versiyasını endirib ZIP-dən tam çıxarın.
2. Windows-da `YOLO_BASLAT.cmd` açın. Python, tələb olunan paketlər və YOLO26n modeli ilk dəfə internetdən quraşdırılır. Sonrakı açılışlar quraşdırılmış paketləri və modeli istifadə edir.
3. Açılan `/vision.html` səhifəsində **Təlim hesabı ilə daxil ol** düyməsini seçin. Artıq operator hesabına daxil olmusunuzsa bu addım göstərilmir. Production rejimində mövcud operator hesabınızla daxil olun.
4. **Video seç** sahəsinə klikləyin və ya faylı sürükləyin. **Analizi başlat** düyməsini basın.
5. Gedişi, son analiz kadrını və aşkarlanan sayı izləyin. Tamamlandıqda videonu səhifədə oynadın, **Videonu endir** və ya **JSON hesabatı** seçin.

Linux/macOS: `python tools/start.py --vision`. Hazır mühitdə alternativ olaraq `python -m pip install -r requirements-vision.txt`, sonra `python tools/dev.py` və `/vision.html` istifadə edin. Modeli əvvəlcədən endirin; xidmətin çəkiləri fərqli qovluqdadırsa `VISION_MODEL_PATH` lokal YOLO26n yolunu qəbul edir.

## Nə ölçülür?

- Standart YOLO26n, 960 giriş ölçüsü, 0.25 etibar həddi, COCO `person` sinfi, hər kadr, CPU-da 4 PyTorch thread.
- Hər kadrdakı aşkarlamalar ayrıca sayılır. Kadrlar üzrə say toplanmır; unikal ziyarətçi, üz tanıma və ya giriş-çıxış izləmə aparılmır.
- Son kadrın sayı, orta say, maksimum say, emal olunan kadr sayı və emal müddəti göstərilir.
- Nəticə H.264 MP4-dür, səssizdir və mənbə videonun sürətində oynayır. Bu oynatma sürəti modelin canlı emal sürəti demək deyil.
- Fiziki sahə ölçülməyib: sıxlıq `null` qalır. Veb sınağı real məntəqə doluluğunu yeniləmir. Kalibrasiyalı kamera/sensor göndərişi üçün ayrıca `vision.worker` var.
- Uzaq, qismən görünən və örtülmüş insanlar buraxıla bilər. Saylar etiketlənmiş həqiqi sayla müqayisə edilmədiyindən dəqiqlik faizi iddia edilmir.

## Limitlər və məlumatların saxlanması

MP4, MOV, WebM, AVI; 100 MiB; 60 saniyə; maksimum 1920×1080 və ya 1080×1920; 60 FPS; 3600 kadr. Faylın həqiqi video metadatası serverdə yoxlanılır. Boş, yararsız, həddən böyük və natamam oxunan fayl aydın xəta ilə dayandırılır.

Bir prosesli prototipdə eyni anda bir analiz; maksimum 10 dəqiqə emal vaxtı; yükləmə üçün 90 saniyə; istifadəçi üçün saatda 12 yükləmə cəhdi. Aktiv analiz dayandırıla bilər. API CPU inference və video kodlamasını ayrıca subprocess-də icra edir. Dayandırma və timeout proses ağacını bitirir; natamam fayllar təmizlənir. Yüklənmiş orijinal emal bitdikdə silinir.

Hər iş yükləyən hesabın ID-sinə bağlıdır və `dashboard:read` icazəsi tələb edir. Cookie əsaslı brauzer yükləmələri mövcud same-origin/CSRF qorumasından keçir. Yalnız dəqiq video endpoint-i 64 KiB JSON limitindən ayrılır: autentifikasiyadan sonra diskə axınla yazılır və bayt limiti yenidən tətbiq edilir. Fayl adları yol kimi istifadə edilmir. Nəticələr autentifikasiyalı `/api/vision/jobs/...` ünvanlarından `no-store` ilə verilir; statik frontend və service worker keşinə daxil olmur.

Ən çox 8 iş saxlanılır; köhnə tamamlanmış işlər yeni iş üçün silinə bilər. 1 saatdan sonra nəticə əlçatmaz olur və növbəti status/yükləmə sorğusunda diskdən təmizlənir. Server restartı əvvəlki işləri silir. Bu prototip **bir server prosesi** üçündür; eyni verilənlər qovluğuna birdən çox uvicorn worker başlamayın. Çox server üçün paylanmış növbə və obyekt saxlancı tələb olunur.

## Yoxlama — 15 noyabr 2026

Rəsmi Roboflow Supervision `people-walking.mp4` nümunəsinin 10 saniyəlik, 1920×1080, 25 FPS hissəsi real HTTP API müqaviləsi ilə yükləndi və YOLO26n ilə emal olundu:

- 250/250 kadr; hər kadrda 26–41 aşkarlama; orta 34.0; son kadr 31.
- Bu sınaqda model yüklənməsi, analiz və kodlama daxil 38.9 saniyə. Performans kompüterə görə dəyişir.
- Analiz zamanı yoxlanan health sorğularının ən uzunu 0.033 saniyə idi.
- 10.000 saniyəlik H.264 nəticəsi, 250 kadr, video byte-range sorğusu 206 ilə yoxlandı.
- Yararsız video rədd edildi; aktiv işin dayandırılması prosesi və müvəqqəti faylları təmizlədi.
- Avtomatik testlər autentifikasiya, CSRF, başqa hesabın nəticəyə girişinin bloklanması, böyük/chunked yükləmələr, paralel işin rəddi, saxlanma limiti və məzmun yoxlamalarını əhatə edir.

Mənbələr: [Supervision video nümunələri](https://supervision.roboflow.com/latest/assets/), [Starlette request streaming](https://www.starlette.io/requests/), [FileResponse və HTTP range](https://starlette.dev/responses/), [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg). `imageio-ffmpeg==0.8.1` Windows/Linux/macOS üçün ffmpeg icra faylını paketlə gətirir; YOLO çəkiləri və istifadəçi videoları Git-ə əlavə edilmir.
