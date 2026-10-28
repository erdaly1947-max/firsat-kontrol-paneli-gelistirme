# Fırsat-Kontrol Paneli — Sürüm 01 geliştirme durumu

> **Güncel kaynak:** Bu depodaki `main` dalı Sürüm 01 geliştirme kaynağıdır. Önceki Windows deneme paketinde `radar_core.py` içindeki `Decimal` ad alanı hatası görüldü; düzeltilen sürüm için ayrı regresyon testleri eklendi. Korunan Sürüm 00 Release'i ayrı bir referanstır. Uygulanan işlevler kaynak kod ve test kanıtıyla, ölçülmemiş kalanlar açıkça ayrılır.

## CANLI BAĞLAM — en son doğrulanmış durum

> **Bu bölüm güncel özet içindir; yeni kanıt geldikçe güncellenir.** Eski canlı özetin önemli ayrıntıları tarihsel kayıtta korunur. Aşağıdaki durumun son rapor kanıtı 28 Ekim 2026, 00:51 TRT civarındadır. Bu zamandan sonraki gerçek çalışma durumu yeni rapor/log görülmeden doğrulanmış sayılmaz.

### Nerede kaldık?
Sürüm 01’in son incelenen çalıştırmasında canlı piyasa akışı güncel olarak raporlandı; ancak geçmiş mumların başlangıç hazırlığı tamamlanmamıştı. Günlük ve sorun giderme raporları yeni durum taşıyordu, analiz raporunun yenilenmesi ise doğrulanmamıştı.

### Doğrulananlar ve halledilenler
- README’de son incelemenin bulguları ve açık işler tarihli kayıt olarak saklandı.
- Günlük raporun gönderimi 00:50:18 TRT’de başarılı olarak loglandı.
- Sorun giderme ZIP’i üretildi ve bütünlük kontrolü başarılı oldu: 1.983.519 bayt; SHA-256 değeri aşağıdaki tarihsel kayıtta yer alır.
- Günlük, analiz ve sorun giderme JSON raporları okunabildi; ancak bunların zaman damgaları farklıdır ve aynı anda oluşmuş tek bir durum gibi değerlendirilmemelidir.

### Açık kalanlar
- **Analiz raporu gönderimi:** 00:50:23 TRT’de sunucu bağlantısı hatası görüldü. 00:50:45 TRT’deki sonraki girişimin başarılı olduğu doğrulanmadı.
- **Geçmiş mum hazırlığı:** Son tanıda `bootstrap_ready=false` idi. İki eski/eksik mum aralığı hatası kalmıştı; canlı akışın güncel olması bu hazırlığın tamamlandığı anlamına gelmez.
- **Render piyasa geçidi:** Yaklaşık 00:09 ve 00:43 TRT’de bellek taşması/yeniden başlama logları görüldü. Bunların analiz raporu hatasına doğrudan sebep olduğu kanıtlanmadı.
- **`ayarlar.json` kaydı:** Yaklaşık 00:44 TRT’de `PermissionError / WinError 5` görüldü. Sorunun kalıcı olarak çözüldüğü doğrulanmadı.

### Sıradaki iş
Yeni bir rapor veya günlük alındığında önce zaman damgalarını karşılaştır; analiz raporunun güncellenip güncellenmediğini, geçmiş mum hazırlığının tamamlanıp tamamlanmadığını ve geçit/ayar hatalarının tekrarlanıp tekrarlanmadığını kontrol et. Sonucu bu canlı bölüme özetle, ayrıntılı yeni bulguları gerektiğinde tarihli tarihsel kayda ekle.

### Değişiklik ve onay durumu
Bu son incelemede yalnızca README kaydı güncellendi. Bu açık sorunları çözmek amacıyla kaynak kodda veya bulut hizmeti yapılandırmasında değişiklik yapılmış değildir. Teşhis ile düzeltme ayrı tutulur; kod veya bulut yapılandırması değişikliği için kullanıcıdan açık onay beklenir.

## Tarihsel çalışma kaydı — 28 Ekim 2026 (son rapor anı: 00:51 TRT)

Bu bölüm, 28 Ekim 2026 saat 00:51 Türkiye saati civarındaki son rapor ve günlük incelemesini kaydeder. Bu kayıt, daha eski Sürüm 00 anlık görüntülerinden ayrıdır. Tespitler o inceleme anına aittir; sonraki çalıştırmalar yeni zaman damgalarıyla ayrıca kaydedilmelidir.

### Bulut raporlarının durumu

- **Analiz raporu — 00:08:05 TRT (2026-10-27 21:08:05 UTC):** Son okunabilen analiz raporu 0 aday gösteriyor ve BTC bağlamını eski/eksik olarak işaretliyordu. Daha sonraki günlük ve sorun giderme kayıtlarıyla karşılaştırıldığında bu rapor güncel durumu yansıtmıyor; analiz raporu yenilemesi başarısız veya doğrulanmamış durumda.
- **Günlük rapor — 00:49:37 TRT (21:49:37 UTC):** Rapor içindeki motor durumu 00:49:20 TRT (21:49:20 UTC) zamanına aitti. Uygulama sürümü `01`; canlı akış `CANLI AKIŞ GÜNCEL`, geçmiş mum hazırlığı `GEÇMİŞ MUM HAZIRLIĞI EKSİK`, motor durumu `BAĞLANTI/VERİ UYARISI` olarak kaydedildi. Tarama evreni 156 pariteydi.
- **Sorun giderme raporu — 00:51:11 TRT (21:51:11 UTC):** Uygulama sürümü `01`; durum uyarıydı, canlı akış güncel görünüyordu ve geçmiş mum hazırlığı tamamlanmamıştı. 156 paritenin incelenmiş olması, 156 güçlü fırsat bulunduğu anlamına gelmez.
- Günlük raporun gönderimi 00:50:18 TRT'de başarılı göründü. Analiz raporu gönderimi 00:50:23 TRT'de `RuntimeError: Sunucu bağlantısı başarısız` hatasıyla başarısız oldu; hata ayrıntısı logda bulunmuyordu. 00:50:45 TRT'de başka bir analiz raporu gönderim girişimi başladı, fakat sonraki kayıt kesitinde başarılı tamamlandığı doğrulanmadı. Bu nedenle en son analiz raporunun yenilendiği kabul edilmemelidir.

### Veri hazırlığı ve altyapı logları

- Önceki tanılama denemesinde piyasa geçidi/proxy üzerinden gelen HTTP 502 hatalarıyla 134 hata görüldü. Sonraki denemede geçmiş mum hazırlığı hataları 2 kayda düştü: `CVCUSDT 1M` ve `USDCUSDT 1M` için eski/eksik geçmiş aralıkları. Buna rağmen `bootstrap_ready=false` olduğundan tüm başlangıç geçmiş mum hazırlığı hazır sayılmaz.
- Render piyasa geçidi loglarında 27 Ekim 2026 UTC saat yaklaşık 21:09 ve 21:43 civarında Node.js bellek taşması (heap out of memory) ve yeniden başlama olayları görüldü; bunlar Türkiye saatiyle yaklaşık 28 Ekim 00:09 ve 00:43'tür. Bunlar bağlantı hatalarına katkıda bulunmuş olabilir; mevcut kayıtlar, analiz raporu gönderim hatasının doğrudan bu olaylardan kaynaklandığını kanıtlamaz.
- Yerel `ayarlar.json` dosyasını atomik olarak değiştirme sırasında yaklaşık 00:44 TRT'de `PermissionError / WinError 5 — Access denied` kaydedildi. Sonraki ayar/yazı boyutu kayıtları sorunun geçici olmuş olabileceğini gösteriyor; kesin olarak çözüldüğü doğrulanmadı.
- Sorun giderme ZIP'i için yapılan bütünlük kontrolü başarılıydı. Boyut: **1.983.519 bayt**. SHA-256: `5a09d8449ee94d65e83e7491ff443d1a1b9c4cf7a564b74b4e03dc1be3ed0fbd`.

### Bu kayıt anındaki sonuç ve açık işler

1. Günlük ve sorun giderme raporları yeni durum bilgisi taşıyor; analiz raporu ise eski kalmış veya yenilenmesi doğrulanmamış durumda.
2. Canlı akışın güncel olması, sekiz zaman dilimi için geçmiş mum hazırlığının tamamlandığını göstermez. `bootstrap_ready=false` kaldığı için veri hazırlığı uyarısı sürmektedir.
3. Analiz raporu gönderim hatasının nedeni, Render bellek taşması olaylarının bu hatayla doğrudan ilişkisi ve `ayarlar.json` yazma izni sorununun kalıcı olup olmadığı henüz kesinleştirilmemiştir.
4. Bu incelemede kod veya bulut hizmeti yapılandırması değiştirilmedi. Bu bölüm yalnızca görülen rapor ve log bulgularının kaydıdır.

## Çalışma ve sürüm kuralları — güncel geliştirme düzeni

1. Program kaynakları ve kod değişiklikleri bu geliştirme deposunda, mevcut `main` dalında yürütülür. Kullanıcının açık onayı olmadan yeni dal oluşturulmaz. Bu düzeltme grubu için kod değişiklikleri ve test ekleme yetkisi verilmiştir.
2. Eski `erdaly1947-max/matrix` deposu, Sürüm 00 ZIP'i ve kalıcı Release dosyaları korunur; bu çalışma onlara commit, merge, yeniden paketleme veya başka bir değişiklik yapmaz.
3. Mevcut hesaplamalar gereksiz yere yeniden yazılmaz. Doğrulanmış hatalar mevcut modüllerde düzeltilir; ilgili regresyon testleri eklenir veya güncellenir.
4. `main` gönderimi `.github/workflows/validate-and-package.yml` üzerinden kaynak derleme, Python birim testleri, Worker testleri ve piyasa geçidi kontrollerini başlatır. ZIP ve SHA-256, yalnızca gerekli doğrulama adımları başarılı olursa oluşturulur.
5. Otomatik test başarısı tek başına gerçek Windows ekranındaki taşma/kesilme durumunu veya stratejinin kârlılığını kanıtlamaz. Bu kanıtlar ayrı tutulur; doğrulanmayan özellik tamamlandı sayılmaz.
6. Herhangi bir zorunlu test başarısızsa hata gizlenmez ve yeni ZIP başarılı sürüm olarak sunulmaz.

## Sürüm 00 ZIP kimliği — sabit referans

- Dosya: `Firsat-Kontrol-Paneli-Surum-00.zip`
- Paket boyutu: **287.118 bayt**; paket içinde **22 dosya** bulunur.
- SHA-256: `d5909444e7c48f8d79f7cc4f5115da1e606db59bd335e743c554c03d6caddbdb`
- GitHub Actions paketleme zamanı: **27 Ekim 2026, 15:46:11 Türkiye saati**; çalışma `40505956633` başarıyla tamamlandı.
- Paketi oluşturan kaynak ağacı: `73326f2d273fa720ffe63017ad02b6ad67f86ce5`; paketleme tetikleme commit'i `2e19e636850124da84594b72a0742ff9406c715d` dosya ağacını değiştirmedi.
- Sabit dağıtım bağlantısı: [Sürüm 00 ZIP](https://github.com/erdaly1947-max/matrix/releases/download/surum-00/Firsat-Kontrol-Paneli-Surum-00.zip). [Sürüm sayfası](https://github.com/erdaly1947-max/matrix/releases/tag/surum-00).

Bu kimlik, korunacak Sürüm 00 referans paketini ayırt etmek içindir; güncel `main` kaynağı ve Sürüm 01 deneme ZIP'iyle aynı nesne değildir. Bu çalışma eski `matrix` deposuna veya sabit Release ZIP'ine dokunmaz.

## Mevcut kaynakta gerçekten bulunanlar — main

- Windows üzerinde `BASLAT.bat` ile açılan Python/Tkinter masaüstü paneli; `.exe` olarak derlenmiş bir uygulama değildir.
- Tek analiz motoru Binance Spot genel piyasa verisini kullanır. Paketteki `market_data_relay.json`, Render piyasa geçidini (`https://firsat-kontrol-market-relay.onrender.com`) gösterir. BtcTurk yerel USDT Spot listesi tarama evreni için kullanılır; fiyat/mum analizi Binance verisi üzerinden yapılır.
- Motor 5m, 15m, 30m, 1h, 4h, 1d, 1w ve 1M olmak üzere sekiz zaman dilimini değerlendirir; kapanmış mumlar, veri güncelliği ve geçmiş mum hazırlığı ayrı durumlar olarak izlenir.
- Kodda teknik göstergeler, A/B/C aşamaları, BTC piyasa bağlamı, BTC'ye göre göreceli güç/korelasyon, likidite kontrolleri, puanlama, koşullu giriş/stop/teknik hedef planı, alarm ve sinyal/geçmiş kayıtları vardır. Kodda bulunmaları, bütün piyasa koşullarında kârlılıklarının veya tarihsel başarının kanıtlandığı anlamına gelmez.
- Bulut rapor Worker'ı günlük, analiz ve sorun giderme JSON raporlarını okunabilir uçlardan sunar. Güncel kullanıcı çalıştırmasında bu üç JSON raporunun içeriğine erişildi; raporların her biri farklı bir çalışma anını temsil edebilir.

## Arayüzün mevcut hali — kodda uygulanan davranış

- Panelin üstünde motor durumu, tarama evreni, WebSocket durumu, sesli bildirim durumu ve BTC piyasa bağlamı gösterilir.
- Kontroller: `Başlat`, `Durdur`, `Pariteleri Güncelle`, `Günlük Rapor`, `Analiz Raporu`, `Seviye Takibi`, `Sesli Bildirim`, `Ses Testi`, `Sorun Giderme ZIP`, ses seviyesi ve 8–15 punto aralığında yatay yazı boyutu kaydıracı. Üst araç çubuğunda ayrı `Kayıtlar` düğmesi ve `Panel Işığı` kontrolü yoktur; kayıt erişimi tanılama bölümündeki `Son kayıtlar` ve `Kayıt klasörünü aç` üzerinden sağlanır.
- Aday tablosunun gerçek sütunları şunlardır: `Coin`, `Binance USDT`, `BtcTurk USDT`, `Puan`, `Zaman`, `A/B/C`, `Veri`, `BTC'ye göre`, `Son karar`. Seçilen coin alanında keşif yolu, hızlı karar, koşullu giriş, kırılım, zarar durdurma, en fazla üç teknik hedef, alarm uygunluğu ve eksik kontroller gösterilir. Ayrı `Teknik ayrıntılar` paneli göstergeler ve zaman dilimi bulgularını açılır/kapanır şekilde gösterir.
- Adaylar canlı/güncel olma, güçlü alarm uygunluğu, A/B/C aşaması ve puan gibi ölçütlere göre sıralanır; motor eski/eksik mum akışında adayı güncel fırsat gibi sunmamak üzere veri tazeliği kapıları uygular.
- Sesli fırsat alarmı ile stop geçişinin sesleri ayrıdır. Seviye takibi aday seçimi değiştiğinde veya motor kapanınca açık takip görünümü bırakmamak üzere kapatılır.
- Pencere ekran boyutundan hesaplanıp ortalanır. Güncel kodda varsayılan genişlik ekran genişliğinin yaklaşık **%72'si**, yükseklik yaklaşık **%86'sıdır**; bu, aşağıda kayıtlı daha dar panel hedefinin tamamıyla uygulandığı anlamına gelmez.

### Kalan arayüz tasarım farkları — güncel kodla karşılaştırma

- **Siyah arka plan ve beyaz ayırıcılar uygulanmıştır.** Aday tablosunda BTC'ye göre kısa durum sütunu da vardır. Eski README notlarında bu iki özellik “uygulanmadı” diye geçiyorsa bunlar tarihsel durumu anlatır.
- **Yazı boyutu ayarı 8–15 punto yatay kaydıraktır.** Yeni kurulum/varsayılan ayar 8 punto; kayıtlı ve geçerli 8–15 aralığındaki değer korunur. Bozuk veya aralık dışı değer güvenli biçimde sınıra alınır. Kaydırak hareket ettikçe yazılar ölçeklenir ve fare/klavye bırakıldığında ayar kaydedilir.
- Hedef pencere genişliği ilk açılışta ekranın yaklaşık yarısı, ihtiyaç olursa en fazla yaklaşık %80'i; yükseklik ekranın en az %10 altında olacaktı. Mevcut varsayılan genişlik yaklaşık %72, yükseklik %86'dır. Bu ölçü farkı bu düzeltme grubunda değiştirilmez.
- Seçilen coin özeti ile teknik ayrıntılar ayrı bileşenlerdedir; teknik ayrıntılar sağ panelde özetin altında dikey açılır/kapanır. Bu, kabul edilmiş hedef tasarımdaki yan yana hızlı özet/ayrıntı yerleşimiyle tam aynı değildir. Sabit, ayrı bir alt giriş-hedef-risk paneli de tam uygulanmış sayılmaz; giriş/stop/hedef bilgileri seçilen coin özeti içinde gösterilir.
- Ayrı `Kayıtlar` araç çubuğu düğmesi ve çoğaltılmış iç başlık yoktur. Kayıtlar tanılama görünümündeki kontroller üzerinden açılır. Eski `Panel Işığı` kontrolünün yerini yazı boyutu kaydıracı almıştır; kaydetme sırasında eski parlaklık anahtarları temizlenir.

Bu bölüm uygulanan davranışı kalan görsel yerleşim farklarından ayırır. Otomatik testler gerçek Windows ekranındaki taşma/kesilme durumunu veya stratejinin kârlılığını kanıtlamaz.

#### A–D tasarım bölümleri: hedef ile mevcut durum

| README'deki hedef bölüm | Güncel kaynakta görülen durum | Sonuç |
|---|---|---|
| A. Üst bölüm — BTC ve genel piyasa | Motor/canlı veri/geçmiş mum durumları, BTC özeti ve açılır BTC ayrıntıları var; tarama evreni bilgisi tanılama özetinde de gösteriliyor. | İçerik mevcut; BTC ve genel durum alanı korunmuş/genişletilmiş. |
| B. Orta bölüm — öncelikli adaylar | Aday tablosunda dokuz sütun var; Binance/BtcTurk fiyatları, puan, zaman dilimi, A/B/C, veri tazeliği, BTC'ye göre durum ve karar gösteriliyor. | Mevcut. |
| C. Seçilen coin — hızlı karar ve teknik ayrıntılar | Hızlı karar özeti ile teknik ayrıntı ayrı bileşenler; teknik ayrıntı sağ tarafta özetin altında dikey açılır/kapanır. | İki içerik alanı mevcut; istenen yan yana yerleşim uygulanmamış. |
| D. Alt bölüm — giriş, hedef ve risk kontrolü | Giriş bölgesi, kırılım, stop ve teknik hedefler seçilen coin özeti içinde yazılıyor; bunlar için ayrı, sürekli görünen alt panel yok. | İçerik var; bağımsız alt bölüm olarak uygulanmamış. |

Sonuç: kabul edilmiş A–D tasarımında **iki yerleşim farkı** açık kalıyor: C bölümündeki hızlı özet/teknik ayrıntı yan yana değil, dikey; D bölümündeki giriş-hedef-risk bilgileri ayrı bir alt panelde değil. Bu, iki ana bölümün bilinçli olarak silindiğine dair kanıt değildir. README'de “tam olarak iki bölüm kalıcı olarak kaldırılacak” şeklinde açık bir karar kaydı bulunmuyor; bu yüzden böyle bir karar varsayılmamalı.

Kaynak kod ve testlerde ayrıca görülen arayüz kontrolü farkları şunlardır: ayrı `Kayıtlar` araç çubuğu düğmesi yoktur, kayıtlar tanılama bölümünden açılır; eski `Panel Işığı` kontrolünün yerini yazı boyutu kaydıracı almıştır; ikinci/tekrarlı iç başlık üretilmez. Bunlar kontrol veya başlık değişiklikleridir ve A–D ana bölümlerinin kaldırılmasıyla aynı şey değildir.

## Tarihsel doğrulama ve Windows çalışma kanıtı — Sürüm 00

Aşağıdaki CI sonucu, bulut raporu zamanları ve Windows anlık görüntüleri önceki Sürüm 00/önceki deneme paketinin tarihsel kayıtlarıdır. Bunlar `Decimal` hatasını ve yazı boyutu kontrolünü düzelten güncel Sürüm 01 commit'inin test sonucu değildir. Düzeltilen sürüm yalnızca güncel `main` commit'ine ait GitHub Actions doğrulaması ve o çalışmanın yeni artefaktı üzerinden değerlendirilmelidir.


- Paketleme/CI çalıştırması [#40505956633](https://github.com/erdaly1947-max/matrix/actions/runs/40505956633) başarılı tamamlandı: 19 Python kaynak dosyası derlendi; ayar JSON'ları doğrulandı; **78 Python birim testi** geçti; Cloudflare rapor Worker testleri, Render geçidi testleri ve canlı Render/Binance WebSocket ile BtcTurk USDT doğrulamaları geçti; ZIP bütünlüğü kontrol edildi ve Release dosyaları güncellendi.
- CI başarısı, gerçek Windows ekranında bütün kontrol ve yerleşimlerin görsel olarak sınandığını veya stratejinin kârlı olduğunu kanıtlamaz. Kullanıcı bu ZIP'i kendi bilgisayarında başlatıp rapor gönderdi; bu, açılış ve rapor akışına ilişkin gerçek kullanım kanıtıdır.
- Son okunan bulut raporu anlık görüntüleri (27 Ekim 2026, Türkiye saati): Günlük rapor **16:01:26** oluşturulmuş, içindeki motor durumu **16:00:55**; analiz raporu **16:01:46** oluşturulmuş, kaynak durumu **16:01:31**; sorun giderme raporu **16:02:08** oluşturulmuş, içindeki en yeni motor durumu **16:02:05**. Üç JSON içeriği okunabildi.
- Sorun giderme raporundaki 16:02:05 anlık görüntüsünde sürüm `00`, **69 aday**, `CANLI AKIŞ GÜNCEL`, `GEÇMİŞ MUM VERİLERİ HAZIRLANIYOR`; başlangıç hazırlığı 1.248 parite/zaman dilimi birleşiminin 522'si tamamlanmış, 521 başarılı ve 1 hatalı, `bootstrap_ready=false`. Dolayısıyla program açılmış, canlı akış görülmüş ve raporlar okunmuştur; **geçmiş mum hazırlığı henüz tamamlanmış değildi**.
- Daha eski 16:00:55 durum anlık görüntüsü canlı akışı eski/eksik, 537/1.248 tamamlanma ve 17 hata olarak göstermişti. Raporların farklı zaman damgaları nedeniyle bu sayılar tek bir eşzamanlı durum gibi birleştirilmez; daha sonraki sorun giderme anlık görüntüsü 16:02:05 durumunu kaydeder.
- Sorun giderme JSON'u `firsat_kontrol_devir.zip` için dosya boyutu ve SHA-256 metaverisi içeriyordu. Bu incelemede ZIP'in ikili içeriği açılıp tek tek doğrulanmadı; burada doğrulanan şey JSON raporunun okunabilirliği ve raporda ZIP metaverisinin bulunmasıdır.

## Dağıtım paketi ve kullanıcıya teslim kuralı

1. `main` gönderimleri ve pull request'ler otomatik test/doğrulama yapar; tek başına ZIP yayımlama onayı sayılmaz. Kalıcı `surum-01` paketi, kullanıcı açıkça `workflow_dispatch` üzerinden `publish_package=true` seçerek paketlemeyi başlattığında oluşturulur. Bütün zorunlu testler geçmeden paket oluşturma/yayımlama adımlarına geçilmez.
2. Paketleme çalışması başarılı tamamlandığında Sürüm 01 program ZIP'i, SHA-256 doğrulama dosyası, kalıcı GitHub Release dosyaları ve 14 gün saklanan Actions artefaktı doğrulanır. ZIP gerçek dosya olarak indirilir; arşiv bütünlüğü (`testzip`), gerekli masaüstü dosyaları ve üretilen SHA-256 özeti kontrol edilir. Eski Release ZIP'i güncel paket yerine kullanılmaz.
3. **Kullanıcıya teslim yöntemi sabittir:** doğrulanmış ZIP dosyası doğrudan sohbet içinde tıklanabilir indirme bağlantısı olarak `sandbox:/mnt/data/Firsat-Kontrol-Paneli-Surum-01.zip` yolundan gönderilir. SHA-256 dosyası da ayrı bağlantı olarak verilir. Kullanıcıya ZIP'i almak için GitHub Actions sayfasına gitmesi, Actions artefaktı bulması veya Release sayfasından elle indirmesi söylenmez; o sayfalar yalnızca ek kaynak/izleme bağlantısı olarak paylaşılabilir.
4. Sohbette verilecek dosya, paketleme çalışmasının oluşturduğu gerçek ZIP olmalıdır; Actions artefaktının dış kapsayıcı ZIP'i ya da daha önceki bir sürüm yanlışlıkla program ZIP'i olarak sunulmaz. İndirme veya yerel dosya yolu doğrulanamıyorsa bu açıkça belirtilir; bozuk/eski dosya hazırmış gibi paylaşılmaz.
5. Programı kurup denemek için yalnızca program ZIP'i gerekir. SHA-256 dosyası bütünlüğü bağımsız doğrulamak içindir.

## [Tarihsel kayıt] 26 Ekim 2026 — Bulut rapor aktarımının ilk doğrulaması

Bu tarihli not, rapor aktarımının ilk doğrulandığı anı kaydeder; daha sonraki Sürüm 00 kullanımının güncel durumu yerine geçmez. Kullanıcının programı çalıştırmasıyla üç JSON raporunun bulut okuma uçlarından okunabildiği ve sorun giderme ZIP'i için yükleme metaverisi bulunduğu gözlenmişti. Sonraki gerçek kullanımda bu JSON okuma davranışı tekrar kontrol edilmiştir.

Kullanılan okuma yolları:
- Analiz raporu JSON: `/latest`
- Günlük rapor JSON: `/daily`
- Sorun giderme raporu JSON: `/troubleshooting`
- Sorun giderme ZIP: `/troubleshooting.zip`

Rapor Worker'ının ana adresi `https://firsat-kontrol-analysis-report.erdaly1947.workers.dev` şeklindedir. Yükleme uçları token doğrulaması ister; okuma uçları URL'yi bilenlere açıktır. Raporlara erişim anahtarı, parola veya başka hassas bilgi konulmamalıdır.

### Tarihsel kod bileşenleri

- `analysis_report.py`: analiz, günlük ve okunabilir sorun giderme JSON raporlarını ve sorun giderme ZIP'ini gönderme işlevlerini içerir.
- `tek_motor_paneli.pyw`: panelde günlük rapor oluşturma/gönderme, analiz raporu oluşturma/gönderme ve sorun giderme ZIP'i gönderme kontrollerini içerir. Sorun giderme işlemi JSON raporu ve ZIP paketini birlikte gönderir.
- `cloudflare/report-worker/src/index.js`: rapor yükleme/okuma rotaları.
- `cloudflare/report-worker/test/index.test.js`: Worker uçları için testler.

## Yerel rapor dosyaları — sabit adlar

Raporlar `reports/` klasöründe her üretimde aynı dosyaların üzerine yazılır; tarih-saat ekli yeni rapor dosyaları oluşturulmaz.

- Günlük/durum JSON raporu: `firsat_kontrol_raporu.json.gz`
- Günlük Markdown özeti: `firsat_kontrol_raporu.md.gz`
- Günlük tanı özeti: `firsat_kontrol_raporu_tani.json.gz`
- Teknik analiz raporu: `analiz_raporu.json.gz`
- Sorun giderme/devir paketi: `firsat_kontrol_devir.zip`

Başarılı yeni üretimden sonra program yalnızca kendi eski tarihli rapor adlandırma kalıplarıyla eşleşen dosyaları temizler. Diğer dosyalara dokunulmaz. Raporların JSON içerikleri yerelde gzip ile sıkıştırılır; devir paketi ZIP olarak oluşturulur. Buluta JSON raporları gzip sıkıştırmasıyla, devir paketi ise ZIP ikili dosyası olarak gönderilir. Bulut okuma uç noktaları JSON içeriğini açarak okunabilir biçimde sunar.

## Sürüm 00 ZIP içeriğindeki dosyalar ve görevleri

- `binance_erken_firsat_radari.py`: Binance Spot piyasa verisi analiz motoru.
- `radar_core.py`: teknik analiz, aday değerlendirme ve koşullu risk planı.
- `ortak_piyasa.py`, `tek_motor_evreni.py`: halka açık piyasa uç noktaları ve yerel USDT parite listesi.
- `binance_mum_arsivi.py`, `sinyal_kaydi.py`: kapanmış mum arşivi ve sinyal izleme kayıtları.
- `tek_motor_paneli.pyw`: Tkinter masaüstü kontrol paneli; motoru başlatma/durdurma, adayları gösterme, seçilen coin ayrıntıları, seviye takibi, alarmlar ve rapor kontrolleri.
- `veri_yasam_dongusu.py`: eski aday geçmişi CSV'lerini aylık ZIP arşivine doğrulayarak taşıyan ve yalnızca eski, PID etiketli geçici dosyaları temizleyen bakım modülü.
- `btcturk_usdt_spot.json`: yüklenen yerel başlangıç parite listesi. Motor, `data/` altında henüz liste yoksa bu kök dizindeki kopyayı da arar.
- `BASLAT.bat`, `ayarlar.json`, `requirements.txt`, `KULLANIM_KILAVUZU.txt` ve `firsat_kontrol.ico`: başlatma, yapılandırma, bağımlılıklar, kullanım ve görsel kaynakları. ZIP dışında kalan GitHub kaynakları arasında Python test klasörü, `.github/workflows` ve Render piyasa geçidi sunucusunun `render_relay/` kaynakları vardır; Render hizmeti depodan dağıtılır.

## Çalışma sınırları

Program halka açık piyasa verilerini okuyan bir analiz ve karar destek aracıdır; borsa hesabına bağlanmaz, bakiye/pozisyon bilgisi istemez, emir göndermez ve otomatik alım-satım yapmaz. A/B/C aşamaları araştırma durumlarıdır; kârlılık garantisi veya emir değildir.

## Başlatma

ZIP dosyasını Windows’ta ayrı bir klasöre çıkarın ve `BASLAT.bat` dosyasını çalıştırın. Başlatıcı Tkinter içeren uygun Python kurulumunu (Python Launcher/kayıt defteri/PATH üzerinde 3.11–3.14 aralığındaki kurulumlar) arar; `requests` ve `websocket-client` paketlerini kontrol eder, eksikse kurmaya çalışır. Bu paket bir EXE kurucusu değildir.

GitHub'ın `main` dalı ZIP'i kaynak arşividir; bağımsız dağıtım paketiyle aynı şey değildir. Dağıtım paketi ancak derleme, otomatik testler ve ZIP bütünlük kontrolü başarılı olup program ZIP'i Release'e yayımlandığında doğrulanmış sayılır.

## Tarihsel kod ve doğrulama kayıtları

Bu bölümdeki tarihler geçmişte yapılan değişiklikleri ve o zamanki test sonuçlarını açıklar. **Güncel paket kimliği ve son gerçek çalışma durumu için üstteki “Sürüm 00 ZIP kimliği” ve “Paket doğrulaması ve gerçek Windows çalışma kanıtı” bölümleri esas alınır.** Eski Actions sonuçları daha yeni raporların yerine geçmez.

- Kaynak sürüm etiketi `radar_core.py` içinde `APP_VERSION = "00"` şeklindedir.
- **26 Ekim 2026 — panel ve motor ayar özetlerinin ayrılması:** [Commit `86ebc63d`](https://github.com/erdaly1947-max/matrix/commit/86ebc63d1ab80de924df6a4f060966ae4e5a12db) tam ayar SHA-256 özeti ile `panel_ui` alanı hariç motor ayarı özetini ayırdı. Bu mekanizma, panel/ses tercihlerinin motor ayarı değişikliği sanılmaması içindir. Mevcut ZIP'te ayrıca aşağıda belirtilen `screen_brightness`/`panel_brightness` anahtarı uyumsuzluğu vardır; bu eski commit notu o uyumsuzluğun çözüldüğü anlamına gelmez.
- **25 Ekim 2026 — motor durumlarının ayrılması:** [Commit `ab1c7d7d`](https://github.com/erdaly1947-max/matrix/commit/ab1c7d7d8a21ca8bf2b37d652a49d6d294737048) canlı WebSocket sağlığını, geçmiş mum hazırlığını ve genel motor durumunu ayrı kaydetti. Geçici ağ hataları ile kalıcı geçmiş veri boşlukları için farklı tekrar deneme davranışları tanımlandı.
- [Eski doğrulama çalıştırması #40238052373](https://github.com/erdaly1947-max/matrix/actions/runs/40238052373) ve [#40233230870](https://github.com/erdaly1947-max/matrix/actions/runs/40233230870), ilgili 25–26 Ekim kod/test durumlarının tarihsel kanıtlarıdır. Son paket için güncel doğrulama ise [#40505956633](https://github.com/erdaly1947-max/matrix/actions/runs/40505956633) çalıştırmasıdır.

### Güncel açık işler

- Başlangıç mum hazırlığının 1.248 parite/zaman dilimi birleşimi için tamamlandığı, son alınan sorun giderme raporunda doğrulanmadı (`bootstrap_ready=false`). Canlı veri güncelliği ile geçmiş mumların hazır olması ayrı durumlar olarak izlenmelidir.
- Gerçek tarihsel piyasa verisi üzerinde geriye dönük test (backtest), kaçırılan yükselişler/yanlış pozitifler ve stratejinin tarihsel performansı ölçülmedi. Kodda analiz ve sinyal takibi bulunması kârlılık kanıtı değildir.
- Windows masaüstünde siyah arka plan ve diğer onaylanmış hedef yerleşim kararları uygulanmadı. Güncel arayüzün görsel/etkileşim hedefleri ayrıca doğrulanmalıdır.
- Panel ayar dosyasında `screen_brightness` ile kodun okuduğu/yazdığı `panel_brightness` anahtarı tutarsızdır. Bu inceleme sırasında yalnızca kaydedilmiştir; kaynak koda değişiklik yapılmamıştır.
- `ayarlar.json` komisyon/kayma oranlarını tanımlamaz. Mevcut teknik risk/getiri değeri brüttür; güçlü fırsat kapısı ilk teknik hedef için en az 1,5 brüt teknik risk/getiri, en az 80/100 puan ve diğer veri/aşama/likidite/plan/BTC kapılarını arar. Program net masraf sonrası getiri hesaplamaz.

## Sürüm 00 — kesin başlangıç noktası

- **En son Sürüm 00 paketi üstteki SHA-256 ile tanımlanan ZIP'tir.** Bundan sonraki modül incelemelerinde `radar_core.py`, `binance_erken_firsat_radari.py`, `ortak_piyasa.py`, `tek_motor_evreni.py`, `binance_mum_arsivi.py`, `sinyal_kaydi.py`, `analysis_report.py`, `tek_motor_paneli.pyw` ve diğer ZIP dosyaları referans alınır.
- Kaynak kod yeniden yazılmaz; mevcut motor fonksiyonları ve hesaplamalar korunarak geliştirme yapılır. Bir işlevin planda yazılı olması, kodda uygulanmış olduğuna kanıt değildir; bir işlevin kodda bulunması da tarihsel piyasa başarısını kanıtlamaz.
- Sürüm 00 düzeltme işleri `main` üzerinde yürütülür. Kullanıcı önceden açıkça onay vermeden yeni dal açılmaz. Sürüm 1 dalı ancak kullanıcı onayından sonra `1.surum-readme-gereksinimler` adıyla açılabilir.

## Kalıcı çalışma kuralları

Bu bölüm, proje boyunca uygulanacak çalışma düzenini tanımlar. Kullanıcının sonradan bildirdiği yeni kurallar bu bölüme eklenir; tekrar eden hükümler birleştirilir, hiçbir kuralın anlamı yorumlanmaz, değiştirilmez. Buradaki kurallar, çelişen eski çalışma notlarına göre önceliklidir ve kullanıcı aksini belirtmedikçe geçerlidir.

### 1. Çalışma alanı ve kayıtların yeri

- Program yazımı, kod düzenleme ve bunlarla ilgili bütün çalışmalar yalnızca GitHub üzerinde yürütülür.
- **Kesin dal kuralı:** Kullanıcıya önceden haber vermeden ve açık onayını almadan yeni Git dalı açılmaz. Bu kural tüm aşamalarda geçerlidir.
- Bu projeyle ilgili ChatGPT Kitaplığı'nda hiçbir kayıt, dosya veya klasör oluşturulmaz.
- Projenin kaynakları, gerekli dosyaları ve çalışma kuralları GitHub deposunda tutulur. Çalışma kuralları bu `README.md` dosyasında kayıt altına alınır.

### 2. Aşamalar, gereksinimler ve tasarım onayı

- İlk aşamada netleştirilen gereksinimler temel alınır. Her yeni aşama ve kod önceki aşamaların üzerine eklenir; önceki kararlar kaybedilmez veya birbirinden kopuk değerlendirilmez.
- İstenen davranış, programda nasıl uygulanacağı ve hangi mantıkla çalışacağı önce netleştirilir. Arayüz tasarımında sonucun kullanıcıya nasıl gösterileceği, hangi bilgilerin öne çıkarılacağı ve fırsat kararının nasıl anlaşılacağı somutlaştırılır.
- Henüz kesinleşmemiş yeni tasarım konuları kesin karar gibi uygulanmaz; kullanıcıya sorulur. Bu README'ye aktarılan Sürüm 01 düzeltme görevi, açıkça listelenen kodlama ve regresyon testleri için ayrıca yetki içerir; aynı görevde tekrar onay istenmez.
- Yeni ve henüz onaylanmamış tasarım kararları kodlanmadan önce netleştirilir. Kullanıcının zaten açıkça yetkilendirdiği bir düzeltme grubu için tekrar onay sorulmaz; kapsam dışı tasarım değişikliği yapılmaz.
- Tasarım ve onay süreci tamamlanmadan sonraki aşamaya geçilmez.

### 3. Her çalışmanın başında mevcut durumu belirleme

Her yeni çalışma başlangıcında mevcut sürüm, aktif aşama, README’deki gerçek tamamlanma durumu ve sıradaki iş netleştirilir. README, mevcut kod, gerçek çalışma raporları ve ilgili test sonuçları karşılaştırılır. Daha önce başarılı olan kontroller gereksiz yere tekrarlanmaz; doğrulanmış eksikler üzerinde ilerlenir.

### 4. Gereksinim kaydı, kodlama, test ve durum güncellemesi

- Gereksinimler, kabul edilmiş tasarım kararları ve uygulama yöntemi kodlamadan önce README’ye kaydedilir. Tasarım onayı alınmadan ilgili kodda değişiklik yapılmaz; önce kullanıcıya sorulur.
- Birbiriyle ilişkili kodlama işleri anlamlı ve işlevsel gruplar hâlinde tamamlanır; işler gereksiz yere küçük parçalara testlere ayrılmaz.
- Bir kodlama grubu için belirlenen kapsam bitmeden o gruba ait test turu başlatılmaz. Kodlama tamamlanınca ilgili testler topluca, ardından gerekli genel regresyon testleri çalıştırılır.
- Testlerde başarısız sonuç varsa gerekli düzeltmeler yapılır ve etkilenen testler yeniden çalıştırılır. Başarısız testleri bulunan bir grup veya sürüm bir daha kontrol edilir.
- **Gereksinim/tasarım kaydı ile uygulama durumu kaydı ayrıdır:** Gereksinimler ve planlanan davranış önceden yazılır. Uygulamanın tamamlandığı, test edildiği veya başarılı olduğu ancak kod, rapor ve test kanıtları görüldükten sonra kayda geçirilir ve kullanıcıya bildirilir.
- İlgili uygulama ve test grubu tamamlandığında sonuçlar, kalan eksikler ve sürüm kayıtları README'de gerçeğe uygun biçimde güncellenir. Uygun olduğunda ilgili kod, test ve durum kayıtları tek commit altında toplanır.
- **README her zaman güncel tutulur:** Her çalışma sonunda güncel program durumu, gerçekten çalışan akışlar ve açık kalan işler README ile karşılaştırılır; güncel duruma aykırı eski ifadeler düzeltilir. Geçmiş kayıtlar gerektiğinde korunur, ancak açıkça “tarihsel/eski kayıt” ve ilgili tarih olarak işaretlenir. Eski test veya CI sonucu güncel çalışma durumuyla karıştırılmaz. Aynı konu hakkındaki güncel durum, eski notlardan belirgin biçimde ayrılır.

- **README iki katmanlı tutulur: canlı bağlam ve tarihsel kayıt.** Canlı bağlam README'nin üst kısmındaki kısa, güncel çalışma özetidir; her yeni rapor, günlük, test veya inceleme sonrasında en son doğrulanmış durumla güncellenir. İçinde nerede kalındığı, tamamlanan/doğrulanan işler, açık sorunlar, sıradaki kontrol ve kod/bulut değişiklikleri için onay durumu bulunur. Yeni durum geldikçe bu özet güncellenir; tekrar eden eski özetler canlı bölümde biriktirilmez.
- **Geçmiş kayıtlar silinmez veya güncel durum gibi sunulmaz.** Canlı bölümden çıkarılan önemli bulgular, çözüm ve test kanıtı ile zaman bilgisi gerektiğinde tarihsel kayıtta tutulur. Bir bulgu ancak yeni kanıtla çözüldü olarak işaretlenir; şüphe veya olası neden kesin sebep gibi yazılmaz. Yeni kanıt önceki kaydı değiştiriyorsa canlı bağlam düzeltilir ve tarihsel kayıt ilgili tarihle korunur.
- Tamamlanmış işler tekrar uygulanmaz. Her yeni değişiklik doğrulanmış bir eksiğe veya kullanıcı tarafından onaylanmış yeni bir gereksinime dayanır.

### 5. Dal, sürüm, aşamalar arası aktarım ve son ZIP paketi

- **Sürüm 00 başlangıç tabanı**, yukarıda kimliği verilen ve kullanıcının bilgisayarında başlattığı ZIP paketidir. Paketteki sürüm etiketi "00" olarak kalır; bu README güncellemesi kaynak kodunu veya uygulama davranışını değiştirmez. Planlanan yeni özellikler, uygulanıp doğrulanana kadar uygulanmış sayılmaz.
- **Dal açılmadan önce açık kullanıcı onayı zorunludur.** Onay alınmadan dal oluşturulmaz, yeniden adlandırılmaz veya başka bir dal geliştirme alanı olarak seçilmez. Sürüm 00 başlangıç ve düzeltme işleri `main` üzerinde yürütülür. Kullanıcı Sürüm 1 dalının açılmasını onaylarsa adı tam olarak `1.surum-readme-gereksinimler` olur. Sürüm 00 tabanının bu dala kopyalanması ve sonraki geliştirmelerin orada yürütülmesi, yalnızca verilen onay kapsamındadır; onay olmadan `main` veya başka bir dal üzerinde farklı bir geliştirme süreci başlatılmaz.
- Yan dalda yapılan değişiklikler gerekli hesaplama, regresyon, geçmiş veri, panel, raporlama ve paket kontrolleri tamamlanmadan main dalına aktarılmaz. Sürüm 1 ancak bu kontroller ve ilgili kullanıcı onayı sonrasında hazırlanır.
- Her aşamanın sonunda, yeni sohbet odasında kesintisiz devam edilebilmesi için kesinleşmiş kararlar, tamamlanan işler, doğrulanmış eksikler ve sıradaki aşamanın amacı birlikte özet olarak aktarılır.
- Bağlam aktarımı tamamlanmış sayılmadan önce güncel README kontrol edilir; aktarım README'deki gerçek durumla tutarlı olmalıdır.
- ZIP paketi hazırlanırken gerekli yerel BtcTurk USDT evreni dosyası pakette bulunur; fan token dışlama kuralları korunur.
- Nihai ZIP paketi oluşturulmadan önce paketleme aşaması kullanıcıya bildirilir ve açık onayı alınır. Bu bildirim ve onay olmadan yeni ZIP paketi oluşturulmaz.

## Geliştirme hedefi ve ortak karar sistemi

### 6. Ana karar: mevcut bilgisayar programını koru, üzerine geliştir

Programın amacı, kullanıcının para kazanmasına destek olmak üzere mevcut sistemi koruyarak hızlı yükseliş potansiyeli taşıyan coinleri daha erken ve daha isabetli değerlendirmektir. İlk hedef, mevcut motorun yaptığı hesaplamaları yeniden yazmak değil; eksik kalan yönlerini mevcut işlevler üzerinden geliştirmek ve sonuçlarını ortak bir karar yapısında birleştirerek arayüzde bir bakışta anlaşılacak şekilde yansımasını sağlamaktır.

- Mevcut program baştan yazılmaz. Kullanıcı istemedikçe çalışan ve gerekli işlevler korunur; mevcut davranışlar sessizce bozulmaz.
- Aynı gösterge, piyasa verisi veya teknik seviye hesabı farklı yerlerde gereksiz yere tekrarlanmaz. Mevcut hesaplamaların çıktıları yeniden kullanılabilir ve ihtiyaç duyulan geliştirmeler uygun mevcut modüle bağlanır.
- Yeni bir fonksiyon veya modül ancak kullanıcı isterse ya da kod incelemesi mevcut işlevlerin geliştirilmesiyle ihtiyacın karşılanamayacağını gösterirse değerlendirilir.
- Yeni özelliklerin aday sıralamasını, A/B/C aşama sınıflandırmasını, alarmları veya mevcut panel davranışını değiştirmesi tasarımda açıkça belirtilir; sessiz ve doğrulanmamış davranış değişikliği yapılmaz.
- Amaç, ilk bakışta piyasanın durumunu, hangi coinlerin neden öne çıktığını ve seçilen coindeki olası getirinin riskine değip değmediğini anlamayı sağlamaktır. Ayrıntılı analizler ve mevcut işlevler erişilebilir kalır.
- Program halka açık piyasa verilerini okuyan bir analiz ve karar destek aracıdır. Bu gereksinimler kendi başına borsa hesabına bağlanma, emir gönderme veya otomatik alım-satım yetkisi oluşturmaz.

### 7. İlk somut iş: mevcut–eksik–geliştirme–test matrisi

Yeni kod yazmadan önce mevcut sistemin gerçek durumu güvence altına alınır. Kod, mevcut fonksiyonlar, veri akışı ve testler incelenir; hâlihazırda çalışan, kısmen çalışan ve eksik olan işlevler birbirinden kesin biçimde ayrılır. Bir davranış yalnızca tasarım belgesinde yer aldığı için uygulanmış kabul edilmez; kodda gerçekten bulunup bulunmadığı kontrol edilir.

Her mevcut fonksiyon için şu üç soru yanıtlanır:

1. **Şimdi ne yapıyor?** Kodda gerçekten bulunan işlev ve ürettiği sonuç nedir; arayüze ne yansıyor?
2. **Nerede yetersiz kalıyor?** İstenen davranışın hangi parçası eksik, kısmi veya testlerle doğrulanmamış?
3. **Mevcut fonksiyon nasıl geliştirilirse ihtiyaç karşılanır?** Hangi mevcut modülde, hangi hesaplama ve sonuçlar yeniden kullanılarak geliştirme yapılabilir?

Matris en az şu sütunları içerir:

| Fonksiyon/modül | Şu anki davranış ve kod kanıtı | Eksik veya yetersiz kalan yön | Mevcut yapı üzerinden geliştirme | Yeniden kullanılacak hesaplama/veri | Doğrulama testi | Durum |
|---|---|---|---|---|---|---|
| Ortak USDT parite evreni — `ortak_piyasa.py:fetch_common_usdt_symbols`, `tek_motor_evreni.py:build_single_engine_universe` | Binance Spot piyasa verisi ve yerel kaydedilmiş BtcTurk USDT listesi kullanılır; son kullanıcı raporunda tarama evreni 156 parite olarak bildirildi. | Son kontrol anında BtcTurk listesi `LOCAL_SAVED_LIST` modundaydı ve yerel liste daha önce kaydedilmişti. Önbellek/alternatif ağ yollarının tüm kenar durumları gerçek kullanımda ayrıca doğrulanmadı. | Var olan ortak evren ve cache akışı korunur; ikinci evren hesabı yazılmaz. | pairs, evren modu, kaynak zaman damgası ve eşleştirme sonucu. | Güncel/eskimiş yerel liste, boş evren, aktif olmayan pariteler, ağ başarısızlığı ve USDT eşleşmesi testleri. | Son canlı çalıştırmada 156 parite görüldü; tüm cache/alternatif yol senaryoları açık |
| Mum akışı, veri güncelliği ve 8 zaman dilimi — `binance_erken_firsat_radari.py:TIMEFRAMES`, `BinanceRadar`; `radar_core.py:valid_bars` | 5m, 15m, 30m, 1h, 4h, 1d, 1w ve 1M zaman dilimleri vardır; REST/WebSocket ve tarihsel mum arşivi kullanılır. | Paket doğrulamasında canlı Render/Binance WebSocket kontrolü geçti. Kullanıcı çalıştırmasında son sorun giderme snapshot’ında akış günceldi ancak geçmiş mum başlangıç hazırlığı 522/1248’deydi ve hazır değildi. | Mevcut REST/WebSocket, arşiv ve geçerlilik kontrolleri üzerinde ilerlenir; ikinci veri katmanı açılmaz. | mum arşivi, `valid_bars`, zaman dilimi sabitleri ve akış yaşları. | Her zaman diliminde kapanmış/açık mum, boşluk, eski akış, onarım ve veri yok kenar durumları. | Canlı akış doğrulandı; geçmiş hazırlığı son snapshot’ta tamamlanmadı; kenar durumlarının tamamı açık |
| Göstergeler ve A/B/C aşama değerlendirmesi — `radar_core.py:_indicator_snapshot`, `assess_timeframe`, `evaluate_binance_candidate` | EMA, MACD, RSI, ADX, DMI, ATR ve hacim bulguları hesaplanır; zaman dilimi kanıtlarından A/B/C aşaması çıkarılır. | Son paket CI’sinde 78 Python birim testi geçti. Bu durum göstergelerin farklı piyasa rejimlerindeki tarihsel isabetini veya kârlılığını ölçmez. | Var olan metrikler ve kanıt grupları kullanılır; aynı göstergeler için ikinci hesaplama yazılmaz. | `timeframes[*].metrics`, `evidence_groups`, `findings`, `missing_checks`. | Gösterge referans serileri, eksik/kesintili geçmiş ve aşama regresyonu. | Kodda uygulanmış; genel CI testleri başarılı; tarihsel etkinlik ölçülmedi |
| Pivot, destek/direnç, kanal ve Fibonacci — `_confirmed_pivot_points`, `_support_resistance_zones`, `_confirmed_channel`, `_fibonacci_swing` | Kapanmış mumlardan teyitli pivotlar, destek/direnç bölgeleri, kanallar ve Fibonacci düzeltme/uzatma seviyeleri üretilir; puan/plan bu çıktıları kullanır. | Kod mevcuttur; bunların geçmiş piyasa verisinde hedef/kanal doğruluğu ve yanlış sinyal oranı için tam backtest yapılmadı. | Hedef/puan iyileştirmesi aynı fonksiyonların çıktıları üzerinden yapılır. | `support_resistance_zones`, `confirmed_channel`, `fibonacci`, ATR ve pivotlar. | Elle doğrulanmış fiyat örnekleri; kanal, eksik pivot ve haftalık/aylık swing senaryoları. | Uygulanmış; tarihsel piyasa doğruluğu/backtest açık |
| BTC piyasa bağlamı ve güçlü fırsat kapısı — `score_btc_market_context`, `_apply_btc_context_freshness`, `assess_btc_strong_opportunity_gate` | BTC’nin 1h/4h yönü, seviye/kanal durumu ve göreli oynaklığı değerlendirilir; eski/eksik bağlam, seviye kaybı veya aşırı oynaklık güçlü fırsatı engelleyebilir. Son raporlarda BTC bağlamı hesaplandı. | Testler geçti ancak tüm kapı kombinasyonlarının canlı ve tarihsel piyasa koşullarındaki performansı ölçülmedi. | Var olan BTC puanı, uyarıları ve kapısı korunur; eksik veri olumlu puan sayılmaz. | `btc_market_context`, `data_completeness`, `risk_warnings`, `relative_volatility_ratio`. | Taze/eski bağlam, eksik 1h/4h, kritik seviye kaybı ve oynaklık eşikleri. | Kodda uygulanmış; CI başarılı; tarihsel etki ölçülmedi |
| BTC'ye göre göreceli güç ve korelasyon — `_relative_strength_and_correlation`, `btc_correlation_risk_adjustment`, `score_opportunity` | Eş zamanlı kapanmış mumlardan göreceli performans ve Pearson korelasyonu hesaplanır. Riskli/tam BTC bağlamında ortalama korelasyon ≥0,80 ise -6, ≥0,60 ise -3 düzeltmesi olabilir; korelasyon tek başına yön sinyali değildir. | Bu işlev için özel Python test dosyası vardır ve son 78 testlik suite geçti. Eşiklerin tarihsel başarıya etkisi backtest ile ölçülmedi. | Mevcut korelasyon kuralı ve veri kapıları korunur. | `relative_strength_vs_btc_pct_points`, `btc_return_correlation`, `btc_correlation_assessment`. | Eşik sınırları, yetersiz örnek, eski veri ve sağlıklı/riskli BTC bağlamı. | Kodda uygulanmış; özel unit test ve genel CI başarılı; tarihsel öngörü gücü ölçülmedi |
| Aday puanı ve sıralama — `score_opportunity`, `candidate_priority_key`, `_candidate_rows` | 0–100 puan fiyat yapısı, hacim, momentum, trend, çoklu zaman dilimi, göreceli güç, BTC bağlamı, korelasyon düzeltmesi ve likiditeyi birleştirir. Son karara ayrıca zorunlu uygunluk kapıları etki eder. | Puanlamanın tarihsel başarıya, erken yakalamaya ve yanlış pozitiflere etkisi ölçülmedi. | Mevcut bileşenler ve sıralama korunur; değişiklik gerekçeli ve geçmiş veride doğrulanmış olmalıdır. | `score_components`, `opportunity_score`, `final_decision`, `strong_opportunity_qualified`. | Kararlı sıralama, puan sınırları ve geçmiş veri ile yanlış pozitif/kaçırılan yükseliş analizi. | Kodda uygulanmış; son CI başarılı; tarihsel etkinlik ölçülmedi |
| Koşullu giriş, stop, teknik hedef ve R projeksiyonları — `build_trade_plan` | Giriş bölgesi, kırılım, stop, teknik hedefler, 1R/2R/3R karşılaştırmaları ve geçersizleşme koşulu raporlanır. Son analiz raporu aday risk planlarını içerir. | Hesaplanan hedef/stop seviyelerinin geçmiş gerçek piyasa sonuçlarındaki doğruluğu sistematik olarak test edilmedi. | Aynı plan fonksiyonu ve mevcut seviye/ATR girdileri geliştirilir. | `risk_plan`, ATR, destek/direnç, kanal ve Fibonacci. | Giriş bandı/stop/target geometrisi ve tüm sınır durumları; tarihsel test. | Kodda uygulanmış; raporda görülüyor; tarihsel doğruluk açık |
| Güçlü fırsat ve risk/getiri kapısı — `score_opportunity` | Güçlü fırsat için ≥80 puan, B/C aşaması, güncel mum, parite uygunluğu, başarılı likidite, kovalamama, geçerli teknik plan, BTC kapısı ve ilk teknik hedefte brüt risk/getiri ≥1,5 gerekir. | Kod ve testler vardır; tarihsel performans veya masraf sonrası net getiri hesaplaması yoktur. | Mevcut brüt kapı korunur. Masraf sonrası hesaplama ancak ücret/kayma varsayımları netleştirilip onaylandıktan sonra ele alınır. | `strong_opportunity_qualified`, `risk_plan.targets[0].risk_multiple`, likidite ve tazelik. | 1,5 sınırı ve tüm kapıların birlikte/ayrı başarısızlık testleri; ileride geçmiş veri ölçümü. | Kodda uygulanmış; net maliyet ve tarihsel performans ölçümü açık |
| Sinyal takibi ve tarihsel sonuç — `sinyal_kaydi.py:SignalTracker` | Sinyal anında plan seviyeleri kaydedilir; sonraki fiyat örnekleri giriş/hedef/stop ve 24 saat penceresi bakımından izlenir. | Bu izleme tam piyasa backtest’i değildir; aday listesine girmeyen yükselişler, kaçırılan fırsatlar, mum içi hedef/stop sırası ve işlem maliyetleri sistematik ölçülmez. | Mevcut izleme ve özet fonksiyonları geliştirilir; yeni bir paralel motor eklenmez. | Dondurulmuş `risk_plan`, fiyat örnekleri ve `historical_summary`. | Giriş/stop/hedef/24 saat senaryoları; ayrı backtest gereksinimi netleştirilirse ölçüm tasarımı. | Kısmi işlev uygulanmış; tam backtest yapılmamış |
| Panel aday listesi ve seçilen coin özeti — `tek_motor_paneli.pyw:_build_ui`, `_selection_changed`, `_render_state` | Mevcut tabloda dokuz sütun vardır: coin, Binance/BtcTurk fiyatı, puan, zaman, A/B/C, veri, BTC'ye göre durum ve son karar. Seçilen coin özeti ile açılır teknik ayrıntılar ayrı bileşenlerdedir. | Kaynak kod ve regresyon testleri dokuz sütunu doğrular. Teknik ayrıntılar sağ panelde dikey açılır; hedef penceredeki yan yana hızlı özet/ayrıntı yerleşimi ve daha dar başlangıç ölçüleri hâlâ farklıdır. | Mevcut motor JSON alanları ve risk planı kullanılır; paralel hesaplama katmanı eklenmez. | `btc_market_context`, `relative_strength_vs_btc_pct_points`, `btc_return_correlation`, `findings`, `missing_checks`, `risk_plan`. | Veri/JSON eşleşmesi, aday seçimi, karar gerekçesi ve risk seviyeleri; gerçek Windows yerleşim/ölçek kontrolü. | Açılış ve rapor gönderimi kullanıcı tarafından doğrulandı; hedef yerleşim açık |
| Panel ölçüleri, tema, renkler ve kontroller — `tek_motor_paneli.pyw:_build_ui`, `_apply_font_scale` | Siyah zemin ve beyaz ayırıcılar uygulanmıştır; yazı boyutu kontrolü 8–15 punto aralığında yatay kaydıraktır. Varsayılan pencere yaklaşık %72 ekran genişliği/%86 ekran yüksekliğidir. | Yeni kurulum varsayılanı ve kaydırak sınır/kayıt davranışı regresyonlarla sınanır. Gerçek Windows ekranında yerleşim/taşma testi otomatik testlerin yerine geçmez. | Mevcut panel korunur; kullanıcı onayı olmadan görünüm veya kod değiştirilmez. | Pencere ölçüleri, tema, kontrol etkileşimleri, renk/etiket açıklığı ve taşma regresyonu. | Siyah zemin ve yazı boyutu kaydıracı uygulanır; pencere ölçüsü ve gerçek Windows görsel testi açık |
| Rapor, devir ZIP’i ve depolama bakımı — `tek_motor_paneli.pyw`, `analysis_report.py`, `veri_yasam_dongusu.py`, `binance_mum_arsivi.py` | Yerel günlük/analiz raporları, tanı paketi, mum arşivi ve sinyal geçmişi için kod vardır. Kullanıcının son çalıştırmasında günlük, analiz ve sorun giderme JSON raporları buluttaki okuma uçlarından okunabildi. | Güncel JSON uçları okunabildi; son sorun giderme raporu ZIP için boyut/hash metaverisi taşıdı fakat bu incelemede ZIP ikili dosyası açılıp doğrulanmadı. Uzun süreli Windows depolama/arşiv senaryoları da uçtan uca denenmedi. | Mevcut raporlama mekanizması korunur; yeni sistem yalnızca gerçek eksik kanıtlanırsa tasarlanır. | JSON/Markdown raporları, tanı çıktısı, SHA-256 manifesti, mum arşivi ve sinyal geçmişi. | ZIP açma/SHA doğrulama, bozuk dosya, arşiv sınırları, gerekli rapor ve evren dosyalarının paketlenmesi. | JSON yükleme/okuma doğrulandı; ZIP ikili içeriği ve uzun çalışma senaryoları açık |

**Matrisin kapsamı:** Bu tablo kodda bulunan davranışla, son test/çalışma kanıtını ve ölçülmemiş performans iddialarını birbirinden ayırır. Korunan Sürüm 00 ZIP kimliği ile güncel Sürüm 01 geliştirme kaynağı ayrı nesnelerdir; güncel kod durumu için bu README'nin üst bölümünü ve ilgili `main` GitHub Actions çalışmasını esas alın. Son paket CI'si başarılıdır; kullanıcı Windows üzerinde programı başlatıp bulut JSON raporlarını okuma yoluna kadar doğrulamıştır. Ancak son sorun giderme anlık görüntüsünde geçmiş mum hazırlığı henüz tamamlanmamıştır, tarihsel backtest yoktur ve arayüzün kabul edilmiş hedef tasarımının bazı maddeleri (özellikle pencere ölçüsü ve özet/ayrıntı yerleşimi) uygulanmamıştır. Eski notlarda geçen başarısızlıklar güncel durum değildir; burada yalnızca açıkça tarihsel olarak işaretlenen kayıtlar geçmişi açıklar.

### 8. Hesaplamaların korunması ve karar gereksinimleri

Program sekiz zaman dilimindeki mumları ve mevcut teknik göstergeleri zaten değerlendirir. EMA (üstel hareketli ortalama), MACD (hareketli ortalamaların yakınsama-ıraksama göstergesi), RSI (Göreceli Güç Endeksi), ADX (ortalama yönsel endeks), DMI (yönsel hareket göstergeleri) ve ATR (ortalama gerçek aralık) hesapları gereksiz yere kopyalanmaz. Destek/direnç ve kırılım değerlendirmeleri, mevcut hesaplamalar ve sonuçlar üzerinden geliştirilir.

Ortak karar sistemi, mevcut teknik çıktıları birbirinden kopuk ham değerler olarak sunmak yerine şu bağlamlarla birlikte değerlendirir:

- BTC'nin ana yönü, piyasa rejimi ve genel risk koşulları.
- Coinin kendi teknik aşaması, fiyat yapısı ve kırılım/geri test durumu.
- Coinin BTC'ye göre performansı ve BTC ile korelasyonu (birlikte hareket ilişkisi).
- Yakın ve önemli destek/direnç bölgeleri, yatay kanal sınırları ve olası kırılım veya seviye kaybı.
- Giriş bölgesi, zarar durdurma seviyesi, teknik hedefe kalan getiri ve stop seviyesine kadar olan risk.
- Veri güncelliği, eksik veri, eksik teyit ve işlemin geçersizleşeceği koşullar.

Program her aday için en az şu sorulara cevap üretebilmelidir:

- Önündeki ilk önemli direnç veya olası kâr alma bölgesi nerede?
- Olası girişten bu bölgeye kadar ne kadar getiri alanı bulunuyor?
- Girişten zarar durdurma seviyesine kadar fiyat bazında ve yüzde olarak ne kadar risk var?
- Hedefe kalan alan risk karşısında yeterli mi; hedef çok yakınsa fırsat düşük kaliteli olarak mı sınıflandırılmalı, yoksa değerlendirme dışı mı bırakılmalı?
- Eksik veri, geçersizleşme koşulu veya sonucu zayıflatan başka bir engel var mı?

Yakın direnç, teknik bulgulara dayalı olası kâr alma bölgesidir; kesin fiyat tahmini veya otomatik satış emri değildir. Teknik hedefler, gerçek destek/direnç ve fiyat yapısıyla gerekçelendirilir. Sadece matematiksel risk katları kullanılarak teknik hedef belirlenmiş gibi gösterilmez diğer fonksiyonlarada bakılır.

Mevcut README'de kayıtlı başlangıç davranışı korunarak dikkate alınır: güçlü fırsat kapısı, en yakın teknik hedef için brüt teknik risk/getiri oranının en az 1,5 olmasını ister; spread ayrı likidite filtresinde değerlendirilir. Bu mevcut kural sessizce değiştirilmez. Eşiğin veya düşük kaliteli fırsatları dışlama koşullarının değiştirilmesi gerekiyorsa kod incelemesi, gerekçeli tasarım ve geçmiş verilerle doğrulama gerekir. Mevcut `ayarlar.json` komisyon/kayma ayarlarını içermez ve mevcut sürüm bu maliyetleri hesaplamaz. Masraflar sonrası net risk/getiri gereksinimi, maliyet varsayımları açıkça tanımlanıp uygulanıp test edilene kadar mevcut özellikmiş gibi gösterilmez.

### 9. Panel yerleşimi ve gösterilecek bilgiler — kabul edilmiş hedef tasarım

Bu bölüm gereksinim/tasarım kaydıdır; maddelerin tamamının mevcut ZIP içinde uygulandığı iddiası değildir. Mevcut arayüzün gerçek hâli README’nin başındaki “Arayüzün mevcut hali” bölümünde kodla karşılaştırılarak yazılmıştır. Henüz uygulanmamış kararlar değiştirilmeden korunur.

#### Kullanıcının kesinleştirdiği görünüm ve mevcut kontroller — hedef gereksinimler

- Hedef çalışma ortamı Windows, ekran çözünürlüğü 1920×1080 ve Windows ölçeklendirmesi %125'tir. Panel başlangıçta ekran genişliğinin yaklaşık yarısına sığacak şekilde tasarlanır; okunabilirlik gerektirirse genişlik en fazla ekranın yaklaşık %80'ine çıkarılabilir. Pencere yüksekliği ekran yüksekliğinden en az %10 daha kısa olmalıdır.
- **Panel arka planı siyah olacak; ayırıcı çizgiler beyaz olacaktır.** Durum renklerinde kırmızı, sarı, mavi, yeşil, açık mor/lila, turkuaz ve lacivert kullanılabilir. Renk tek başına karar gerekçesi sayılmaz; her önemli rengin anlaşılır metinsel karşılığı bulunur. Siyah arka plan henüz uygulanmadığı için bu madde hedef tasarım olarak kalır.
- Ses seviyesi kontrolüne benzer `Panel Işığı` ayarı kodda vardır ve ses kontrollerinin yanında yer alır. Bununla birlikte kod şu an siyah yerine gri tonları üretir; ayar anahtarı tutarsızlığı da yukarıdaki güncel durum bölümünde kayıtlıdır. Hedef arka plan siyah olma kararını bu kontrolün mevcut olması karşılamaz.
- Mevcut yararlı kontroller korunur veya aynı işlev açık kalacak şekilde uyarlanır: parite listesini güncelleme, rapor devir ZIP'i oluşturma, Başlat, Durdur, Alarm Açık/Kapalı, ses seviyesi, sesi testi ve seçilen coin için giriş/hedef seviyelerini izleme. Kontrol etiketleri tasarım onayında tutarlılaştırılır.
- Adayların mevcut A/B/C aşamaları ve anlamları korunur: A hazırlık, B yapı/kırılım, C devamlılık. Kapalı mumda katılım, geri test ve devamlılık teyitleri kaybolmaz. Eski/eksik veri için renkli bir yazı uyarısı korunur.
- Karar alanları mevcut işlevler üzerinden düzenlenir: **Adaylar** listesi; **Giriş Kontrolü** içinde senaryo zaman dilimi, kırılım seviyesi, zarar durdurma ve olası giriş; **Seçilen Coin** içinde kırılım seviyesi, zarar durdurma ve teknik hedefler. Bunlar ham hesap çıktıları yığınına çevrilmez; hızlı karar bilgisi öne çıkarılır, ayrıntılar erişilebilir kalır.
- Yerleşim ve ölçüler için tasarım kararı kod değişikliğinden önce gözden geçirilir. Bu maddeler kabul edilmiş arayüz gereksinimleridir; mevcut panelin hepsini uyguladığı veya gerçek Windows ekranında doğrulandığı anlamına gelmez.

#### A. Üst bölüm — BTC ve genel piyasa

Mevcut motor durumu, bağlantı bilgileri, alarmlar ve parite evreni bilgileri korunur. Mevcut **“Piyasa ve parite ”** alanı kaldırılmaz; BTC piyasa bağlamıyla genişletilir. Burada kısa ve anlaşılır biçimde şu bilgiler gösterilir; önemli kelime ve rakamlar anlam bütünlüğü korunarak vurgulanır:

- BTC ana yönü ve genel piyasa risk durumu.
- Güçlü destek ve direnç bölgeleri.
- Yatay kanal varsa alt ve üst sınırları.
- Önemli kırılım veya önemli seviye kaybı.
- Verinin güncel olup olmadığı ve varsa veri eksikliği.

BTC özeti nedeniyle mevcut parite evreninin kapsamı veya durumu kaybolmaz.

#### B. Orta bölüm — öncelikli adaylar

Mevcut aday tablosu korunur. A/B/C aşamaları, fiyat, veri durumu, zaman dilimi ve keşif yolu bilgileri kaybolmaz. Tabloyu gereksiz kalabalıklaştırmadan coin için kısa bir **BTC'ye göre durum** bilgisi eklenir; adayın BTC'den daha güçlü veya daha zayıf performans gösterip göstermediği ilk bakışta anlaşılabilir. Önemli kelime ve rakamlar anlam bütünlüğü korunarak vurgulanır:

Ayrıntılı korelasyon değerleri aday tablosunu doldurmak yerine seçilen coin bölümünde gösterilir. Yeni hesaplamaların gösterimi mevcut aday sıralamasını veya aşama sınıflandırmasını sessizce değiştirmez. Sıralama veya sınıflandırma mantığında yapılacak değişiklik ayrı olarak gerekçelendirilip test edilir.

#### C. Seçilen coin — hızlı karar özeti ve teknik ayrıntılar

Mevcut **“Seçilen adayın özeti”** alanı, hızlı karar özeti ile ayrıntılı analiz olmak üzere iki bölüme ayrılır.

**Sol bölüm — hızlı karar özeti:**

- Coinin mevcut teknik aşaması.
- BTC ile ilişkisi, BTC'ye göre performansı ve BTC koşullarının aday üzerindeki etkisi.
- Ana fiyat yapısı: yükseliş, düşüş veya yatay kanal.
- En önemli yakın destek ve direnç bölgeleri.
- Fırsatın önündeki temel engel veya eksik teyit.
- Açıklanabilir genel durum: “izlemeye değer”, “teyit bekleniyor”, “risk yüksek” veya “veri yetersiz” gibi sonuçlar. Önemli kelimeler ve rakamlar anlam bütünlüğü korunarak vurgulanır.

**Sağ bölüm — mevcut ayrıntılı analiz:**

- EMA, MACD, RSI, ADX, DMI ve ATR gibi mevcut teknik bulgular.
- Sekiz zaman diliminin değerlendirmeleri.
- A/B/C aşamasının gerekçeleri.
- Mevcut analiz ve kontrollerin sonuçları, eksik kontroller ve veri güncelliği.

Hızlı özet, ayrıntılı analizin yerine geçmez; mevcut teknik bulguları anlaşılır bir karar görünümünde birleştirir. Renkler ve etiketler sonucu özetleyebilir, ancak bir rengin kendisi karar gerekçesi olamaz. Her önemli uyarının anlaşılır bir nedeni bulunur. Gösterilen durumlar otomatik alım-satım kararı değil, öngörü içindir.

#### D. Alt bölüm — giriş, hedef ve risk kontrolü

Mevcut giriş kontrolü alanı korunur. Bilgiler birbirinden açıkça ayrılır:

| Gösterim | İçerik |
|---|---|
| Giriş | Mevcut koşullu giriş bölgesi ve kırılım seviyesi |
| Zarar durdurma | Stop seviyesi ve girişe göre fiyat/yüzde riski |
| Teknik hedef | Gerçek direnç bölgesine ve fiyat yapısına dayanan olası hedef/kâr alma bölgesi |
| Net risk/getiri | Hedefe kalan getiri ile stop riski; masraflar sonrası karşılaştırma yalnızca masraf varsayımları hesaplanıp doğrulandığında gösterilir |
| Matematiksel hedefler | Mevcut 1R/2R/3R risk katı projeksiyonları |
| Son durum | Giriş koşulu, geçersizleşme şartı, eksik veri ve teyit uyarıları |

Gerçek teknik hedef ile matematiksel hedef aynı şeymiş gibi gösterilmez. Teknik hedefe ulaşmak için kalan getiri yetersizse bu, hızlı özette açıkça belirtilir ve fırsat kalitesi kuralları uygulanır. Teknik hedef otomatik emir değildir.

### 10. Aşamalı uygulama, doğrulama ve sürüm geçişi

Bu yol haritası, üzerinde çalışılıp doğrulanacak **tasarım planıdır**. Listelenen bir özellik, kodda uygulanıp test edilmeden tamamlanmış olarak raporlanmaz. Her aşamanın sonucu doğrulanmadan sonraki aşamada o sonuç gerçekleşmiş kabul edilmez.

1. **Mevcut sistemi güvenceye alma:** Kod, fonksiyonlar ve testler incelenir; mevcut davranışlar kayıt altına alınır ve mevcut–eksik–geliştirme–test matrisi hazırlanır.
2. **Hesaplama altyapısını geliştirme:** Ortak veri kullanımının, BTC değerlendirmesinin ve teknik yapı hesaplarının mevcut modüllere nasıl bağlanacağı belirlenir.
3. **Hedef ve risk katmanını tamamlama:** Gerçek direnç hedefleri, masraf varsayımları ve net risk/getiri koşulları tanımlanır. Mevcut davranış ile planlanan geliştirme ayrı tutulur.
4. **Ortak sonuç yapısını kurma:** BTC raporu ve coin bazındaki sonuçlar tek, tutarlı bir veri akışında birleştirilir; mevcut hesaplamaların yinelenmesi önlenir.
5. **Panel yerleşimini uygulama:** Önce üst bölümde genel BTC görünümü, ardından aday tablosu ve seçilen coin özeti/ayrıntıları, son olarak alt giriş-hedef-risk alanı düzenlenir.
6. **Doğrulama:** Hesaplamalar için birim testleri, önceki işlevlerin bozulmadığını kontrol etmek için regresyon testleri ve geçmiş piyasa verileriyle kontroller yapılır.
7. **Paket ve son kontrol:** Hesaplamalar, panel davranışları, mevcut işlevler ve raporlama birlikte test edilir. Raporlama, alarm davranışı, veri güncelliği ve panel sonuçlarının tutarlılığı; paket bütünlüğü ve sürüm kayıtları doğrulanır.

#### Son doğrulama ve sürüm 00 → sürüm 1 geçişi

- Son doğrulama aşamasında yeni özellikler tek başına değil, mevcut sistemin bütünüyle birlikte değerlendirilir.
- Test sonucu, kod ve sürüm kayıtlarıyla kanıtlanmayan hiçbir iş tamamlandı diye işaretlenmez. Başarısız testler çözülmeden sürüm hazır kabul edilmez.
- Paket bütünlüğü ve sürüm kayıtları doğrulanmadan dağıtıma hazır paket ilan edilmez.
- Sürüm 00, başlangıç tabanı olarak main dalında tutulur. Bu başlangıç hazırlığındaki README tutarlılık düzeltmesi ve APP_VERSION = "00" etiketi, yalnızca başlangıç noktasını tanımlar; tasarlanan yeni özelliklerin uygulanması veya test edilmesi değildir.
- Sürüm 00 başlangıç tabanı `main` üzerinde korunur. Sürüm 1 için bir dal ancak kullanıcı önceden açıkça onay verdikten sonra açılır ve adı `1.surum-readme-gereksinimler` olur. Bu dalda yapılacak değişiklikler, gerekli hesaplama, regresyon, geçmiş veri, panel, raporlama ve paket kontrolleri tamamlanmadan ve kullanıcı onayı alınmadan `main` dalına aktarılmaz. Dal açma onayı, kodlama veya birleştirme onayı sayılmaz.
- **Yeni sürüm 1**, yalnızca gerekli kontroller tamamlandıktan ve sonuçları doğrulandıktan sonra hazırlanır. README'ye tasarım planının kaydedilmesi veya sürüm etiketinin değiştirilmesi, özelliklerin tamamlandığı ya da ZIP paketinin hazır olduğu anlamına gelmez.

Bu gereksinimlerin README'ye kaydedilmesi tek başına kod değişikliği değildir. İlk uygulama işi, mevcut kodun kanıtlarla incelenmesi ve fonksiyon bazında matrisin doldurulmasıdır; sonuçlara göre her eksikliğin hangi mevcut modüle bağlanacağı, hangi hesaplamayı yeniden kullanacağı ve nasıl doğrulanacağı belirlenecektir.

## [Tarihsel uygulama kaydı] 25 Ekim 2026 — motor ve panel değişiklikleri

### Bu düzeltme grubunda uygulanan kod değişiklikleri

- Sürüm etiketi `APP_VERSION = "00"` olarak korunmuştur. Programın tek motorlu mimarisi ve mevcut hesaplamaları baştan yazılmamıştır.
- `radar_core.py` içinde BTC korelasyonu, tek başına yön sinyali veya pozitif puan sayılmaz. Yalnızca eşzamanlı kapanmış mumlardan yeterli 1h/4h korelasyonu varsa, BTC bağlamı tam ve riskliyse aday puanına risk düzeltmesi eklenir: ortalama korelasyon ≥0,80 için -6 puan; ≥0,60 için -3 puan. Eski/eksik BTC bağlamında, ölçüm örnek sayısı yetersizse, BTC bağlamı sağlıklıysa veya ortalama korelasyon 0,60'ın altındaysa ceza uygulanmaz. Negatif korelasyon ayrıca olumlu puan getirmez.
- `tek_motor_paneli.pyw` içinde BTC 1h/4h piyasa bağlamı, seçilen coin hızlı karar metninde göreceli güç/korelasyon açıklamaları, destek/direnç, koşullu giriş, zarar durdurma, teknik hedef ve eksik teyitler bulunur. **Mevcut aday tablosunun sekiz sütununda ayrı BTC göreceli güç/korelasyon sütunu yoktur**; bu, kabul edilmiş hedef tasarımla karşılaştırıldığında açık UI farkıdır.
- Pencere boyutu ekran ölçülerine göre hesaplanıp ortalanır. Ses kontrollerine yakın, ayarları kaydedilen açık-gri aralıkta aydınlık kontrolü eklenmiştir.
- Adayın göreceli güç/korelasyon alanları motor ve rapor verisinde bulunur. Mevcut masaüstü aday tablosunda bu alanlar ayrı sütun değildir; ayrıntı seçilen coin alanında gösterilir.
- Aday tablosunda karar sınıflarını yeşil/kırmızı/sarı/mavi/lila/turkuaz ve A/B/C aşamalarını ayırt eden renk etiketleri eklenmiştir; eski/eksik veri gri uyarı olarak kalır.
- `tests/test_btc_correlation_adjustment.py` içine eşik, riskli/sağlıklı BTC, eski veri, yetersiz örnek, negatif korelasyon ve puan bileşeni için otomatik testler eklendi. `.github/workflows/validate-and-package.yml`, kaynak derleme ve otomatik testler için `ubuntu-slim` kullanır; ayrıca ayar JSON'ları doğrulanır. Bu 25 Ekim tarihli kayıtta o dönemki iş akışının her `main` gönderiminde paket oluşturduğu belirtiliyordu. 27 Ekim 2026 tarihli politika düzeltmesiyle olağan `main` gönderimleri yalnızca doğrulama yapar. Açıkça istenen son paketlemede program ZIP'i, SHA-256 doğrulama dosyası ve Actions artefaktı hazırlanır. Bunların tamamını indirmen gerekmez; program için ZIP yeterlidir. Bu kaynak doğrulaması, Windows masaüstü arayüzünün görsel veya canlı çalıştırma testi değildir.
- Tarihsel politika notu: Önceki iş akışı sürümünde ZIP ve SHA-256 dosyası her `main` push çalıştırmasında üretiliyordu; bu davranış sonradan ayrıştırılmıştı. Güncel otomasyon yeniden düzenlendi: testleri geçen her `main` push'u Sürüm 01 deneme ZIP'i, SHA-256 ve 14 günlük Actions artefaktı üretir; kalıcı Release dosyaları yalnızca açık paketleme çalıştırmasında değiştirilir. Windows denemesi için ZIP'i indirmen yeterlidir.

### Tarihsel doğrulama notları — güncel durum için üstteki kayıt esas alınır

- **Tarihsel CI notu:** Önceki bazı Actions denemelerinde çalıştırıcı atanmamış ve komut adımları başlamamıştı. Bu, o denemelerin sonucunu açıklar; 27 Ekim 2026 itibarıyla güncel çalışma durumunu tanımlamaz. Programın Render üzerinden veri alması ve raporların buluttan okunabilmesi sonraki gerçek kullanımda doğrulandı. Eski Python/JavaScript test sonuçları güncel işlevin yerine geçen bir kanıt olarak kullanılmamalı; gerektiğinde yalnızca kod değişiklikleri için regresyon kontrolü sayılmalıdır. [Sürüm 00 doğrulama geçmişi](https://github.com/erdaly1947-max/matrix/actions/workflows/validate-and-package.yml?query=branch%3Amain).
- Güncel paketleme politikası: her başarılı `main` gönderimi yeni bir Sürüm 01 deneme ZIP'i ve Actions artefaktı üretir; kalıcı GitHub Release indirme dosyası sıradan gönderimlerle güncellenmez. Render üzerinden programın piyasa verisi alması güncel çalışma durumunda doğrulanmıştır. Tarihsel backtest ve gerçek Windows masaüstünde panel taşma/etkileşim kontrolü ayrı açık işlerdir.
- Komisyon ve kayma sonrası net getiri hesabı eklenmedi ve bilerek eklenmeyecektir. Teknik risk/getiri brüt kalır; emir gönderimi veya otomatik alım-satım bulunmaz.
- Programın dağıtım ZIP'i kalıcı bağlantıdan indirilebilir: https://github.com/erdaly1947-max/matrix/releases/download/surum-00/Firsat-Kontrol-Paneli-Surum-00.zip . Programı kullanmak için yalnızca bu dosyayı indirmen yeterlidir. Olağan `main` gönderimlerinde ZIP yenilenmez; yalnızca açıkça başlatılan ve başarılı son paketleme işleminde güncellenir.
- **25 Ekim 2026 tarihli ağ/TLS tanısı (tarihsel):** O gün kullanıcının ev internetinden doğrudan Binance/BtcTurk REST adreslerine erişimde `TLS WRONG_VERSION_NUMBER` ve Windows `curl.exe` için `SEC_E_INVALID_TOKEN` görüldü. O bulgu doğrudan ağ yolunu tanımlıyordu. Daha sonra piyasa verisi Render geçidi üzerinden alınacak şekilde kuruldu; 27 Ekim 2026 güncel durumunda programın Render üzerinden veri aldığı kullanıcı tarafından doğrulandı. Dolayısıyla eski doğrudan TLS hatası, mevcut Render veri akışının başarısız olduğu anlamına gelmez. CI/Python/JavaScript test kayıtları bu güncel çalışma durumunun yerine geçmez; yalnızca tarihsel teknik kayıttır.
- **Tarihsel not:** Bu kaydın yazıldığı sırada kullanıcının yerel test sonucu bekleniyordu. 27 Ekim 2026 tarihinde kullanıcı son Sürüm 00 paketini yerel bilgisayarında başlatıp rapor gönderdi. Açık işler ve henüz uygulanmamış tasarım kararları güncel durum bölümünde listelenir. Dal açma kuralı değişmez: kullanıcı önceden açıkça onay vermeden yeni dal açılmaz.



## [Tarihsel teknik kayıt] Ağ bağımsız piyasa verisi geçidine geçiş

### 25 Ekim tanılamasının tarihsel bulguları

- 25 Ekim 2026 tarihli Windows tanılamasında, bilgisayar evdeki TurkTelekom_ZWR3J ağına bağlıyken data-api.binance.vision:443 için TLS ClientHello sonrasında TLS yanıtı yerine düz HTTP 307 Temporary Redirect alındı. Yönlendirme guvenliinternet.turktelekom.com.tr alan adına gidiyordu ve yanıtta Via başlığı vardı. Bu, söz konusu ağ bağlantısında Türk Telekom Güvenli İnternet filtre/yönlendirmesiyle uyumludur.
- Aynı ev Wi-Fi bağlantısında telefondan borsa siteleri açılırken, bilgisayar telefonun mobil erişim noktasına bağlandığında programın ve tarayıcının çalışması; sorunun masaüstü programının temel veri işleme kodundan ziyade bilgisayarın ev interneti üzerindeki HTTPS/TLS yolunda olduğunu gösteren karşılaştırmalı kanıttır.
- Windows ortam değişkenleri, Windows Internet Settings ve WinHTTP kontrollerinde yapılandırılmış proxy bulunmadı. Bu nedenle bu sorun için proxy kurulması veya proxy ayarlarının değiştirilmesi çözüm olarak kaydedilmemelidir.
- Doğrudan ağ yolundaki yönlendirme yerel program tarafından güvenli biçimde düzeltilemeyeceğinden, halka açık piyasa verisinin ayrı bir bulut sunucusundan alınması ve uygulamaya HTTPS/WebSocket üzerinden iletilmesi yaklaşımı seçildi. 

### Tarihsel deneme: Cloudflare Workers ile piyasa verisi

- Ücretsiz Cloudflare Worker oluşturulup dağıtıldı. Worker sağlık uç noktası ve BtcTurk halka açık USDT ticker isteği çalıştı.
- Aynı Worker üzerinden Binance REST istekleri denendi; Cloudflare çıkışından yapılan istekler Binance tarafında HTTP 403/451 ile engellendi. Birden fazla resmî Binance API ana makinesini denemek de sorunu çözmedi. Bu nedenle Cloudflare Worker, Binance piyasa verisi için uygun aktif geçit olarak doğrulanmadı.
- Sonuç: Cloudflare denemesi boşa gitmiş bir kod değişikliği değildir; sorunun kaynağını ayıran ve hangi ücretsiz altyapının bu kullanımda çalışmadığını kanıtlayan bir deneydir. Cloudflare piyasa verisi denemesiyle ilgili tarihsel bilgiler depodaki ilgili kayıt dosyalarında tutulur; güncel masaüstü ZIP'i artık Cloudflare adresine bağımlı değildir.
- Cloudflare hesabındaki Worker'ı silmek gerekmez. Güncel uygulama için geçerli adres, ZIP'e yazılan market_data_relay.json dosyasındaki Render adresidir. Eski Cloudflare dağıtımını yeniden etkinleştirmek, Binance veri akışının çalıştığı anlamına gelmez.

### Masaüstü ZIP içinde yapılandırılan piyasa geçidi — Render

- Aktif hizmet adı: firsat-kontrol-market-relay.
- Bölge ve plan: Frankfurt, Render Free Web Service.
- Genel adres: https://firsat-kontrol-market-relay.onrender.com
- Sağlık kontrolü: https://firsat-kontrol-market-relay.onrender.com/healthz
- Render yönetim ekranı: https://dashboard.render.com/web/srv-dbf3n80n74is73beeeog
- Kaynak kod: render_relay/server.js, render_relay/package.json, render_relay/test/server.test.js ve render_relay/smoke-check.mjs.
- Hizmet yalnızca izin listesine alınmış halka açık piyasa verisi uç noktalarını ve Binance genel mum WebSocket akışlarını iletir. Borsa hesabı girişi, API anahtarı, bakiye/pozisyon erişimi, emir oluşturma veya işlem yürütme özelliği yoktur. Rastgele URL'lere vekil isteği göndermeye izin verilmez.
- GitHub deposunun main dalına bağlı otomatik dağıtım açıktır. Yeni commit geldiğinde Render hizmeti kaynak koddan tekrar oluşturulup dağıtılır.

### [Tarihsel] Canlı bağlantı doğrulaması — 25 Ekim 2026

GitHub Actions çalıştırması [40216714717 — canlı Render piyasa verisi testi](https://github.com/erdaly1947-max/matrix/actions/runs/40216714717) aşağıdaki kontrolleri başarıyla tamamladı:

1. Render /healthz uç noktası HTTP 200 döndürdü.
2. Binance exchangeInfo yanıtı alındı; 3.736 sembol listelendi ve BTCUSDT etkin Spot paritesi doğrulandı.
3. Binance BTCUSDT 5 dakikalık mum uç noktasından mum verisi alındı.
4. BtcTurk halka açık USDT ticker yanıtı alındı.
5. Binance WebSocket bağlantı el sıkışması tamamlandı ve gerçek bir kline/mum mesajı alındı.
6. Python kaynak derleme, Python otomatik testleri, Cloudflare geçidi JavaScript testleri, Render geçidi testleri, canlı piyasa verisi kontrolleri, ZIP bütünlüğü, SHA-256 üretimi ve Release dosyalarının güncellenmesi başarılı oldu.

Bu tarihsel sonuç, bulut sunucusunun ilgili uç noktalara o test anında erişebildiğini kanıtlar; güncel çalışma için son kullanıcı raporları ve en üstteki paket doğrulaması esas alınır. Gelecekteki kesintisiz erişim garantisi değildir. Ücretsiz Render hizmeti 15 dakika boyunca gelen HTTP isteği veya açık WebSocket bağlantısından gelen mesaj almazsa uykuya geçebilir. Sonraki istek/bağlantı hizmeti uyandırır ve ilk yanıt gecikebilir. Bu ücretsiz plan sınırı nedeniyle program ilk bağlantıda bekleme veya yeniden bağlanma yaşayabilir. Güncel davranış için [Render ücretsiz hizmet sınırları](https://render.com/docs/free) incelenebilir.

### Program ZIP'ini indirme ve paketleme

- **Sürüm 01 Windows deneme ZIP'i:** [Kalıcı Release indirme bağlantısı](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/releases/download/surum-01/Firsat-Kontrol-Paneli-Surum-01.zip). Bu bağlantı, en son başarılı ve açıkça onaylanmış paketleme işleminde güncellenir.
- **Sürüm 01 SHA-256 doğrulama dosyası:** [Firsat-Kontrol-Paneli-Surum-01.zip.sha256](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/releases/download/surum-01/Firsat-Kontrol-Paneli-Surum-01.zip.sha256).
- **Sürüm 00 başlangıç tabanının sabit ZIP'i:** [Firsat-Kontrol-Paneli-Surum-00.zip](https://github.com/erdaly1947-max/matrix/releases/download/surum-00/Firsat-Kontrol-Paneli-Surum-00.zip). Bu eski başlangıç paketidir; Sürüm 01 deneme paketinin yerine geçmez.
- Sürüm 01 [Actions doğrulama ve paketleme geçmişi](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/actions/workflows/validate-and-package.yml?query=branch%3Amain).

GitHub Actions Python 3.14.8 ortamında kaynak derlemesini ve otomatik testleri, Node.js 22 ortamında geçit testlerini ve canlı Render/Binance/BtcTurk REST + WebSocket kontrollerini çalıştırır. Açık `workflow_dispatch` çalışmasında `publish_package=true` seçilmelidir; zorunlu testler başarılıysa Sürüm 01 ZIP'i, SHA-256 doğrulama dosyası ve 14 gün saklanan Actions artefaktı oluşturulur ve kalıcı `surum-01` Release dosyaları güncellenir. Başarısız testlerde paket yayımlanmaz. **Normal teslimde kullanıcıya program ZIP'i doğrudan sohbet içinde indirilebilir dosya bağlantısı olarak verilir; kullanıcının GitHub Actions artefaktını elle bulup indirmesi istenmez.**

Programa ait dağıtım ZIP'ine gerekli masaüstü dosyaları ve `market_data_relay.json` eklenir. Sunucunun Node.js kaynakları (`render_relay/`) masaüstü ZIP'ine konmaz; Render bunları GitHub deposundan kendisi oluşturur. Paket içindeki `market_data_relay.json` aktif Render adresini göstermelidir. ZIP'in bütünlüğü paketleme sırasında kontrol edilir; SHA-256 dosyası ayrıca üretilir.

### Tekrarlanabilir çözüm / gelecekteki bakım

1. Bilgisayarın doğrudan HTTPS erişimi tekrar bozulursa önce mevcut tanılama sonuçları ve ağdaki yönlendirme hedefi incelenir; doğrulanmış Türk Telekom filtre bulgusu unutulup yeniden proxy ayarı aranmamalıdır.
2. Bulut geçidi değiştirilecekse önce sunucu sağlık kontrolü, gerçek Binance REST mum verisi, BtcTurk USDT ticker'ı ve gerçek Binance WebSocket mum mesajı ayrı ayrı doğrulanır. Sadece sunucunun live olması yeterli değildir.
3. Yeni geçidin adresi kaynak market_data_relay.json dosyasına yazılır; GitHub Actions içinde güncel paket adresi ve canlı smoke-test adresi aynı tutulur. Bu iki adresin tutarsız kalmasına izin verilmez.
4. Kod veya yapılandırma `main` dalına kaydedildiğinde otomatik doğrulama yapılır ve testler başarılıysa Windows denemesi için yeni Sürüm 01 ZIP'i/Actions artefaktı oluşturulur. Kalıcı Release indirme bağlantısı yalnızca kullanıcı açık paketleme çalıştırması istediğinde güncellenir.
5. Render ücretsiz hizmeti kullanım dışı kaldığında uykuya geçebileceği için, taramaya yeniden başlanırken ilk bağlantı gecikmesi ve WebSocket yeniden bağlanma durumu normalleştirilmeden canlı piyasa verisi güncel kabul edilmez.

## Bulut bağlantısı — Analiz raporu ve okunabilir rapor uçları

Paneldeki **Analiz Raporu** butonu, motor tanı raporlarından ayrı bir teknik analiz özeti üretir. Güncel kullanıcı çalıştırmasında `/latest`, `/daily` ve `/troubleshooting` JSON uçlarının içerikleri okunabildi; bu, raporların gönderildikleri her anda birbirleriyle eşzamanlı oldukları anlamına gelmez. Aday puanları ve kararları, zaman dilimi bulguları, seçilmiş teknik göstergeler, BTC piyasa bağlamı, veri yeterliliği ve koşullu giriş/stop/hedef planları rapora dahil edilir. Ham mum dizileri ve motor tanılama alanları bu rapora dahil edilmez.

Analiz raporu JSON olarak hazırlanır ve gzip ile sıkıştırılır. Yerel kopya sabit `reports/analiz_raporu.json.gz` dosyasına yazılır; her yeni rapor aynı dosyanın üzerine kaydedilir, tarihli yeni dosya oluşturulmaz. Günlük durum raporunun JSON, Markdown ve tanı dosyaları da sabit dosya adlarıyla gzip biçiminde saklanır ve her üretimde öncekinin üzerine yazılır; Markdown metni kolay inceleme için panoya normal metin olarak kopyalanır. Devir paketi `reports/firsat_kontrol_devir.zip` sabit adıyla oluşturulur ve önceki paketin üzerine yazılır. Sunucu bağlantısı yapılandırılmamışsa panel yalnızca yerel dosyaları üretir; piyasa taramasını etkilemez. Yapılandırılmışsa rapor HTTPS üzerinden, yetkilendirilmiş yükleme uç noktasına arka planda gönderilir.

Bağlantı mimarisi: [Cloudflare rapor Worker kılavuzu](cloudflare/report-worker/README.md). Worker adresi programda sabittir; yükleme anahtarı Windows Kimlik Bilgileri Yöneticisi'nde saklanır. İlk güncellemede ZIP'i mevcut program klasörüne ayıklayın ve eski chatgpt_baglanti.local.json dosyasını önceden silmeyin. Programın ilk açılışında yalnızca bilinen Worker adresi kabul edilir; anahtar Windows kasasına taşınır, geri okunarak doğrulanır ve bundan sonra eski dosya silinir. Kayıt başarısızsa dosya korunur.

**Güvenlik:** Kod commitleri Worker dağıtımını veya Cloudflare gizli anahtarının (UPLOAD_TOKEN) kurulumunu değiştirmez; mevcut Worker ve anahtar ayrı kalır. Tüm yükleme uç noktaları Bearer anahtarını doğrular. Okuma adresleri bağlantıyı bilenlere açıktır; raporlara parola veya başka gizli bilgi koymayın. ChatGPT sohbetine otomatik mesaj gönderilmez; rapor bağlantısı ayrıca açılarak okunur.


## Aday tablosu

Aday tablosu Binance fiyatının yanında BtcTurk fiyatını, puanı, zaman dilimini, A/B/C aşamasını, veri durumunu ve son kararı gösterir. BtcTurk fiyatı görüntüleme içindir; Binance analiz motorunun fiyat/mum kaynağı değildir. Fiyat farkı sütunu yoktur. Hedef tasarımda önemli kelime ve rakamların renk/hiyerarşiyle vurgulanması gerekir; renk tek başına karar gerekçesi olamaz.


## Üç raporlama düğmesi — mevcut arayüz etiketleri

- **Günlük Rapor:** Programın genel durumunu ve çalışma özetini üç gzip dosyası olarak yerel reports klasörüne kaydeder: `.json.gz`, `.md.gz` ve `_tani.json.gz`. Markdown metni ayrıca panoya okunabilir metin olarak kopyalanır.
- **Sorun Giderme ve Devir Paketi (ZIP):** Sıkıştırılmış günlük raporları, gzip biçimindeki tanı özeti ve sınırlı günlük kaydını, bütünlük manifestiyle birlikte tek ZIP dosyasında toplar.
- **Analiz Raporu:** Radarın coin analiz sonuçlarını `.json.gz` biçiminde yerel dosyaya kaydeder ve bağlantı ayarlanmışsa aynı sıkıştırılmış içeriği sunucuya gönderir. Bu rapor motor tanılamasını veya günlük kayıtlarını içermez.

Bu üç düğme farklı amaçlara hizmet eder; birbirlerinin yerine geçmez.

## Sürüm 01 — Ekran görüntülerini buluta yükleme ve ChatGPT'de okuma

### Uçtan uca akış — başarılı yöntem

1. **Kullanıcının gönderimi:** Windows masaüstü panelindeki 📷 düğmesi dosya seçiciyi açar. Kullanıcı 1–3 PNG/JPG/JPEG dosyasını kendisi seçer. Dosyalar otomatik olarak klasörden topluca alınmaz. Her görüntü 15 MiB sınırını geçmemeli; türü ve dosya imzası doğrulanır. Asıl görüntü verisi küçültülmez veya yeniden sıkıştırılmaz.
2. **Masaüstü → Render test geçidi:** `analysis_report.py`, HTTPS üzerinden `https://firsat-kontrol-test-relay.onrender.com` adresine bağlanır. Önce `/healthz` ile servis uyandırılır/doğrulanır; geçici ağ/cold-start hatalarında GET istekleri sınırlı yeniden denemeler kullanır. Görüntü yükleme POST'ları körlemesine tekrarlanmaz.
3. **Render → Cloudinary:** `render_relay/server.js`, `/api/images/stage` isteğinde PNG/JPEG içeriğini doğrular ve Render'da tutulan `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` değerleriyle Cloudinary API'sine yükler. API Secret masaüstü programına, README'ye, GitHub'a veya sohbet mesajlarına yazılmaz. Her yükleme `fkp_screenshot_<UUID>` kimliği ve `fkp-staged` etiketiyle geçici olarak saklanır; orijinal dosya adı metadata içinde korunur.
4. **Grup halinde etkinleştirme ve üç görsel sınırı:** Seçilen dosyaların tümü geçici yüklemeyi başarıyla tamamladıktan sonra `/api/images/commit` çağrılır. Sunucu yeni görüntüleri etkinleştirir ve etkin listeyi en fazla üç kayıtla sınırlar; yeni yükleme daha eski kayıtlardan yer açmayı gerektirirse en eski görüntü kaldırılır. Bir grup başarısız olursa mevcut etkin listeyi yarım bırakmamak için commit iptal edilir ve geçici görüntüler temizlenmeye çalışılır.
5. **Listeleme:** `GET /images/manifest` yalnızca etkin kayıtların `id`, `filename`, `content_type`, `size_bytes` ve `uploaded_at` metadata alanlarını JSON olarak döndürür. Manifestte görünmesi, tek başına görüntünün içeriğinin açılıp okunduğu anlamına gelmez.
6. **ChatGPT tarafında görüntüyü açma:** Önce `/healthz`, sonra `/images/manifest` çağrılır. İncelenecek görüntünün UUID'si manifestten alınır ve `GET /images/{UUID}?format=base64` isteği yapılır. Yanıt `application/json` biçimindedir; `ok`, `id`, `content_type`, `size_bytes`, `encoding: "base64"` ve `data` alanlarını içerir. `data` alanı `data:image/png;base64,...` veya JPEG karşılığına dönüştürülür ve görseli okuyabilen görüntü aracına verilir. Böylece yalnızca URL'nin döndüğünü değil, görsel piksel içeriğini gerçekten okuyup açıklayabildiğimizi doğrularız.

### Neden bu düzeltme gerekiyordu?

- Normal `GET /images/{UUID}` yolu, doğru biçimde `image/png` veya `image/jpeg` ikili yanıtı döndürür. Ancak bu oturumdaki metin ağırlıklı web okuma/aracısı, ikili görüntü içeriğini doğrudan alamayıp `CRAWL_UNEXPECTED_CONTENT_TYPE` hatası verdi. Bu hata, Cloudinary'ye yüklemenin veya dosyanın bozuk olduğunu göstermiyordu.
- Çözüm olarak `render_relay/server.js` içine isteğe bağlı `?format=base64` inceleme yolu eklendi. Bu seçenek normal PNG/JPEG indirme yolunu değiştirmez; yalnızca JSON üzerinden inceleme gerektiğinde devreye girer. Gerçek görüntü indirme ve Base64'ten tekrar baytlara çözme kontrolleri `render_relay/test/cloudinary-images.test.js` regresyon testine eklendi.
- **İnceleme yolu sınırı:** güvenli metin yanıtı için görüntü baytları 512 KiB ile sınırlıdır. Bu sınır aşılırsa yanıt `413` döner; bu, görüntünün bulutta olmadığı anlamına gelmez. Büyük görüntüleri incelemek için parçalı aktarım gibi ayrı bir çözüm gerekir. Orijinal yükleme sınırı ise 15 MiB/görüntü olarak kalır.
- ChatGPT tarafında başarılı görüntü okuma yöntemi: manifestten UUID'yi bul → `?format=base64` JSON yanıtını al → `data` alanını data URI'ya dönüştür → görseli görsel okuma aracına ver. Sadece manifest başlıklarına veya arama sonucunda görünen küçük önizlemeye dayanarak “görseli açtım” denmez.

### 28 Ekim 2026 — uçtan uca doğrulama kaydı

- Kullanıcı Windows programından üç görüntü yükledi. Manifest üç etkin görüntüyü listeledi; üçü de Base64 inceleme yolu ile alınıp gerçekten açıldı.
- İlk üçlü içindeki iki eski PNG (31.799 ve 33.405 bayt) ve daha sonra yüklenen ekran görüntüsü (467.105 bayt) görüntü olarak açıldı. Yeni ekran görüntüsünün TradingView Binance BTCUSDT günlük grafiği olduğu, fiyat/günlük değişim/RSI etiketleri ve grafik üzerindeki işaretlemeler okunabildiği doğrulandı; diğer iki görüntünün akış şemaları da okunabildi.
- Yeni bir görüntü yüklendiğinde etkin listenin üç görüntüyle sınırlı kaldığı ve en eski görüntünün döngüden çıkarıldığı ayrıca kontrol edildi.
- Otomatik doğrulama çalışması [#40698725467](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/actions/runs/40698725467) başarılı oldu. Yeni görüntü inceleme yolu yalnızca **test** Render hizmetine (`firsat-kontrol-test-relay`) dağıtıldı. Üretim piyasa geçidi `firsat-kontrol-market-relay` üzerinde bu çalışma için değişiklik yapılmadı.

### Render ayarları ve güvenlik

Render test hizmetinin **Ortam Değişkenleri** bölümünde şu değerler bulunmalıdır:
- `CLOUDINARY_CLOUD_NAME` — Cloudinary'deki Bulut Adı
- `CLOUDINARY_API_KEY` — Cloudinary API anahtarı
- `CLOUDINARY_API_SECRET` — Cloudinary API gizli anahtarı

API Secret yalnızca Render'da saklanmalıdır; masaüstü programına, GitHub'a, kayıtlara veya sohbet mesajlarına eklenmemelidir. Görüntüler bağlantıyı bilen kişilerce açılabilir; parola, API anahtarı, hesap bilgisi veya diğer gizli bilgiler içeren ekran görüntüleri yüklenmemelidir.
