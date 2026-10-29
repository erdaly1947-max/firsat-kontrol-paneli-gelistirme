# Fırsat-Kontrol Paneli — güncel geliştirme ve teslim kaydı

Bu README, projenin güncel teknik özeti, gerçek çalışma durumu, kabul edilmiş işlev gereksinimleri ve bağlayıcı çalışma kurallarının tek kaydıdır. Eski günlükler ve birbiriyle çelişen talimatlar yerine aşağıdaki güncel durum ve kurallar geçerlidir. Tarihsel kayıtlar yalnızca hâlâ işe yarayan bir sürüm kimliği veya doğrulama kanıtı sağlıyorsa tutulur.

## Güncel doğrulanmış durum — 28 Ekim 2026

### Canlı Render hizmeti

- Hizmet: firsat-kontrol-market-relay
- Canlı adres: https://firsat-kontrol-market-relay.onrender.com
- Render yönetimi: https://dashboard.render.com/web/srv-dbf3n80n74is73beeeog
- Kaynak depo: https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme
- Kaynak dalı: main; otomatik dağıtım açık.
- Çalışma ortamı: Node.js. Derleme komutu: npm install --prefix render_relay --omit=dev --no-package-lock. Başlatma komutu: npm start --prefix render_relay.
- 28 Ekim 2026 saat 20:21 TRT civarında commit 008b678 başarıyla dağıtıldı; Render günlükleri sunucunun 10000 portunda hazır olduğunu ve hizmetin canlıya geçtiğini gösterdi.
- CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY ve CLOUDINARY_API_SECRET değerleri Render ortam değişkenlerine girildi; gizli değerler bu README'ye, masaüstü paketine veya sohbete yazılmaz.
- Dağıtım sonrası canlı /images/manifest uç noktasından JSON biçiminde ok: true yanıtı ve görüntü kayıtları alındı. Bu, canlı hizmetin Cloudinary'den mevcut görüntü listesini okuyabildiğini doğrular; masaüstü programından canlı hizmete tam yükleme akışının uçtan uca çalıştığını tek başına kanıtlamaz.
- Masaüstü görüntü aktarımının canlı adrese geçirilmesi commit `5ae27ccf19b361c2333d6ccf10a5834dfcc46807` ile yapıldı. Bu commitin GitHub Actions doğrulaması [#40741310609](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/actions/runs/40741310609) başarıyla tamamlandı; Render canlı hizmeti yeni kaynaktan çalışıyor. Canlı manifest tekrar `ok: true` döndürdü.

### Görüntü aktarımını canlıya geçirme — mevcut durum

- Masaüstündeki analysis_report.py artık görüntü yükleme, manifest ve görüntü indirme işlemleri için https://firsat-kontrol-market-relay.onrender.com adresini kullanacak şekilde değiştirildi.
- tests/test_image_upload.py canlı geçidi bekleyecek şekilde güncellendi; .github/workflows/validate-and-package.yml içindeki canlı görüntü sağlık/manifest kontrolü de aynı üretim adresini kullanır.
- Kod değişikliğinin CI doğrulaması ve canlı manifest kontrolü başarılıdır. Bununla birlikte, kullanıcının Windows bilgisayarındaki program sürümü güncellenip ilk gerçek ekran görüntüsü yüklemesi canlı servise yapıldığında tam uçtan uca doğrulama da yapılmalıdır.
- firsat-kontrol-test-relay test amacıyla durur; masaüstü programının normal görüntü aktarım adresi değildir.

Canlı manifestten görüntü listesini okuyabilmek, görüntü stage/commit, listeleme ve indirme akışının masaüstü programından uçtan uca çalıştığını tek başına kanıtlamaz. Bu doğrulama yapılmadan görüntü aktarımı tamamlandı sayılmaz.

### Görsel gönderme ve doğrudan inceleme — başarıyla doğrulanmış yöntem

28 Ekim 2026'da kullanıcı tarafından panel aracılığıyla buluta gönderilen birden fazla ekran görüntüsü manifestten bulundu, görüntü baytları indirildi ve görsel içerikleri gerçekten açılıp okundu. Bu, yalnızca dosya adlarını görmek değil, pikselleri ChatGPT'nin görsel algılamasına aktarıp ekrandaki içeriği incelemek şeklinde çalıştı.

Görüntü yolu:
1. Güncel görüntü manifesti, önbellek kırıcı benzersiz sorgu parametresi eklenerek alınır.
2. Manifestteki en yeni görüntü kimliği ile görüntü baytları alınır.
3. Görüntü gerçek bir PNG/JPEG görüntüsü olarak açılır ve incelenir.

Kullanıcı “fotoğraf gönderdim”, “görsel gönderdim” veya “ekran görüntüsü gönderdim” dediğinde ilk yapılacak işlem doğrudan bulut manifestini kontrol edip en yeni görüntüyü açmaktır. Önce web araması yapılmaz, başka ekranlarda dolaşılmaz ve kullanıcıdan görüntüyü yeniden sohbete yüklemesi istenmez. Bulut erişimi başarısız olursa bu açıkça bildirilir; görüntü görülmüş gibi davranılmaz.

Masaüstü kodundaki ilgili işlevler analysis_report.py içindedir: görüntü partisi yükleme, geçici yükleme, commit, manifesti alma ve görüntüyü çekme. Sunucu tarafındaki görüntü uçları render_relay/server.js içindedir. Cloudinary anahtarları yalnızca Render ortamında tutulur. Aktif manifest en fazla üç görüntü gösterir; yükleme PNG/JPEG için tasarlanmıştır ve tek görüntünün boyut sınırı 15 MiB'dir.

## Programın amacı ve mevcut kapsamı

Program, hızlı yükseliş potansiyeli taşıyan coinleri erken bulmaya yardımcı olan bir teknik analiz ve karar destek aracıdır. Otomatik alım-satım yapmaz, borsa hesabına bağlanmaz ve emir göndermez. Güçlü fırsat ya da A/B/C sınıflandırması kârlılık garantisi değildir.

Mevcut kaynakta şu işlev aileleri bulunur:
- Binance Spot halka açık piyasa verisi ve WebSocket mum akışı; BtcTurk yerel USDT Spot parite listesi üzerinden ortak tarama evreni. BtcTurk fiyatı bilgi amaçlıdır; teknik mum analizi Binance verisinden yapılır.
- 5m, 15m, 30m, 1h, 4h, 1d, 1w ve 1M olmak üzere sekiz zaman dilimi; veri tazeliği ve geçmiş mum hazırlığının ayrı takibi.
- EMA, MACD, RSI, ADX, DMI, ATR ve hacim göstergeleri; kapanmış mumlardan pivot, destek/direnç, kanal ve Fibonacci seviyeleri.
- BTC piyasa bağlamı ve risk durumu; BTC'ye göre göreceli güç ve korelasyon değerlendirmesi.
- Aday puanı ve sıralaması, A/B/C aşama değerlendirmesi, veri/likidite/teyit kapıları, koşullu giriş bölgesi, stop, teknik hedefler ve geçersizleşme koşulları.
- Alarm ve sinyal geçmişi, tek motorlu Windows paneli, günlük/analiz/sorun giderme raporları ve sorun giderme ZIP'i.
- Bulut raporları için Cloudflare Worker ve piyasa verisi için ayrı Render geçidi.

Kodda işlevin bulunması, o işlevin tarihsel piyasa koşullarında kârlı çalıştığının kanıtı değildir. Gerçek piyasa verileri üzerinde sistematik backtest, kaçırılmış yükseliş/yanlış pozitif ölçümü ve maliyet sonrası net risk/getiri henüz bu README'de doğrulanmış tamamlanmış özellikler olarak gösterilmez.

## Önemli kaynak dosyaları

- binance_erken_firsat_radari.py — ana analiz motoru ve canlı tarama.
- radar_core.py — teknik göstergeler, aday değerlendirmesi, BTC bağlamı, fiyat yapısı ve koşullu risk planı.
- ortak_piyasa.py ve tek_motor_evreni.py — ortak USDT evreni ve piyasa verisi yardımcıları.
- binance_mum_arsivi.py — geçmiş mum arşivi ve hazırlık.
- sinyal_kaydi.py — sinyal ve geçmiş kayıtları.
- tek_motor_paneli.pyw — Windows Tkinter paneli.
- analysis_report.py — rapor oluşturma/gönderme ve ekran görüntüsü yükleme/okuma istemcisi.
- veri_yasam_dongusu.py — eski kayıtların yaşam döngüsü ve arşiv bakımı.
- render_relay/server.js — Render piyasa/görsel/rapor geçidi sunucusu.
- render_relay/rest_cache.js — sınırlı boyut ve kayıt sayısı kullanan REST önbelleği.
- cloudflare/report-worker/src/index.js — rapor Worker'ı.
- tests/ — Python ve sunucu işlevlerinin otomatik testleri.
- .github/workflows/validate-and-package.yml — kaynak doğrulama, test ve açıkça istenen son paketleme akışı.

## Bağlantılar ve entegrasyon kullanım haritası

Bu bölüm, bir hizmet/eklenti bağlantısı yeniden kurulacağı veya bir işlev taşınacağı zaman başvuru kaydıdır. Programın kullandığı bağlantılar ile ChatGPT'nin inceleme sırasında kullandığı bağlantılar ayrıdır. URL veya gizli anahtarı değiştirmeden önce ilgili kod ve bu harita kontrol edilir.

### GitHub — kaynak kod ve testler

- Ana depo: https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme
- Güncel dal: main. Kabul edilmiş sürüm zinciri, main tamamlanıp sabitlendikten sonra yeni sürüm dallarına bir önceki sürümün eksiksiz kopyalanması esasına dayanır.
- .github/workflows/validate-and-package.yml Python derlemesini/birim testlerini, Worker testlerini, Render hizmet testlerini ve canlı piyasa/görüntü manifesti kontrollerini çalıştırır.
- Render canlı hizmeti aynı depodaki main dalına bağlıdır ve otomatik dağıtım açıktır.
- Gizli değerler koda, README'ye, commit mesajlarına veya loglara yazılmaz.
- Paketleme tamamlandığında kullanıcıya Actions kapsayıcı arşivi değil yalnızca doğrulanmış program ZIP'i teslim edilir.

### Render — canlı piyasa ve görüntü geçidi

**Canlı hizmet**
- Ad: firsat-kontrol-market-relay
- URL: https://firsat-kontrol-market-relay.onrender.com
- Yönetim: https://dashboard.render.com/web/srv-dbf3n80n74is73beeeog
- Kaynak depo/branch: ana GitHub deposu / main; otomatik dağıtım açık.
- Build: npm install --prefix render_relay --omit=dev --no-package-lock
- Start: npm start --prefix render_relay

**Test hizmeti**
- Ad: firsat-kontrol-test-relay
- URL: https://firsat-kontrol-test-relay.onrender.com
- Yönetim: https://dashboard.render.com/web/srv-dbgr3mdg1s2s73c48iu0
- Ayrı test hizmetidir; otomatik dağıtımı kapalıdır ve masaüstü programının normal hedefi olmamalıdır.

**Kullanılan canlı uçlar**
- GET /healthz: sunucu sağlığı ve sürüm bilgisi.
- /binance/api/v3/... ve /btcturk/api/v2/...: izin listesinde bulunan halka açık piyasa REST verisi.
- /ws/binance/stream?streams=...: Binance genel WebSocket mum akışı.
- POST /api/report, /api/report/daily, /api/report/troubleshooting, /api/report/troubleshooting-zip: raporları Cloudflare rapor Worker'ına iletir.
- POST /api/images/stage, /api/images/commit, /api/images/abort: görüntü yükleme grubu.
- GET /images/manifest: etkin Cloudinary görüntü listesi.
- GET /images/{UUID}?format=base64: seçilen görüntü baytlarını JSON içinde Base64 biçiminde döndürür.

Sunucu kodu render_relay/server.js, sınırlı REST önbelleği render_relay/rest_cache.js, sunucu testleri render_relay/test/, canlı piyasa kontrolü render_relay/smoke-check.mjs içindedir. Canlı piyasa kontrolü sağlık, Binance mum verisi, BtcTurk USDT ticker'ı ve gerçek WebSocket mesajını ayrı ayrı doğrular; yalnızca hizmetin live görünmesi yeterli değildir.

### Cloudinary — görüntü dosyası saklama

- Görüntü dosyalarını Cloudinary saklar; istemci Cloudinary'ye doğrudan bağlanmaz, Render geçidini kullanır.
- Canlı Render Environment bölümünde CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY ve CLOUDINARY_API_SECRET değişkenleri bulunmalıdır. Gerçek değerler README'ye, sohbete veya masaüstü ZIP'ine yazılmaz.
- Render tarafındaki stage/commit/abort ve en fazla üç etkin görüntü mantığı render_relay/server.js ile render_relay/test/cloudinary-images.test.js içindedir.
- Görüntü listesi çalışmıyorsa önce canlı Render /healthz, sonra Cloudinary değişken adları/değerlerinin doğruluğu kontrol edilir. API Secret paylaşılmaz.

### Cloudflare — rapor saklama ve okuma

- Worker: https://firsat-kontrol-analysis-report.erdaly1947.workers.dev
- Kaynak: cloudflare/report-worker/src/index.js
- Kılavuz: cloudflare/report-worker/README.md
- Sağlık: GET /health
- Analiz: POST /api/report, oku GET /latest
- Günlük: POST /api/report/daily, oku GET /daily
- Sorun giderme JSON: POST /api/report/troubleshooting, oku GET /troubleshooting
- Devir ZIP: POST /api/report/troubleshooting-zip, indir GET /troubleshooting.zip

Masaüstü analiz/durum raporlarını yerelde reports klasöründe üretir. analysis_report.py raporları canlı Render geçidine yollar; Render bunları Cloudflare Worker'a aktarır. Okuma URL'leri WORKER_BASE_URL / READ_URL üzerinden doğrudan Worker'a gider. Yükleme Bearer token ile doğrulanır. Render'daki REPORT_RELAY_TOKEN ve CLOUDFLARE_REPORT_TOKEN değerleri, sunucu/Worker tarafındaki ilgili gizli ayarlarla uyumlu tutulur. Anahtarlar koda ve README'ye yazılmaz; raporlara gizli bilgi konmaz.

Depodaki cloudflare_worker klasörü tarihsel piyasa-verisi denemesidir; aktif piyasa REST/WebSocket geçidi Render'dır. Rapor saklama Worker'ı ile eski piyasa veri denemesi aynı işlev değildir.

### Exa — ChatGPT'nin buluttaki ekran görüntüsünü açması

- Exa, Windows programının çalışma zamanı bağımlılığı değildir. ChatGPT tarafında ekran görüntüsünü Render üzerinden bulup, görüntünün gerçek baytlarını sohbete getirerek görsel incelemeyi sağlayan bağlı web-fetch bağlantısıdır.
- Kullanıcı “fotoğraf gönderdim”, “görsel gönderdim” veya “ekran görüntüsü gönderdim” dediğinde ilk adım canlı Render hizmetinden güncel manifesti almaktır: GET /images/manifest adresine benzersiz bir check sorgusu eklenir; bu önbellek kaynaklı eski yanıt riskini azaltır.
- Manifestten en yeni görüntünün UUID'si alınır. Ardından GET /images/{UUID}?format=base64 adresine yine benzersiz check sorgusu eklenir. Görüntü 512 KiB'ten küçükse gerçek PNG/JPEG baytları Base64 olarak alınır. Yanıt 413 ile görüntü sınırını bildirirse GET /images/{UUID}?format=base64&preview=1 kullanılır; bu yol Cloudinary'den en fazla 1280 piksel genişliğinde bir JPEG önizlemesi alır. Önizleme orijinal dosyayı veya saklanan görüntüyü değiştirmez. Gelen JSON içindeki content_type ve Base64 data görüntü algılamasına verilir. Sadece dosya adını görmek görüntüyü okumak sayılmaz.
- Görüntü açılmazsa sırayla manifest erişimi, UUID, indirme yanıtı, HTTP/önbellek hatası, Render durumu ve Cloudinary yapılandırması kontrol edilir. Kullanıcıdan görüntüyü yeniden sohbete yüklemesi istenmez; açılmadan görüldüğü iddia edilmez.
- Exa görüntünün saklandığı yer değildir; depolama Cloudinary, dosya API'si Render, görüntüyü ChatGPT'ye getiren erişim Exa'dır.

### Arıza durumunda ilk kontrol noktası

| Belirti | İlk kontrol |
|---|---|
| Piyasa verisi gelmiyor | market_data_relay.json, Render /healthz, render_relay/smoke-check.mjs ve Render logları |
| Görüntü yüklenmiyor | analysis_report.py içindeki IMAGE_RELAY_BASE_URL, canlı Render /healthz, CLOUDINARY_ değişkenleri, tests/test_image_upload.py |
| Yüklenen görüntü ChatGPT'de görünmüyor | Exa ile güncel /images/manifest, UUID ve /images/{UUID}?format=base64 yanıtı |
| Rapor yüklenmiyor | analysis_report.py içindeki RELAY_BASE_URL, Windows Kimlik Bilgileri Yöneticisi'ndeki Firsat-Kontrol-Paneli/ReportUploadToken, Render REPORT_RELAY_TOKEN/CLOUDFLARE_REPORT_TOKEN ve Worker durumu |
| Rapor eski | /latest, /daily ve /troubleshooting içindeki zaman damgalarını ayrı karşılaştır; farklı raporlar farklı çalışma anları olabilir |
| Kod canlıya ulaşmamış | GitHub Actions sonucu, Render repo/branch/auto-deploy ayarı ve canlı deploy commit SHA'sı |

## Kabul edilmiş teknik analiz ve karar gereksinimleri

Hesaplamalar gereksiz yere kopyalanmaz; yeni geliştirme mevcut modüllerin doğrulanmış çıktılarını kullanır. Program değerlendirmede şu bağlamları birlikte ele almalıdır:

- BTC ana yönü, piyasa rejimi, seviye/kanal durumu ve genel risk koşulları.
- Coinin fiyat yapısı, teknik aşaması, kırılım ve geri test durumu.
- BTC'ye göre performans ve BTC ile korelasyon.
- Yakın destek/direnç, kanal sınırları, Fibonacci ve fiyat yapısına dayalı teknik hedef.
- Koşullu giriş, stop riski, hedefe kalan getiri, eksik teyit ve geçersizleşme koşulu.
- Veri güncelliği, eksik geçmiş ve likidite.

Güçlü fırsat kapısının mevcut başlangıç koşulları korunur: en az 80/100 puan, uygun B/C aşaması, güncel ve yeterli veri, başarılı likidite kontrolleri, geçerli teknik plan, BTC risk kapısı ve ilk teknik hedefte en az 1,5 brüt teknik risk/getiri. Eşikler sessizce değiştirilmez. Komisyon ve kayma varsayımları uygulanıp test edilene kadar net maliyet sonrası getiri hesaplanmış gibi sunulmaz. Teknik hedef, matematiksel 1R/2R/3R projeksiyonundan ayrıdır ve emir değildir.

### Kabul edilmiş panel tasarımı

- Üst bölüm: motor/veri durumu, BTC ana yönü, genel piyasa riski, önemli destek/direnç, kanal ve veri tazeliği.
- Aday listesi: coin, Binance/BtcTurk USDT fiyatları, puan, zaman dilimi, A/B/C, veri durumu, BTC'ye göre durum ve son karar.
- Seçilen coin: hızlı karar özeti ile teknik ayrıntılar; BTC ilişkisi, fiyat yapısı, destek/direnç, önemli engeller ve eksik teyitler.
- Giriş/hedef/risk alanı: koşullu giriş, kırılım, stop ve yüzde riski, teknik hedef, matematiksel risk katları, geçersizleşme koşulu.
- Siyah panel arka planı, beyaz ayırıcılar ve okunabilir durum metinleri. Renk tek başına karar gerekçesi olmaz.
- Pencere ölçüsü, metin ölçeklendirme ve gerçek Windows ekranında taşma kontrolü, otomatik testlerden ayrı görsel doğrulama gerektirir.

Bu bölüm kabul edilmiş hedef davranışı tanımlar; herhangi bir madde, kaynak ve testle doğrulanmadıkça uygulanmış sayılmaz.

## Raporlama ve bulut uçları

Cloudflare rapor Worker adresi:
https://firsat-kontrol-analysis-report.erdaly1947.workers.dev

Kullanılan okuma uçları:
- /latest — en son analiz raporu
- /daily — günlük durum raporu
- /troubleshooting — sorun giderme JSON raporu
- /troubleshooting.zip — sorun giderme ZIP'i

Masaüstü istemcisi analiz raporunu reports/analiz_raporu.json.gz dosyasına, günlük ve tanı raporlarını sabit rapor dosyalarına yazar; devir ZIP'i sabit adlı dosyaya oluşturulur. Yükleme kimlik bilgileri Windows Kimlik Bilgileri Yöneticisi/Render ortamı gibi uygun gizli saklama noktalarında tutulur. Gizli değerler README'ye, kaynak koduna veya sohbet mesajlarına yazılmaz. Rapor uçlarında başarılı okuma yapılması, tüm raporların aynı çalışma anını temsil ettiği anlamına gelmez; rapor zaman damgaları karşılaştırılmalıdır.

## Aşamalı geliştirme ve sürüm kuralları — güncel ve bağlayıcı

Bu bölüm, eski ve çelişen dal/test/paket kurallarının yerine geçer.

### 1. Mevcut main'i tamamla, sonra dondur

- Önce mevcut main dalındaki program son hâline getirilir. Motor fonksiyonları, panel, raporlama, bulut görsel aktarımı, sunucu kaynakları, yapılandırmalar, bağımlılıklar ve gerekli testler eksiksiz kontrol edilir.
- main tamamlanıp gerekli doğrulamaları geçtikten sonra sabit tutulur; sonraki geliştirme için main'e yeni değişiklik gönderilmez.
- Tamamlanmış main'in tüm içeriği yeni Sürüm 1 dalına kopyalanır. Sürüm 1 tamamlanınca bütün güncel içeriği Sürüm 2 dalına kopyalanır; sonraki sürümlerde de aynı zincir sürer. Hiçbir sürüm sıfırdan başlamaz ve önceki sürümün kodu/işlevleri kaybolmaz.
- Yeni bir dala geçmeden önce kullanıcıya haber verilir; izin beklenmez. Test çalıştırmak, kodu düzeltmek veya doğrulama yapmak için izin istenmez.

### 2. Aşamalar ve bildirim

- İş aşama aşama yürütülür. Her aşamada eksikler belirlenir, ilgili değişiklikler yapılır ve testler çalıştırılır.
- Her aşama tamamlandığında kullanıcıya kısa bir durum bildirimi yapılır: ne tamamlandı, ne doğrulandı, sırada ne var ve hangi açık iş kaldı.
- Bildirim, kullanıcıdan izin istemek anlamına gelmez. Kapsamda açık olmayan veya birbiriyle çelişen bir gereksinim çıkarsa, yalnızca bu belirsizliği netleştirmek için soru sorulur; bilinen kararlar yeniden sorulmaz.

### 3. Değişikliğe uygun test kapsamı

- Her küçük değişiklikten sonra bütün program tekrar baştan sona test edilmez. Önce değiştirilen işlevin doğrudan testleri ve etkilenen davranışlara ait ilgili regresyon testleri çalıştırılır.
- Ortak modül, veri akışı, yapılandırma, kullanıcı arayüzü veya hizmetler arası bağlantı etkileniyorsa buna uygun entegrasyon testleri de çalıştırılır.
- Her aşama sonunda o aşamanın işlev alanları için daha geniş kontroller yapılır. Başarısız test varsa neden bulunur, kod düzeltilir ve ilgili testler yeniden çalıştırılır.
- Son ZIP'ten önce programın tüm kritik bileşenlerini ve hizmetler arası akışları kapsayan zorunlu tam doğrulama yapılır. Başarısız zorunlu test varsa paket hazır diye sunulmaz.
- Otomatik test başarısı, gerçek Windows arayüzünün görsel kontrolü veya tarihsel kârlılık kanıtı değildir; bunlar gerektiğinde ayrı ve dürüst biçimde raporlanır.

### 4. Son paket ve teslim

- ZIP yalnızca mevcut sürüm kapsamındaki bütün gerçek program geliştirmeleri tamamlandıktan ve zorunlu tam doğrulama başarılı olduktan sonra üretilir.
- **ZIP'e girecek her özellik gerçek program koduna uygulanmış, ilgili iş akışına bağlanmış ve masaüstü arayüzünden kullanılabilir olmalıdır.** Bir özelliğin yalnızca test dosyasında, sahte/mock uygulamada, test verisinde, dokümantasyonda veya kullanılmayan bir modülde bulunması, o özelliğin programa işlendiği anlamına gelmez. Testler gerçek işlevi doğrular; gerçek işlevin yerine geçmez.
- Paket öncesinde sürüm gereksinimleri tek tek gerçek kaynak kodu, arayüz kontrolleri, veri akışı ve çalışma bağlantılarıyla karşılaştırılır. Kodda veya pakette eksik olan bir özellik tamamlanmadan sürüm hazır ilan edilmez.
- Paket açılabilirliği, gerekli masaüstü dosyaları, bağımlılık/yapılandırma dosyaları ve arşiv bütünlüğü doğrulanır. ZIP'teki kaynak sürümünün test edilen kaynak sürümüyle aynı olduğu doğrulanır.
- Masaüstü Windows programını çalıştırmak için gereken bütün dosyalar ZIP içinde bulunmalıdır. Render/Cloudflare sunucu hizmetleri kendi depo ve dağıtım düzenleriyle ayrıca çalışır; masaüstü ZIP'ine sunucunun çalıştırma ortamının konması zorunlu değildir. Test dosyaları ve çalıştırma için gerekmeyen sunucu kaynakları, programın işlev dosyalarıymış gibi masaüstü paketine alınmaz.
- Kullanıcıya teslim edilirken yalnızca program ZIP'inin doğrudan sohbet içi indirme bağlantısı verilir. Kullanıcıdan GitHub Actions arşivini veya başka bir yan dosyayı bulup indirmesi istenmez. Paket oluşturulamadıysa bu açıkça bildirilir; eski ZIP güncelmiş gibi paylaşılmaz.

### 5. Kullanıcının bilgisayarındaki son doğrulama ve sürüm onayı

- **Kullanıcıya ara test için eksik/yarım ZIP gönderilmez.** Kullanıcının test ettiği program, o sürüm kapsamına ait özellikleri gerçek koda işlenmiş, arayüze ve ilgili akışlara entegre edilmiş, asistanın kendi tarafında kontrolleri tamamlanmış bütün bir sürüm adayı olmalıdır. “Deneme ZIP'i” ara derleme değil, tam sürüm adayının kullanıcı kabul paketi anlamına gelir.
- Asistan, kullanıcıya ZIP göndermeden önce kendi tarafındaki aşama testlerini, otomatik testleri, gerekli entegrasyon ve regresyon kontrollerini, arayüz/kaynak kapsamı kontrollerini ve paket doğrulamasını tamamlar. Başarısız zorunlu kontrol varsa önce nedenini giderir; başarısız kontrolle ZIP teslim etmez.
- Kullanıcıya her küçük değişiklikte yeniden test yaptırılmaz. Kodlama, düzeltme, entegrasyon ve ara doğrulamalar asistan tarafında yürütülür; kullanıcı yalnızca bütün özellikleri içeren tamamlanmış sürüm adayının son yerel Windows testini yapar.
- Kullanıcı ZIP'i kendi Windows bilgisayarında çalıştırıp programın bütün işlevlerini kontrol eder; gördüğü sonuçları ve eksikleri rapor olarak gönderir.
- Kullanıcının yerel test raporu incelenir. Bildirilen eksikler düzeltilir, doğrudan ilgili testler ve etkilenen regresyon/entegrasyon kontrolleri tekrarlanır. Yeni bir ZIP ancak ilgili düzeltmeler bütünleştirilip sürüm adayı yeniden tamamlandığında hazırlanır; her küçük düzeltme ayrı bir kullanıcı ara testine çevrilmez.
- Otomatik test veya bulut sağlık kontrolü, gerçek masaüstü programında çalıştırılmamış bir işlevin uçtan uca doğrulandığı anlamına gelmez. Asistan doğrulayamadığı noktaları açıkça ayırır; ancak bu eksiklikleri, özellik hiç koda işlenmemişken kullanıcıya yaptırılacak bir ara testle ikame etmez.
- **Bir sonraki sürüme ancak kullanıcı kendi bilgisayarındaki son kontrol sonuçlarını raporladıktan ve bu sürümü onayladıktan sonra geçilir.** Kullanıcı onayı gelmeden bir sonraki sürümün geliştirme çalışmasına başlanmaz. Bu, dal açmak için genel izin verilmiş olmasını değil, sürümün kullanıcı tarafından kabul edilmiş olmasını bekleyen ayrı bir sürüm geçiş şartıdır.
- Her sürümün kabulü, önceki sürümdeki bütün işlevlerin korunduğu ve yeni değişikliklerin kullanıcının bilgisayarında kontrol edildiği anlamına gelir. Kullanıcının raporundaki başarısızlıklar çözülmeden sürüm kabul edilmiş sayılmaz.

### 5. Kayıtların doğruluğu ve gereksiz tekrarlar

- Bu README güncel kaynak durumu, kabul edilmiş tasarım ve bu iş akışını taşıyan ana kayıttır. Kod, çalışma raporu ve test kanıtı olmadan bir özellik tamamlandı sayılmaz.
- Eski çelişkili çalışma talimatları geçersizdir. Aynı bilgiyi tekrarlayan günlükler, artık uygulanmayan adımlar ve çözülmüş sorun anlatıları güncel bölümlerde tutulmaz.
- Hâlâ işe yarayan eski sürüm/Release kimliği veya doğrulama kanıtı, yalnızca kısa bir tarihsel referans olarak korunur. Tarihsel testler güncel sürüm testleri gibi gösterilmez.
- Doğrulanmış başarılar ve halen açık olan kritik farklar korunur; belirsizlik kesin sonuç gibi yazılmaz.

## Sınırlı tarihsel referanslar

- Korunan eski Sürüm 00 paketi: Firsat-Kontrol-Paneli-Surum-00.zip. SHA-256: d5909444e7c48f8d79f7cc4f5115da1e606db59bd335e743c554c03d6caddbdb. Release: https://github.com/erdaly1947-max/matrix/releases/tag/surum-00
- 28 Ekim 2026'da ekran görüntüsü bulut manifestini alma ve gerçek görüntüyü açıp inceleme yolu başarıyla kullanıldı. Bu, kullanıcıyı yeniden dosya yükletmeden yeni ekran görüntüsünü buluttan kontrol etme kuralının teknik dayanağıdır.
- 28 Ekim 2026'da Render canlı hizmetinin yeni geliştirme deposuna taşındığı ve commit 008b678'in dağıtımının başarılı olduğu doğrulandı. Canlı manifestin okunması başarılıdır; masaüstü görüntü yükleme hedefi hâlâ test hizmetini gösterdiğinden uçtan uca geçiş işi açıktır.

## Windows'ta başlatma

ZIP'i Windows'ta ayrı bir klasöre çıkarıp BASLAT.bat dosyasını çalıştırın. Program Python/Tkinter masaüstü uygulamasıdır; EXE kurucusu değildir. Kullanılan bağımlılıklar requirements.txt dosyasında tutulur. Program halka açık piyasa verilerini okuyan bir analiz/karar destek aracıdır; borsa hesabına bağlanmaz, emir göndermez ve otomatik alım-satım yapmaz.


---

## Fırsat-Kontrol Paneli — tasarım kararları defteri ve sürüm yol haritası

**Kayıt tarihi:** 29 Ekim 2026  
**Tasarım durumu:** 1–100 kayıtlı; 101–118 tamamlanmış yeniden oluşturma kaydı; 119–122 kullanıcının sağladığı metinler; 123–141 kayıtlıdır. Özgün metni bulunamayan maddelerin kaynağı açıkça işaretlenmiştir.  
**Sonraki tasarım kararı:** 142. karar.  
**Kodlama durumu:** Başlanmayacak; bütün tasarım kararları tamamlanana ve gerekli açık onaylar verilene kadar beklemede.

### Bağlayıcı yol haritası

1. **Tasarım kararlarını bitir:** 142. karardan itibaren devam et. Küçük ve ayrıntılı tasarım seçimlerini asistan belirlesin; programın önemli çalışma mantığını veya kapsamını etkileyen kararlar kullanıcıyla birlikte netleştirilsin. Kesinleşmiş kararlar yeniden sorulmasın. Kararların tamamlanması tek başına kodlama izni değildir.
2. **Her 100 kararda kayıt al:** 1–100 aralığı bu kayıtla sabitlenmiştir. Sonraki 100 karar tamamlandığında 101–200 aralığı aynı README içindeki tasarım kararları defterine eklenecek. Böylece kararlar 100'er maddelik aralıklarla korunacak ve yeni sohbetlere aktarılabilecek.
3. **Sürüm 1'i mevcut program üzerinden hazırla:** Tasarım kararlarının tamamı bittikten sonra, mevcut GitHub main dalındaki programı incele. Mevcut işlevleri, dosyaları, yapılandırmaları ve testleri doğrula; eksikleri gider ve gerekli testleri çalıştır. Sürüm 1 hazır olduğu kanıtlanmadan kabul edilmiş sayılmayacak.
4. **Sürüm 1'i kullanıcı testinden geçir:** Tam ve doğrulanmış sürüm adayı kullanıcının Windows bilgisayarında kontrol edilecek. Kullanıcının bulguları düzeltilip ilgili testler tekrarlanacak. Kullanıcının son onayı gelmeden Sürüm 1 kabul edilmeyecek.
5. **Sürüm 1'i sabitle, Sürüm 2'yi ondan üret:** Sürüm 1 kabul edilip sabitlendikten sonra değiştirilmeden korunacak. Yeni tasarım kararları, Sürüm 1'in eksiksiz kopyası temel alınarak Sürüm 2'ye uygulanacak. Mevcut ve çalışan işlevler gereksiz yere yeniden yazılmayacak; yeni işlevler gerçek programa ve arayüze entegre edilecek.
6. **Eksik sürüm teslim etme:** Kullanıcıya ara çalışma veya eksik ZIP verilmeyecek. Sürümün tüm işlevleri uygulandıktan, ilgili testler ve son tam doğrulama geçtikten sonra tam paket hazırlanacak. Kullanıcının son test ve sürüm kabulü tamamlanmadan bir sonraki sürüme geçilmeyecek.
7. **Hesap bağlantısı ve otomatik emir yok:** Program borsa hesabına bağlanmayacak, kullanıcının gerçek işlemlerini izlemeyecek ve otomatik emir göndermeyecek. Başarı raporları radarın ve önerilen teknik işlem planlarının fiyat hareketine göre değerlendirilmesini kapsayacak; kullanıcının gerçek alım-satım performansını kapsamayacak.
8. **Karar kaydını anında koru:** Kullanıcı bir kararı kesinleştirince numarası, başlığı, tam karar metni ve kayıt statüsü README'ye eklenir veya ilgili madde güncellenir. Aynı oturumda bu kayıt yeniden okunup doğrulanmadan sonraki tasarım kararına geçilmez. Özgün metin bulunmuyorsa yeniden oluşturulan içerik açıkça işaretlenir; varsayım sessizce özgün karar gibi kaydedilmez.

### Kararların kaydı: 1–31

1–31. kararlar önceki sohbetlerde kesinleştirildi. Bu aktarımın kaynak metninde bu 31 kararın tamamının tek tek numaralanmış özgün metni bulunmadığından, eksik maddeler uydurularak yeniden yazılmadı. Bu aralık kesinleşmiş kabul edilir; yeniden sorulmayacak veya kendiliğinden değiştirilmeyecek.

Bu aktarımda doğrulanabilen önceki kurallar: Aktif Takip için 4–5 parite; kullanıcı onaylı takip listesi; yeni işlem planının kullanıcı onayı olmadan etkinleştirilmemesi ve eski planın korunması; bildirim ayrıntılarının sağdan açılan panelde gösterilmesi; Binance'ten BtcTurk PRO'ya coin aktarılırken paritenin otomatik seçilmesi; grafiklerin önceki Binance grafiği mantığına uygun çalışması; trend çizgisi ve paralel kanal çizimi ile çizimlerin kalıcı saklanması. Ayrıca 26. kararın kayıtta bulunan metni: BtcTurk PRO doğrudan açıldığında en son incelenen paritenin ayrıntı ekranı açılsın; Binance'ten aktarılan coin otomatik seçilsin.

### Kesinleşmiş tasarım kararları: 32–100

#### 32–40. Grafikler ve çizim araçları
- **32.** Çizimler kalıcı saklanır ve ilgili zaman dilimiyle birlikte kaydedilir.
- **33.** Çizimler taşınarak veya uç noktaları değiştirilerek düzenlenmez; silinip yeniden çizilir.
- **34.** Zaman dilimleri ayrı düğmelerle seçilir; daha önce kararlaştırılmış grafik davranışları yeniden tartışılmaz.
- **35.** Çizimler silinirken kısa süreli Geri Al seçeneği bulunur.
- **36.** Trend çizgisi ve paralel kanal aynı çizim araçları menüsünde bulunur.
- **37.** Aktif planın giriş bölgesi, kâr hedefleri, zarar-kes ve geçersizlik seviyeleri grafikte gösterilir; her biri ayrı ayrı gizlenebilir.
- **38.** Her işlem seviyesi için ad ve fiyat gösterilir.
- **39.** Grafikte yalnızca aktif plan gösterilir. Yeni öneri ayrı açılır ve kullanıcı onayı olmadan etkinleştirilmez.
- **40.** RSI (Göreceli Güç Endeksi), MACD (Hareketli Ortalamaların Yakınsaması ve Iraksaması) ve Momentum (Fiyat İvmesi) fiyat grafiğinin altında ayrı bölümlerde gösterilir; açılıp kapatılabilir.

#### 41–50. Fırsat Radarı
- **41.** Satıra tıklamak coin seçer; Parite Analizi ayrı bir İncele düğmesiyle açılır.
- **42.** Coin satırında kısa fırsat gerekçesi, ayrıca ayrıntılı inceleme bulunur.
- **43.** En güçlü fırsat adayı listenin en üstünde olur.
- **44.** Tarama tamamlandığında liste topluca yeniden sıralanır; inceleme sırasında coinler sürekli yer değiştirmez.
- **45.** Güçlü Fırsat, İzlemeye Değer ve Zayıf Aday seviyeleri kullanılır.
- **46.** Coin satırında tespit zamanı gösterilir.
- **47.** Yeniden sıralama sırasında seçilmiş coin korunur.
- **48.** Fırsat özelliğini kaybeden coin listede kalır ve durum kaybı belirtilir.
- **49.** Coin adı veya parite sembolüyle arama yapılır; liste anında filtrelenir.
- **50.** Hazır filtreler fırsat gücünü, fırsat durumunun güncelliğini ve işlem yapılan borsayı kapsar.

#### 51–60. Raporlar, genel bakış ve pencere davranışı
- **51.** Rapor dönemleri: Bugün, Son 7 Gün, Son 30 Gün, Tüm Dönem ve özel tarih aralığı.
- **52.** Excel (tablo dosyası) ve PDF (belge dosyası) dışa aktarma bulunur.
- **53.** Genel Bakış açılışında piyasa durumu, en güçlü fırsat adayı, aktif işlem planları ve son tarama durumu gösterilir.
- **54.** En güçlü fırsat ve piyasa durumu üstte, diğer bilgiler altta bulunur.
- **55.** Genel Bakış otomatik güncellenir; son güncelleme zamanı ve elle yenileme düğmesi bulunur.
- **56.** Güncelleme sıklığı Sistem ve Ayarlar bölümünden değiştirilebilir.
- **57.** Varsayılan koyu tema; isteğe bağlı açık tema bulunur.
- **58.** Son kullanılan pencere boyutu ve konumu hatırlanır.
- **59.** Pencere kapandığında tarama motorları arka planda çalışmaya devam eder ve fırsat uyarıları etkin kalır.
- **60.** Pencere ek onay sorulmadan doğrudan kapanır.

#### 61–70. Bağlantı, bildirim ve arka plan
- **61.** Bağlantı kesilince uyarı gösterilir, otomatik yeniden bağlanma denenir ve veri akışı geri geldiğinde tarama sürer.
- **62.** Aynı koşul devam ederken yalnızca ilk uyarı verilir; durum önemli ölçüde değişirse yeni uyarı verilir.
- **63.** Pencere kapalıyken Windows masaüstü bildirimi gösterilir ve kayıt tutulur.
- **64.** Uyarı kayıtlarının saklama süresi ayarlardan belirlenir.
- **65.** Eski veriler ekranda kalır, ancak güncel olmadıkları yazı ve veri rengiyle vurgulanır. Güncel veri gelene kadar yeni fırsat değerlendirmesi yapılmaz.
- **66.** Windows açılışında otomatik başlatma ayarlardan açılıp kapatılır.
- **67.** Otomatik başlatma programı arka planda başlatır; ana pencere açılmadan tarama motorları çalışır.
- **68.** Arka plandaki programa erişmek için Windows sistem tepsisi simgesi bulunur.
- **69.** Sistem tepsisi simgesine tek tıklama ana pencereyi açar.
- **70.** Simgeye sağ tıklanınca Programı Tamamen Kapat seçeneği bulunur; motorlar da kapatılır.

#### 71–80. Aktif Takip ve fırsat başarı ölçümü
- **71.** Aktif Takip pariteleri güncel fırsat gücüne göre otomatik sıralanır.
- **72.** **Düzeltilmiş karar:** Gerçekleşen alım-satım işlemlerinin performansı hesaplanmaz. Yalnızca fırsat radarının tespit performansı ve önerilen işlem planlarının fiyat hareketlerine göre başarısı değerlendirilir.
- **73.** Değerlendirme süreleri 1 saat, 4 saat ve 24 saattir.
- **74.** Her sürede dönem sonu fiyat değişimi, dönem içindeki en yüksek yükseliş ve en büyük düşüş ölçülür.
- **75.** Radarın fiyat hareketini tespit başarısı ile önerilen işlem planının hedefe ulaşma başarısı ayrı ölçülür; kullanıcıya ait gerçek işlem sonuçları kullanılmaz.
- **76.** Başarı için gereken yükseliş eşiğini kullanıcı ayarlardan belirler.
- **77.** Genel sonuçlar, coin bazında performans ve Binance ile BtcTurk PRO sonuçları ayrı gösterilir.
- **78.** Raporlarda sayısal özetler, tablolar ve grafikler birlikte kullanılır.
- **79.** Sinyal verilsin veya verilmesin, taranan tüm coinlerin sonraki fiyat hareketleri kaydedilir; eşik ve değerlendirme süreleri uygulanır.
- **80.** Yükselişler erken tespit edilen, geç tespit edilen ve tamamen kaçırılan olarak sınıflandırılır.

#### 81–90. Ölçüm yöntemi ve rapor başlangıcı
- **81.** Erken/geç tespit için izleme başlangıcındaki fiyat referans alınır. Belirlenen yükseliş eşiğine doğru hareketin ilk %25'lik bölgesine ulaşılmadan sinyal gelirse erken; bu bölgeden sonra ancak eşik aşılmadan sinyal gelirse geç tespit sayılır. Eşik sinyal gelmeden aşılırsa yükseliş kaçırılmış sayılır.
- **82.** Her coin için izleme başladığında kaydedilen ilk geçerli fiyat başlangıç fiyatıdır.
- **83.** Önceki kaydın 24 saatlik ölçümü devam ediyorsa kayıt korunur. Ölçüm tamamlandıktan sonra yeni sinyal gelirse yeni kayıt ve başlangıç fiyatı oluşturulur.
- **84.** Hedef ölçüm zamanında güvenilir fiyat alınamazsa ölçüm eksik kaydedilir ve başarı hesabına katılmaz.
- **85.** Eksik ölçümlerin sayısı, toplam içindeki oranı, ilgili zaman dilimi ve kayıtlıysa nedeni gösterilir.
- **86.** Başarı oranı ölçüm sayısıyla birlikte gösterilir. Veri azsa sonuç Yetersiz Veri olarak işaretlenir.
- **87.** Asgari ölçüm sınırı Sistem ve Ayarlar bölümünden kullanıcı tarafından belirlenebilir.
- **88.** Varsayılan asgari sınır 30 tamamlanmış ölçümdür; ayarlardan değiştirilebilir.
- **89.** Genel performans, coin ve tarama motoru ayrı değerlendirilir. Her grup asgari sınırın altındaysa Yetersiz Veri işareti konur; sayısal sonuçlar gösterilmeye devam eder.
- **90.** Raporlar ekranı genel performans özetiyle açılır; toplam sonuçlar, başarı oranları, erken tespitler ve kaçırılan yükselişler ilk ekranda gösterilir.

#### 91–100. Ayrıntılı raporlar, işlem kapsamı ve başarısız sinyaller
- **91.** Genel performans özetindeki bir sonuca tıklanınca ilgili ayrıntılı rapor açılır.
- **92.** Ayrıntılı raporlar varsayılan olarak en önemli sonuçlar önce sıralanır; kullanıcı sıralamayı tarihe, yükseliş oranına veya performansa göre değiştirebilir.
- **93.** Coin, borsa, erken/geç/kaçırılan yükseliş sınıfı ve 1 saat/4 saat/24 saat değerlendirme süresi filtreleri birlikte kullanılabilir.
- **94.** Filtreler değiştikçe sonuçlar anında güncellenir; ayrıca Filtreleri Sıfırla düğmesi bulunur.
- **95.** Rapor ayrıntısında hem ölçüm sonuçları hem de fiyat hareketinin zaman içindeki gelişimi gösterilir.
- **96.** **İşlem yetkisi:** Program analiz, işlem planı ve uyarı sunar. Borsa hesabı bağlanmaz; emirleri kullanıcı kendisi verir ve program otomatik emir göndermez.
- **97.** **Düzeltilmiş karar:** Kullanıcının gerçek işlem performansı hesaplamalara dahil edilmez; işlem geçmişi manuel olarak da istenmez.
- **98.** Yükseliş sinyali verilip ilgili yükseliş eşiğine ulaşılmayan durumlar raporlarda başarısız sinyal olarak ayrı sınıflandırılır.
- **99.** Küçük ayrıntı kararı: 1 saat, 4 saat ve 24 saatlik değerlendirme pencereleri ayrı ölçülür. İlgili pencerede yükseliş eşiğine hiç ulaşılmazsa o pencerenin sonucu başarısız sinyal olur; daha uzun bir pencerenin sonucu ayrı hesaplanır.
- **100.** Başarısız sinyal için yalnızca 24 saatlik değerlendirme tamamlandığında hâlâ yükseliş eşiğine ulaşılmamışsa tek bildirim gönderilir.

### Kayıt bütünlüğü ve sonraki adım

- 1–100. karar aralığı tamamlanmış kabul edilir; bu aralıktaki kesinleşmiş kararlar yeniden açılmaz.
- 72, 75 ve 97. maddeler, gerçek işlem performansını kapsam dışı bırakan kullanıcı düzeltmesine göre kaydedilmiştir.
- Bu defter tasarım gereksinimlerinin kaydıdır; burada yazan hiçbir yeni işlev, kod ve testle doğrulanmadan mevcut programda uygulanmış kabul edilmez.
- **Güncel sonraki adım: 142. tasarım kararı.** 101–112 karar metinleri kullanıcı tarafından sağlandı; 113–118 aralığındaki kaynak durumu aşağıdaki güncel devir bölümünde işaretlidir; eski “101. tasarım kararı” yönlendirmesi geçersizdir.


---

## Güncel tasarım kararları ve devir noktası — 29 Ekim 2026

**Güncel durum:** Kullanıcının devir kaydına göre 140. karar tamamlanmıştı. Bu sohbette 141. karar da kesinleştirildi. Sıradaki yeni karar numarası 142'dir.

### 101–122. karar aralığı — kaynak durumu ve karar metinleri

**Kayıt doğruluğu notu:** 101–112. kararların aşağıdaki metinleri kullanıcı tarafından 29 Ekim 2026'da sağlandı ve bu metinler esas alındı. 113–117. kararların özgün ifadeleri erişilebilen kaynaklarda bulunamadığı için bunlar yeniden oluşturulmuş operasyonel kayıtlardır; özgün metin oldukları ileri sürülmez. Kullanıcı 118. kararın kesinleştiğini bildirdi ancak özgün ifadesi bulunamadığından bu karar tamamlayıcı kayıt olarak yeniden oluşturulmuştur. 119–122. kararlar için kullanıcı tarafından sağlanan metinler esas alınmıştır. Bu kaynak ayrımı korunacaktır.

- **101. Yükseliş başarısı (kullanıcının sağladığı karar metni):** Eşiğe değerlendirme süresi içinde ulaşılıp ulaşılmadığı ve süre sonunda fiyatın nerede kaldığı ayrı gösterilecek.
- **102. Aynı mumda hedef ve zarar durdurma (kullanıcının sağladığı karar metni):** Daha kısa zaman aralığındaki verilerle gerçekleşme sırası araştırılacak. Sıra belirlenemezse sonuç Belirsiz kaydedilecek ve başarı/başarısızlık hesabına katılmayacak.
- **103. Girişten önce hedefe ulaşılması (kullanıcının sağladığı karar metni):** Giriş gerçekleşmedi olarak kaydedilecek; hedef başarısı sayılmayacak.
- **104. Girişten önce zarar durdurmanın aşılması (kullanıcının sağladığı karar metni):** Plan girişten önce geçersizleşti olarak kaydedilecek. Takip sonlandırılacak; başarı veya başarısızlık işlem planı olarak sayılmayacak.
- **105. Giriş seviyesinin doğrulanması (kullanıcının sağladığı karar metni):** Daha kısa zaman aralığındaki veriler kullanılacak. Doğrulanamazsa sonuç Belirsiz olacak.
- **106. Giriş fiyatları (kullanıcının sağladığı karar metni):** Planlanan giriş fiyatı ile girişin doğrulandığı anda gözlemlenen fiyat ayrı kaydedilecek.
- **107. Birden fazla kâr hedefi (kullanıcının sağladığı karar metni):** Her hedef ayrı değerlendirilecek ve ayrı raporlanacak.
- **108. Ölçüm başlangıçları (kullanıcının sağladığı karar metni):** Radarın yükseliş tespit süresi sinyal anında; teknik işlem planının hedef ve zarar durdurma değerlendirmesi giriş doğrulandığında başlayacak. Giriş gerçekleşmezse ayrıca kaydedilecek.
- **109. Sabit ve olay bazlı takip (kullanıcının sağladığı karar metni):** 1 saat, 4 saat ve 24 saatlik ölçümler yapılacak; ayrıca hedef, zarar durdurma veya geçersizleşme olayları izlenecek.
- **110. 24 saat sonrasındaki takip (kullanıcının sağladığı karar metni):** Olay bazlı takip için sabit azami süre olmayacak. Takip, hedefe, zarar durdurmaya veya geçersizleşme koşuluna ulaşılana kadar sürecek.
- **111. Birden fazla hedefin takibi (kullanıcının sağladığı karar metni):** Her kâr hedefi ayrı izlenecek. İlk hedefin gerçekleşmesi diğer hedeflerin takibini bitirmeyecek. Bütün hedefler tamamlandığında veya zarar durdurma/geçersizleşme koşulu gerçekleştiğinde olay bazlı takip sonlandırılacak.
- **112. Ayrıntılı karar — hedef sonrasındaki zarar durdurma veya geçersizleşme (kullanıcının sağladığı karar metni):** Asistan tarafından belirlenen karar: Bir kâr hedefine ulaşıldıktan sonra zarar durdurma veya geçersizleşme gerçekleşirse önceki hedef başarıları korunacak. Ulaşılmamış hedefler ayrı gösterilecek ve sonraki olay da kaydedilecek. Rapor, önceki sonuçları silmeden planın tüm gelişimini gösterecek.
- **113. Erken, geç ve kaçırılmış yükseliş ayrımı — yeniden oluşturulmuş kayıt (özgün metin bulunamadı):** Bu sınıflandırma, izleme başlangıcındaki ilk geçerli fiyat ve yükseliş yolunun ilk %25'lik bölümü kuralına göre yapılır. Sınıflandırmanın referansı, 109. maddede ayrıştırılan izleme başlangıcıdır.
- **114. Sinyal üretmeyen coinlerin ölçümü — yeniden oluşturulmuş kayıt (özgün metin bulunamadı):** Taranan coinlerin sonraki fiyat hareketleri sinyal verilip verilmediğinden bağımsız olarak izlenir. Eşiği aşan fakat sinyalle yakalanmayan hareketler kaçırılan yükseliş ölçümüne katkı sağlar.
- **115. Yeni ve yinelenen sinyal ayrımı — yeniden oluşturulmuş kayıt (özgün metin bulunamadı):** Aynı sinyalin tekrarlanan bildirimi yeni bir ölçüm başlatmaz. Gerçekten yeni bir sinyal, benzersiz kimliğiyle ayrı ölçüm oluşturur; önceki ölçüm sürerken yeni ölçüm onu değiştirmez.
- **116. Eksik ölçümün ele alınması — yeniden oluşturulmuş kayıt (özgün metin bulunamadı):** Ölçüm sonu için güvenilir fiyat verisi yoksa sonuç eksik kaydedilir; başarı veya başarısızlık oranına dahil edilmez.
- **117. Eksik veri görünürlüğü — yeniden oluşturulmuş kayıt (özgün metin bulunamadı):** Eksik ölçümlerin sayısı, toplam ölçümlere oranı, ilgili pencere ve kayıtlıysa eksiklik nedeni raporlarda gösterilir. Eksik sonuçlar sessizce kaldırılmaz.
- **118. Teknik plan olaylarında temas ve teyit koşulu — yeniden oluşturulmuş tamamlayıcı kayıt:** Giriş, hedef, zarar durdurma ve geçersizleşme olayları, ilgili plana önceden kaydedilmiş tetikleme koşuluna göre değerlendirilir. Plan kapanış teyidi gerektiriyorsa yalnızca bu koşul gerçekleştiğinde olay doğrulanır; ek teyit kuralı yoksa kapanmış ve güvenilir mumun yüksek/düşük fiyatının ilgili seviyeye ulaşması temas olarak kaydedilir. Aynı mumda birden fazla olayın sırası güvenilir veriden belirlenemiyorsa sıra tahmin edilmez ve sonuç belirsiz olarak korunur. **Not:** Kullanıcı 118. kararın kesinleştiğini bildirmiştir; bu metin özgün metin bulunamadığı için hazırlanmış tamamlayıcı kayıttır, özgün ifadenin aynısı olduğu iddia edilmez.
- **119. Fiyat hassasiyeti ve yuvarlama — kullanıcı tarafından sağlanan karar metni:** Hedef, giriş ve zarar durdurma seviyelerinin karşılaştırılmasında mümkün olan en yüksek mevcut fiyat hassasiyeti kullanılacak. Ekranda gösterilen yuvarlanmış fiyatlar, gerçekleşme kararını belirlemeyecek. Böylece görüntüleme amacıyla yapılan yuvarlamalar nedeniyle hedef veya zarar durdurma yanlışlıkla gerçekleşmiş ya da gerçekleşmemiş sayılmayacak.
- **120. Yinelenen olay kayıtlarının önlenmesi — kullanıcı tarafından sağlanan karar metni:** Aynı kâr hedefi, zarar durdurma veya geçersizleşme olayı veri akışının tekrarlanması ya da sistemin yeniden başlaması nedeniyle birden fazla kez kaydedilmeyecek. Program, olayları ilgili işlem planı, hedef ve olay türü üzerinden ayırt edecek. Daha önce kaydedilmiş aynı olay yeniden geldiğinde mevcut kayıt korunacak; başarı sayısı ve raporlar ikinci kez artırılmayacak.
- **121. Sonradan gelen veri düzeltmeleri — kullanıcı tarafından sağlanan karar metni:** Daha sonra gelen güvenilir piyasa verileri önceki bir olay kaydını değiştiriyorsa, program eski kaydı sessizce silmeyecek veya üzerine yazmayacak. Düzeltilmiş sonuç yeniden değerlendirilecek; önceki kayıt, yeni sonuç, düzeltme nedeni ve doğrulama zamanı korunacak. Performans raporlarında en son doğrulanmış sonuç esas alınacak.
- **122. Düzeltilen verilerin raporlara yansıması — kullanıcı tarafından sağlanan karar metni:** Bir olayın sonucu sonradan düzeltildiğinde, bu değişiklikten etkilenen başarı oranları, toplam ölçümler ve ilgili grafikler en son doğrulanmış sonuçlara göre yeniden hesaplanacak. Daha önce oluşturulmuş raporların geçmiş sürümleri korunacak. Böylece güncel sonuçlar doğru hesaplanırken önceki raporlarla aradaki fark da izlenebilecek.

**Bu aralığın kaynak durumu:** 101–112 kullanıcı tarafından yeniden sağlanan karar metinlerine dayanır; 113–117 yeniden oluşturulmuş kayıtlardır; 118'in kesinleşme durumu biliniyor ancak özgün metni eksiktir; 119–122 kullanıcı tarafından sağlanan metinlere dayanır.

### Kesinleşmiş kararlar: 123–132

- **123. Sinyal ve ölçüm olaylarının benzersizliği:** Her sinyal ve ölçüm olayı benzersiz kimlikle kaydedilir; aynı olay ikinci kez oluşturulmaz.
- **124. Teknik işlem planının ana kimliği:** Her teknik işlem planının ana kimliği bulunur. Giriş, hedef, zarar durdurma ve geçersizleşme olayları bu kimliğe bağlanır.
- **125. Zaman gösterimi:** Zamanlar UTC (Eşgüdümlü Evrensel Zaman) olarak saklanır, Türkiye saatiyle gösterilir.
- **126. Olay zamanı ve veri ulaşma zamanı:** Piyasa olayının zamanı ile verinin programa ulaşma zamanı ayrı saklanır.
- **127. Ölçüm veri kaynağı ve yeterliliği:** Ölçümde kullanılan kaynak, zaman dilimi, son güvenilir mum zamanı ve veri yeterliliği kaydedilir.
- **128. Ölçüm koşullarının korunması:** Ölçüm koşulları ve kullanılan eşikler saklanır. Sonraki ayar değişiklikleri geçmiş ölçümlerin koşullarını değiştirmez.
- **129. Hesaplama mantığının sürümü:** Sonucu üreten hesaplama mantığının sürümü kaydedilir.
- **130. Belirsizlik nedenleri:** Belirsiz sonuçlarda belirsizlik nedeni de kaydedilir. Birden fazla neden bulunabilir.
- **131. Güvenilir geçmiş mumlar ve düzeltmeler:** Mum kapandıktan sonra güvenilir geçmiş mum verisi esas alınır. Sonradan gelen güvenilir düzeltmelerin eski kayıtları nasıl etkileyeceği önceki kararlar doğrultusunda yürütülür.
- **132. Ölçüm pencerelerinin başlangıcı:** 1 saat, 4 saat ve 24 saatlik ölçümler sinyal zamanından başlar; veri gecikmesi ölçüm süresini uzatmaz.

### Kesinleşmiş kararlar: 133–141

- **133. Sinyal başarısının ölçülmesi:** Aynı fiyat geçmişi üzerinden iki ayrı değerlendirme yapılır. **Radar başarısı:** Yükselişin ne kadar erken tespit edildiği, dönem içindeki en yüksek yükseliş ve en büyük düşüş. **Teknik plan başarısı:** Giriş, hedefler, zarar durdurma ve geçersizleşme koşullarının gerçekleşmesi. Aynı fiyat verisi iki ayrı sistemde yeniden toplanmaz.
- **134. Birden fazla hedefin ölçülmesi:** Her hedefin durumu ayrı değerlendirilir. Hangi hedeflere ulaşıldığı ve en yüksek ulaşılan hedef, gerçekleşen olay kayıtlarından türetilir. Aynı bilgi için ikinci bir olay kaydı oluşturulmaz.
- **135. Sonuçların sınıflandırılması:** Hedefe ulaşma, zarar durdurma, geçersizleşme, sürenin dolması, girişin gerçekleşmemesi ve belirsizlik değerlendirilir. Birden fazla olay gerçekleşebileceğinden yalnızca tek sonuç etiketiyle yetinilmez. Olayların sırası korunur. Sıra güvenilir biçimde belirlenemiyorsa tahmin yürütülmez; sonuç belirsiz kaydedilir.
- **136. Maliyet hesabının kapsamı:** Komisyon, kayma ve maliyet sonrası kazanç hesabı kapsam dışıdır. Program gerçek işlem performansını hesaplamaz; teknik fırsatları ve teknik planların fiyat hareketleri karşısındaki başarısını ölçer.
- **137. Teknik planın başarı koşulu:** Bir planın hedef başarısı sayılabilmesi için giriş koşulu gerçekleşmiş olmalıdır. Giriş gerçekleşmeden hedefe ulaşılması radarın fiyat hareketini tespit başarısına yazılır; teknik planın hedef başarısı sayılmaz. Giriş gerçekleşmişse hedef, zarar durdurma ve geçersizleşme olayları değerlendirilir. Giriş gerçekleşmezse plan, gerçekleşmiş işlem gibi başarılı veya başarısız sayılmaz. Olay sırası güvenilir biçimde belirlenemiyorsa sonuç belirsizdir.
- **138. Giriş koşulunun belirlenmesi:** Sinyalden sonraki kapanmış ve güvenilir mumun en düşük ve en yüksek fiyatı giriş bölgesiyle kesişirse giriş bölgesine temas kaydedilir. Teknik plan ayrıca kapanış, kırılım veya başka bir teyit koşulu gerektiriyorsa giriş ancak bu koşul gerçekleştiğinde doğrulanır. Ek teyit yoksa bölgeye temas yeterlidir. Geçmiş plan koşulları sonradan değiştirilerek eski sonuçlar yeniden yazılmaz. Aynı mumda giriş, hedef veya zarar durdurma olaylarının sırası belirlenemiyorsa tahmin yapılmaz.
- **139. Giriş öncesinde geçersizleşme:** Giriş gerçekleşmeden geçersizleşme koşulu oluşursa plan **“Giriş öncesi geçersizleşti”** olarak kaydedilir. Gerçekleşmiş işlem zararı sayılmaz. Radarın fiyat hareketini tespit başarısı ölçülmeye devam eder. Teknik planın geçersizleşmesi, 1 saatlik, 4 saatlik ve 24 saatlik radar ölçümlerini sonlandırmaz.
- **140. Hedefe ulaşıldığında zarar durdurma seviyesi:** Başlangıçta belirlenen hedefler ve zarar durdurma seviyesi sabit kalır. Bir hedefe ulaşılması zarar durdurma seviyesini kendiliğinden değiştirmez. Seviyeyi değiştiren bir kural varsa önceden belirlenmiş olmalıdır. Geçmiş plan koşulları sonradan oluşan fiyat hareketlerine göre geriye dönük değiştirilmez. Hedef ve zarar durdurma temasları ortak fiyat verisinden değerlendirilir.
- **141. Radar ölçümünün başlangıç fiyatı — kesinleşti:** 1 saatlik, 4 saatlik ve 24 saatlik sinyal sonrası radar ölçümlerinde başlangıç fiyatı, sinyali oluşturan kapanmış mumun kapanış fiyatıdır. Veri gecikmesi nedeniyle daha sonraki bir fiyat başlangıç referansı yapılmaz. Bu karar, **81–82. kararlardaki erken/geç/kaçırılan yükseliş sınıflandırması için kullanılan izleme başlangıcı fiyatını değiştirmez**; iki referans farklı ölçüm amaçlarına aittir. Geçmiş ölçümlerin başlangıç fiyatı sonradan değiştirilmez.

### Aynı sinyalin yeniden oluşması ve ortak kayıt ilkesi

- Önceki sinyalin 24 saatlik ölçümü devam ederken mevcut kayıt korunur.
- Aynı sinyalin tekrar bildirilmesi yeni ölçüm oluşturmaz.
- Gerçekten yeni bir sinyal oluşursa benzersiz kimliğiyle yeni ölçüm kaydı açılır.
- Önceki ve yeni ölçümler birbirini değiştirmeden sürer.
- 133–135. kararlar birlikte uygulanır: fiyat verisi ve olaylar ortak tutulur; farklı başarı ölçümleri bu kayıtlardan türetilir.

### Güncel devir noktası

- **Son kesinleşen karar:** 141.
- **Sıradaki karar:** 142.
- **Karar kaydının durumu:** 101–118 yeniden oluşturulmuş tamamlayıcı kayıt olarak mevcut; 119–122 kullanıcının sağladığı metinlerle kayıtlı. Özgün sohbet metinleri erişilebilir olmadığından kayıt kaynağı açıkça belirtilmiştir; bu durum sonraki tasarım kararlarının ilerlemesini engelleyen açık bir karar maddesi değildir.
- **Kayıt kuralı:** Her kesinleşen karar aynı oturumda README'ye yazılır, yeniden okunur ve doğrulanır; doğrulama bitmeden sonraki numaraya geçilmez.
- **Kodlama:** Açık kullanıcı onayı gelmeden başlanmayacak.
- **GitHub kapsamı:** Bu değişiklik yalnızca README'deki tasarım kararları ve devir kaydı içindir. Program kaynak kodu ve uygulama davranışı değiştirilmedi.
- **Mevcut program durumu:** Tasarım kararlarında hedef olarak yazılması, ilgili işlevin programda mevcut veya test edilmiş olduğu anlamına gelmez. Uygulama durumu ancak daha sonraki inceleme ve doğrulamayla belirlenir.

Yeni sohbet veya devam adımı 142. tasarım kararından başlamalıdır. 101–122 aralığı içerik olarak kayıtlıdır; yeniden oluşturulmuş metinler özgün sohbet alıntısı olarak sunulmaz. Birincil metin sonradan bulunursa sürüm farkı karşılaştırılır ve kullanıcı onaylı kararların anlamı korunur.
