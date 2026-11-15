# Prioritet SOS və əlçatan marşrut

## İnterfeysdə necə tapmaq olar

1. `BASLAT.cmd` ilə serveri başladın və `/workspace.html` açın.
2. Sağ yuxarıdakı **İş rejimini seçin** (hesab) düyməsini açın.
3. **Prioritet SOS rolunu aktivləşdir** seçin. Alternativ demo hesab: **Xüsusi qayğı vətəndaşı · prioritet SOS** (`demo-priority_citizen`, demo şifrəsi `demo`).
4. Rol pəncərəsini bağlayın. Marşrut kartında **Yalnız əlçatan marşrut** görünəcək.
5. SOS göndərin. Ayrı brauzer/profildə dispetçer hesabını açın: tək bir müraciət **Kritik · Priority 1** nişanı ilə yuxarıda görünür və dərhal xəbərdarlıq yaradır.

Hərəkət profilində `limited`, `wheelchair` və ya `assisted` saxlananda da rol avtomatik aktivləşir. Digər xüsusi qayğı ehtiyacları üçün istifadəçi rolu özü seçə bilər. Bu, özünü bəyan etmədir; tibbi təsdiq və ya dövlət reyestri ilə yoxlama deyil. Rol adi vətəndaşla eyni icazələrə malikdir, dispetçer/admin səlahiyyəti vermir. Admin də mövcud rol təyinetmə ekranından bu rolu təyin edə bilər.

Profil paylaşımı standart olaraq bağlı qalır. Priority 1 və ehtiyac profilinin paylaşılmasına razılıq ayrı anlayışlardır. İctimai xəritəyə prioritet və fərdi ehtiyac məlumatları çıxarılmır; sahibinin müraciətləri və səlahiyyətli operatorlar prioriteti görür.

## SOS davranışı

Prioritet serverdə müəyyən edilir; sorğuya özbaşına `priority` əlavə etmək rədd olunur. P1 üçün 4 SOS həddi gözlənilmir. Hadisədə aktiv P1 varsa, operator siyahısında önə çəkilir. “Təhlükəsizəm” aktiv yardım ehtiyacını və ona bağlı P1 xəbərdarlığının aktivliyini dayandırır; müraciətin tarixi prioritetini silmir. Eyni `event_key` ilə təkrar göndəriş əlavə müraciət yaratmır. Adi SOS-dan sonra rol aktivləşib eyni hadisəyə yeni SOS göndərilərsə, aktiv müraciət P1-ə qaldırılır; insan sayı iki dəfə sayılmır.

Profil silinməsi/yenilənməsi P1 rolunu avtomatik söndürmür. İstifadəçi hesab pəncərəsində adi rola qayıda bilər; profil hələ hərəkət dəstəyi tələb edirsə, əvvəl onu yeniləməlidir. Mövcud göndərilmiş SOS-ların prioriteti rolun söndürülməsi ilə azaldılmır.

## Marşrut müqaviləsi

Həm server, həm brauzerin lokal Dijkstra hesablaması aşağıdakı atributların hamısı `true` olan yol və məntəqələri qəbul edir:

- `accessibility_verified`
- `step_free`
- `ramp_access`
- `obstacle_free`
- `wheelchair_accessible`
- `medical_vehicle_accessible`

Naməlum, çatışmayan və ya `false` atribut yolun seçilməməsi deməkdir. Bağlı yollar və ən az 90% dolu məntəqələr əvvəlki kimi çıxarılır. Başlanğıc nöqtəsi qraf düyünündən 2 metrdən uzaqdırsa, aradakı yoxlanmamış keçidə zəmanət verilmədiyindən əlçatan marşrut qaytarılmır. 2 m həddi yalnız demo koordinat uyğunluğu üçündür, GPS dəqiqliyi zəmanəti deyil. Uyğun yol yoxdursa ekran **Təsdiqlənmiş əlçatan marşrut yoxdur** göstərir və yardım SOS-u təklif edir. Adi piyada yoluna səssiz keçid yoxdur.

Standart ORS `foot-walking` provayderi bu atributları təsdiqləmir. Buna görə prioritet vətəndaşlar üçün xarici provayder çağırılmır; `accessible_local_only` səbəbi ilə filtrli lokal qraf istifadə olunur. Server əlçatmaz olduqda brauzer də eyni filtrdən istifadə edir. Köhnə keşdə atributlar yoxdursa adi yol göstərmək əvəzinə marşrut yoxdur nəticəsi verilir.

**Demo sərhədi:** repo Bakı üzrə rəsmi pandus və tibbi nəqliyyat yol reyestrinə malik deyil. Seçilmiş demo yollar/məntəqələr simulyasiya atributları ilə işarələnib. `accessibility_scope=simulation` və UI qeydi bunu göstərir. Real istifadəyə keçmək üçün ölçülmüş, səlahiyyətli qurum tərəfindən yoxlanmış yol/məntəqə və başlanğıc keçidi məlumatları lazımdır. Müddət göstəricisi qrafın təxmini hesabıdır, tibbi avtomobilin real hərəkət vaxtı deyil.

## Yenilənmə və yoxlama

SQLite başlanğıcda mövcud müraciətlərə `priority` sütununu və yeni rolu əlavə edir. Yalnız əvvəlki daxili demo qrafına tam uyğun və əlçatanlıq atributu olmayan qeydlər simulyasiya atributları ilə tamamlanır. Dəyişdirilmiş/naməlum qeydlər təsdiqlənmir; doluluq və bağlı yollar qorunur. Sxem yenilənməsi təkrar işə salınmaya uyğundur.

```sh
python -m pytest -q
node --test tests/*.test.mjs
python tools/load_test.py --isolated --requests 1000
```

Yeni testlər: `tests/test_priority_accessibility.py` və `tests/priority-accessibility.test.mjs`. Əvvəlki 503, 4.5 saniyəlik provayder limiti, 5 saniyəlik brauzer limiti və circuit breaker testləri saxlanılır.
