# Azərbaycan dilində səsli SOS

Vətəndaş xəritəsində **Səsli SOS** düyməsini basır, danışır, yaranan mətn və təklif edilən yardım növünü yoxlayıb **SOS göndər** seçir. Mikrofonla yazmaq və hazır səs faylı yükləmək eyni analizdən keçir. Sistem özbaşına hadisə göndərmir.

## Başlatmaq

Windows-da `SES_BASLAT.cmd` açın. Digər sistemlərdə:

```sh
python tools/start.py --voice
```

İlk quraşdırma Python paketlərini və təxminən 1.6 GB modeli endirir. Sonrakı analizlər modelin yerli nüsxəsi ilə işləyir; audio başqa ASR xidmətinə göndərilmir. `--voice --vision` hər iki əlavə modulu quraşdırır. Model yüklənməyibsə, tətbiq əl ilə SOS seçimini saxlayır.

Səhifə: `/workspace.html#voice`. Əvvəlki sessiya dispetçer rejimində qalıbsa, **Vətəndaş** rejiminə keçin. Səsli SOS vətəndaş səlahiyyəti tələb edir.

Telefon mikrofonu üçün **HTTPS** lazımdır; kompüterdə `localhost` / `127.0.0.1` də işləyir. Adi `http://192.168...` LAN ünvanında mikrofon brauzer tərəfindən bağlana bilər. Belə halda telefonda səs yazıb **Səs faylı seç** ilə yükləyin. Kamera və yer icazəsi səs funksiyası üçün istənilmir. SOS xəritədə göstərilən mövqedən göndərilir; bu, avtomatik GPS təsdiqi deyil.

## Təqdimatda göstərmək

1. **Səsli SOS → Səs yazmağa başla**. Mikrofon icazəsini verin.
2. “Evdə yanğın var, tüstü içəri dolur” deyin və **Bitir və mətnə çevir** basın. Yazı 20 saniyədə özü dayanır.
3. Transkripsiya və **Yanğın** təklifi görünür. Başqa nümunələr: “Bina uçub, dağıntı altında qalmışıq”, “Küçəni su basıb”, “Anam nəfəs ala bilmir, təcili yardım çağırın”.
4. Mətni və mövqeyi yoxlayıb **SOS göndər** basın. İstəsəniz, mətnə düzəliş edib növü yenidən seçdirin.
5. Dispetçer rejimində hadisəni açın → **Səsli SOS**. İstifadəçinin təsdiqlədiyi mətn və hesablana bilmiş danışıq tempi görünür.

Bu prototip real təcili yardım xidmətinə inteqrasiya edilməyib. Analiz zamanı əl ilə SOS-a keçmək mümkündür.

## Nə avtomatikdir?

- `hasan0v/whisper-turbo-az-ct2` Azərbaycan dilində danışığı mətnə çevirir. Sabit reviziya: `e41a2b4e276d27f3416ae975dbf0d90ca352a6d2`.
- `faster-whisper` CPU üzərində INT8 işlədir; Silero VAD səssiz hissələri ayırır. Dil `az`, tərcümə deyil, transkripsiya seçilib.
- Sadə, izah edilən Azərbaycan dili qaydaları mətnə görə yanğın, dağıntı, su basması və tibbi yardım təklif edir. Bu hissə LLM deyil; bütün dialektləri, dolayı ifadələri və mürəkkəb inkarları anladığı iddia edilmir.
- Aşağı model əminliyi, aydın danışığın olmaması, uyğun açar ifadənin tapılmaması və ya birdən çox hadisə növü olduqda sistem növü məcburi seçmir. İstifadəçi yoxlayır.
- Danışıq tempi: transkripsiyadakı söz sayı / VAD-dan sonra danışıq müddəti × 60. Ən az 5 söz və 2 saniyə danışıq tələb olunur. Bu **təxmini** göstəricidir; panika, emosional vəziyyət, diaqnoz və ya təhlükənin ağırlığı kimi istifadə olunmur. Mətni dəyişəndə bu göstərici silinir. SOS prioritet qaydaları dəyişməyib.

## Mənbə seçimi

| Mənbə | İstifadə |
|---|---|
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — MIT | Seçilmiş ASR mühərriki, CPU INT8 və VAD |
| [snakers4/silero-vad](https://github.com/snakers4/silero-vad) — MIT | faster-whisper daxilində danışıq/səssizlik ayırma |
| [mammadovziya/whisper-az](https://github.com/mammadovziya/whisper-az) | Azərbaycan dili üçün benchmark və uyğunlaşdırma referansı; kodu köçürülməyib |
| [LocalDoc/azerbaijani-whisper-turbo](https://huggingface.co/LocalDoc/azerbaijani-whisper-turbo) — Apache-2.0 | Azərbaycan dili üçün uyğunlaşdırılmış baza model |
| [hasan0v/whisper-turbo-az](https://huggingface.co/hasan0v/whisper-turbo-az) və [CT2 ixracı](https://huggingface.co/hasan0v/whisper-turbo-az-ct2) — Apache-2.0 | Layihədə seçilmiş Azərbaycan dili modeli; model kartı yükləmədə saxlanır |

## Sərhədlər və məlumat

Maksimum 20 saniyə (dekoderin kiçik konteyner toleransı ilə), 8 MB; eyni server prosesində bir analiz, istifadəçi başına dəqiqədə 8 sorğu, analiz üçün 150 saniyə limit. WAV, MP3, M4A/MP4, WebM, OGG və FLAC qəbul olunur. CPU nəticəsi dərhal gəlmir; emal vəziyyəti göstərilir. Səs-küy və qısa danışıq səhvlərə səbəb ola bilər.

Müvəqqəti səs və transkripsiya faylları sorğu bitəndə, xəta və ya ləğv zamanı silinir. Yalnız istifadəçi SOS göndərdikdə təsdiqlənmiş mətn və temp SQLite-da saxlanır. Bu qeydlər açıq xəritə, WebSocket snapshot və ümumi müşahidəçi panelinə çıxmır; yalnız hadisəni idarə edə bilən dispetçer/admin və həmin hadisəyə təyin olunmuş briqada oxuya bilir. Giriş auditində mətn yoxdur.

Şəbəkə SOS göndəriləndə kəsilərsə, təsdiqlənmiş qeyd mövcud cihazdakı SOS növbəsinə daxil olur və əlaqə bərpa olunanda eyni hadisə açarı ilə göndərilir. Serverə çıxış tam kəsiləndə **yeni səsin tanınması** işləmir; əl ilə SOS növbəsi qalır. Səs funksiyası brauzerdə oflayn ASR deyil.

Bir prosesli prototip üçündür. Bir neçə server worker-i/replica üçün ayrıca ASR xidməti, növbə və paylaşılan limit tələb olunur. Model faylları Git-ə daxil edilmir.

## Yoxlama

```sh
python -m pytest -q
node --test tests/*.test.mjs
```

Funksional testlər: Azərbaycan hərfləri və ASCII yazılış, inkarlar, qarışıq hadisələr, qısa yazıda tempin boş qalması, autentifikasiya, CSRF, ölçü limitləri, audio təmizlənməsi, təsdiqdən əvvəl SOS yaradılmaması, şəxsi qeydlərin görünmə sərhədi və təkrar göndərişin qeydi dəyişməməsi.

Real səs yoxlaması üçün [LocalDoc/FLEURS Azərbaycan dili test dəsti](https://huggingface.co/datasets/LocalDoc/fleurs-azerbaijani-asr) (CC-BY-4.0), test sətir 0 istifadə edildi: 14.28 saniyə audio, yerli CPU-da 27.77 saniyə model emalı. Mətn istinad cümləsinə uyğun çıxdı; bu bir nümunə ümumi dəqiqlik ölçümü və ya fövqəladə hallar üzrə validasiya deyil. Brauzerin real telefon mikrofonu ayrıca fiziki cihazda yoxlanmalıdır.
