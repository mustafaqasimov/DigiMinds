# DigiMinds · Urban Crisis & Crowd Evacuation Engine

Digital Challenge üçün işləyən FastAPI + WebSocket + offline web tətbiqi. Vətəndaş SOS-larını hadisələr üzrə birləşdirir, kritik zonaları müəyyən edir və dispetçerin müdaxiləsini qeydə alır.

**Bu versiyanın xəritəsi Bakı koordinatlarına yerləşdirilmiş sintetik təlim şəbəkəsidir. Küçələr, məntəqələr və tutumlar rəsmi məlumat deyil.** Lokal qraf real xəritə paketi ilə əvəz edilənədək real təxliyə üçün istifadə edilməməlidir.

![Dispetçer paneli — sintetik demo](docs/preview.jpg)

## Başlatmaq

Python 3.12+ tələb olunur. Frontend üçün npm paketi, CDN və xarici API açarı lazım deyil.

```bash
git clone https://github.com/mustafaqasimov/DigiMinds.git
cd DigiMinds
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python tools/dev.py
```

Brauzerdə `http://127.0.0.1:3000` açın. `http://127.0.0.1:3000/openapi.json` API sxemidir. `npm run dev` eyni launcher-i çağırır; Node yalnız JS testlərini işlətmək üçün lazımdır.

Demo rejimində **Dispetçer → demo hesab seçin**. Hesablar: `demo-dispatcher`, `demo-observer`, `demo-responder`, `demo-admin`; hər birinin demo şifrəsi `demo`-dur. Bunlar yalnız təlim rejimi üçündür. Vətəndaş sessiyası avtomatik yaranır.

## Hazır funksiyalar

| Hissə | Davranış |
| --- | --- |
| Vətəndaş | Xəritədən mövqe/GPS, uyğun məntəqələr, doluluq, piyada marşrutu, 4 SOS növü, “Təhlükəsizəm” |
| SOS +1 | Eyni növ, 180 m sabit hadisə mərkəzi, son 30 dəqiqədə yenilənən açıq hadisə; hər vətəndaş hadisədə bir dəfə sayılır |
| Qırmızı həyəcan | Son sürüşən 300 saniyədə eyni zonada **və ya** 500 m dairədə ≥4 fərqli qəbul edilmiş SOS; məntəqə doluluğu **>95%** |
| Yenidən marşrut | Bağlı yol qrafdan çıxarılır; doluluq **≥90%** olduqda məntəqə namizədlərdən çıxarılır; canlı vəziyyət dəyişəndə yenidən hesablanır |
| Dispetçer | Hadisə xəritəsi, saylar, briqadalar, 1 kliklə göndəriş və ehtiyat məntəqənin açılması; təkrar klik ikinci resurs ayırmır |
| Canlı məlumat | Autentifikasiyalı, rola görə süzülən WebSocket; əlaqə kəsilərsə 4 saniyəlik HTTP polling |
| Offline | Service Worker tətbiq/xəritə keşləyir; brauzer müstəqil Dijkstra hesablayır; SOS IndexedDB-də göndərilməmiş kimi saxlanır |
| Rollar | Vətəndaş, dispetçer, xilasedici, müşahidəçi, admin; admin icazələrdən yeni rol yarada və təyin edə bilir |
| Dillər | Azərbaycan, ingilis, rus dilləri |
| Challenge | 4 SOS dalğası, routing provider kəsilməsi, WebSocket kəsilməsi; laboratoriya yalnız demo rejimində |
| YOLO | Ayrı lokal sensor prosesi; person detection, ROI, kalibrasiya veriləndə nəfər/m², API-yə ölçmə göndərişi |

“4 fərqli SOS” burada 4 unikal hesabatdır; hadisənin `+1` sayğacı ilə ayrı saxlanır. Eyni vətəndaş müxtəlif hadisələr barədə ayrıca hesabat verə bilər. “Təhlükəsizəm” aktiv yardım sayını azaldır, daxil olmuş SOS tarixçəsini silmir. Radius qaydası yaxınlıqdakı SOS koordinatlarını dairə mərkəzləri kimi yoxlayır; tranzitiv DBSCAN zənciri istifadə edilmir.

## Vətəndaş təhlükəsizlik profili

Vətəndaş panelində **Təhlükəsizlik profilim** düyməsi və ya `/#profile` açın. Yaş, hərəkət/əlçatanlıq ehtiyacları, nəqliyyat, ailə və təcili əlaqəni ayrı kartlarda daxil edib saxlayın. Şəxsi hazırlıq siyahısı bu seçimlərə uyğun dəyişir. Paylaşma standart olaraq bağlıdır; razılıq veriləndə yalnız aktiv SOS-a baxan səlahiyyətli operator və təyin edilmiş briqada yardım profilini aça bilir.

Profil cari 8 saatlıq guest sessiyasına bağlıdır; sessiya itdikdə hesab bərpası yoxdur. Hələlik sınaq məlumatından istifadə edin. mygov inteqrasiyası və təsdiqlənmiş əlçatan marşrut əlavə edilməyib.

Dizayn mənbələri, API, testlər və məhdudiyyətlər: [citizen-profile.md](docs/citizen-profile.md).

## İki alternativ işləmə mexanizmi

1. **Xarici API-siz:** serverdə saxlanan yol qrafı və Dijkstra. Yol bağlanmaları və məntəqə yenilənmələri işləyir. Standart seçim budur.
2. **Server də əlçatmazdır:** əvvəl yüklənmiş tətbiq və xəritə, brauzerdə ayrıca Dijkstra, IndexedDB SOS növbəsi. Yeni bağlanmalar bilinmir; ekran köhnə məlumatı açıq bildirir. Yenidən qoşulanda yalnız eyni vətəndaş sessiyasına aid növbə göndərilir, idempotency açarı təkrarı önləyir.

Offline ilk açılışdan sonra və HTTPS/localhost üzərində işləyir. Brauzer məlumatları silinərsə keş və növbə də silinir. 8 saatlıq vətəndaş sessiyası bitərsə əvvəlki növbə başqa şəxs adından avtomatik göndərilmir. SMS/mesh rabitəsi bu versiyaya daxil deyil.

## YOLO

```bash
python -m pip install -r requirements-vision.txt
python -m vision.worker --source path/to/video.mp4 --model yolo11n.pt
```

GPU-suz quraşdırma üçün əvvəl PyTorch-un CPU paketlərini quraşdırmaq olar; `uv` varsa `uv pip install -r requirements-vision.txt --torch-backend cpu`. Model çəkisini ilk dəfə internetdən alır; sonra yerli `--model` yolu ilə offline işləyir. Mənbə lokal şəkil/video, kamera indeksi `0` və ya səlahiyyətli RTSP URL ola bilər. Ayrı sensor prosesi API-ni bloklamır.

Standart `partial` rejim yalnız ölçməni stdout-a verir. Kameranın bütün dolu sahəni əhatə etdiyi təsdiqlənəndən sonra:

```bash
# Eyni SENSOR_KEY server və sensor mühitinə verilməlidir.
python -m vision.worker --source path/to/video.mp4 --coverage full \
  --publish --shelter s1 --api http://127.0.0.1:3000 --area-m2 600
```

`--area-m2` real görünən sahədir, piksel sahəsi deyil. `--roi roi.json` üçün format `[[x,y],[x,y],[x,y],...]`; şəxs qutusunun alt mərkəzi poliqonda sayılır. Kadrlar üzrə saylar bir-birinin üstünə yığılmır. Natamam görünüş ümumi tutum faizinə çevrilmir. Sıx izdiham/örtülmə üzrə ayrıca kalibrasiya lazımdır; bu versiya giriş-çıxış turniket sayğacı və çoxkameralı şəxs deduplikasiyası etmir.

## Testlər

```bash
python -m pytest -q
node --test tests/offline.test.mjs
python tools/load_test.py --isolated
```

İzolyasiya edilmiş yük testi öz müvəqqəti HTTP serverini/DB-sini açıb bağlayır; nümayiş məlumatlarını dəyişmir. 1000 HTTP sorğusu, 24 şəxs, 40 paralel sorğu: 24 yeni SOS və 976 idempotent təkrar gözlənilir. Ayrı integration test 200 unikal şəxs + 200 təkrar göndərir. Canlı serverə test üçün `--isolated` əvəzinə `--base-url URL` istifadə edin; bu seçim həmin demo bazasına test məlumatı yazır. Nəticələr: [verification.md](docs/verification.md).

## Konfiqurasiya və təhlükəsizlik

`.env.example` dəyişənlərin nümunəsidir; tətbiq `.env` faylını avtomatik oxumur. Shell/servis mühitinə verin. Lokal demo üçün dəyişən tələb olunmur. Uvicorn istifadə edilirsə dotenv dəstəyi ilə `python -m uvicorn backend.app:app --env-file .env --host 127.0.0.1 --port 3000` işlədilə bilər.

| Dəyişən | Məna |
| --- | --- |
| `DEMO_MODE=0` | Demo hesabları və nasazlıq simulyasiyasını söndürür |
| `ADMIN_PASSWORD` | Demo söndürüləndə ilkin `admin` üçün ən az 16 simvol |
| `SECURE_COOKIES=1` | HTTPS yerləşdirmədə session cookie yalnız TLS ilə göndərilir |
| `DATABASE_PATH` | SQLite faylı; standart `data/crisis.db` |
| `SENSOR_KEY` | Kamera ölçmələri üçün ayrıca server açarı |
| `ORS_API_KEY` | Opsional OpenRouteService açarı; lokal rejim tələb etmir |
| `ORS_URL` | OpenRouteService foot-walking/geojson endpointi |
| `ALLOWED_ORIGINS` | Vergüllə ayrılmış əlavə etibarlı origin-lər |

PBKDF2 şifrə heşi, 8 saatlıq server sessiyası, HttpOnly/SameSite cookie, CSRF header/origin yoxlaması, Pydantic doğrulama, 64 KiB body həddi, parametrli SQL və audit jurnalı var. SOS limiti 8/dəq/şəxs, ümumi API 300/dəq/şəxs, giriş 12/dəq/IP və 8/dəq/hesab, guest 40/dəq/IP, sensor 120/dəq/məntəqə. `429` ilə `Retry-After` verilir. Rollar yalnız frontenddə gizlədilmir, hər server əməliyyatında yoxlanır.

Bu prototip tək prosesli SQLite və yaddaşdakı limiter istifadə edir. Horizontal miqyas üçün PostgreSQL/PostGIS, ortaq Redis limiter/pubsub, davamlı event queue və etibarlı şəxsiyyət doğrulaması ayrıca mərhələdir. Guest sessiyası insanın unikal şəxsiyyətini sübut etmir. Real FHN dispetçer sistemi ilə inteqrasiya yoxdur; göndəriş burada prototipin briqada statusunu dəyişir.

Arxitektura və challenge uyğunlaşdırması: [architecture.md](docs/architecture.md). Baxılan repolar və istifadə sərhədləri: [sources.md](docs/sources.md).
