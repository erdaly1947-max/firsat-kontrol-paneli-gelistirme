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
- Manifestten en yeni görüntünün UUID'si alınır. Ardından GET /images/{UUID}?format=base64 adresine yine benzersiz check sorgusu eklenir. Gelen JSON içindeki content_type ve Base64 data gerçek PNG/JPEG verisine dönüştürülerek ChatGPT'nin görsel algılamasına verilir. Sadece dosya adını görmek görüntüyü okumak sayılmaz.
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
