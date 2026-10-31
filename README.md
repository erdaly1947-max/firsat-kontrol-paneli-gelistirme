# Fırsat-Kontrol Paneli — güncel geliştirme ve teslim kaydı

Bu README, projenin güncel teknik özeti, gerçek çalışma durumu, kabul edilmiş işlev gereksinimleri ve bağlayıcı çalışma kurallarının tek kaydıdır. Eski günlükler ve birbiriyle çelişen talimatlar yerine aşağıdaki güncel durum ve kurallar geçerlidir. Tarihsel kayıtlar yalnızca hâlâ işe yarayan bir sürüm kimliği veya doğrulama kanıtı sağlıyorsa tutulur.

## Güncel uygulama durumu — 31 Ekim 2026 (önceki tarihli durum kayıtlarının yerine geçer)

Tarihsel Geri Test aşaması kullanıcıyla değerlendirilmiş ve kabul edilmiştir. Kullanıcı, 31 Ekim 2026 tarihinde daha önce onaylanan 153. madde Naratif Avcı tasarımının uygulanmasına, canlı teknik radar ile birlikte çalışmasına, ortak Başlat/Durdur yönetimine ve bütünleşik testine açıkça izin vermiştir. Bu bölüm, daha aşağıdaki “kodlama başlamadı”, “Naratif Avcı için kullanıcı görüşü bekleniyor” ve “Başlat/Durdur yalnızca teknik motoru yönetiyor” şeklindeki eski uygulama kayıtlarının yerine geçer.

**Bu aşamanın sonucu:** Naratif Avcı motoru, teknik radar bağlantısı, arayüz sayfası, radar erken izleme alanı, rapor aktarımı ve iki canlı motorun ortak kontrolü main dalına eklendi. Tasarım 153.1–153.15 için kod karşılıkları aşağıda tek tek izlenir. GitHub Actions doğrulaması tamamlanmadan testlerin başarılı olduğu ileri sürülmez. Kullanıcı görüşü alınana kadar sonraki genel arayüz aşamasına geçilmez.

### 153.1–153.15 uygulama ve kayıt takibi

| Madde | Onaylanmış tasarımın kod karşılığı | Durum |
|---|---|---|
| 153.1 | Naratif puanı teknik puandan ayrıdır. Teknik adaylara yalnızca destek bilgisi eklenir; güçlü fırsat kapısı ve teknik puan değiştirilmez. | Uygulandı; birim/sözleşme testi eklendi. |
| 153.2 | Her kaynak için ayrı yenileme aralığı ve yerel önbellek kullanılır. | Uygulandı. |
| 153.3 | Bir kaynağın hatası diğerlerini durdurmaz. Önceki veri korunur ve eski/hatalı durum görünür kalır. | Uygulandı; kaynak hatası testi eklendi. |
| 153.4 | Ücretsiz/izinli AIXBT Topics, anahtarsız CMC listeleme, DEX Screener ve RSS/Atom kaynakları bağlanır; anahtar veya entegrasyon gerektirenler ayrı işaretlenir. | Kısmen uygulandı; kaynak tablosu aşağıdadır. |
| 153.5 | Tek kaynaklı kayıtlar silinmez; güven seviyesi ve eksik kanıt gösterilir. | Uygulandı. |
| 153.6 | İlgi ivmesi, veri güncelliği, bağımsız kaynak çeşitliliği, olay sayısı, proje yayılımı, fiyat ve hacim tepkisi mevcut veriye göre ayrı bileşenlerdir. | Uygulandı; başlangıç sezgisel puanlaması, henüz piyasa geçmişinde kalibre edilmedi. |
| 153.7 | Başlangıç, Yayılma, Güçlenme, Aşırı Isınma, Zayıflama ve Belirsiz aşamaları kullanılır. | Uygulandı. |
| 153.8 | Naratif, olay ve bildirim geçmişi SQLite'a kaydedilir; ilk gözlem zamanı korunur. | Uygulandı; geçmişe dönük veri doldurulmaz. |
| 153.9 | Kayıtlı ortak Binance–BtcTurk USDT evreni varsa kullanılır; yoksa yerel BtcTurk listesine düşülür ve kesişimin doğrulanmadığı açıkça yazılır. | Uygulandı; güncel ortak evrenin gerçek zamanlı tazeliği ayrıca izlenmelidir. |
| 153.10 | Proje adı/alias ve sınırları belirlenmiş sembol eşleştirmesi yapılır; belirsiz sembol eşleşmesi düşük güvenle işaretlenir. | Uygulandı; serbest yazım benzerliğiyle bulanık eşleştirme bu sürümde yoktur. |
| 153.11 | Aynı başlıklı yinelenen haber tek olay sayılır; tekrar yayıncıları ayrı teyit puanı üretmez. | Uygulandı. |
| 153.12 | Naratif listesi, ilişkili coinler, ayrıntı, kaynak durumu, gelişmeler ve piyasa tepkisi arayüzde gösterilir. | Uygulandı. |
| 153.13 | Yükselen, kanıtı daha güçlü ve aşırı ısınmamış naratifler üstte sıralanır; eksik veri kaydı görünür kalır. | Uygulandı. |
| 153.14 | Aşama ve ilgi yönü filtreleri eklendi. | Uygulandı. |
| 153.15 | Yeni naratif ve Yayılma/Güçlenme geçişi bildirimi oluşturulur; bildirim alım veya güçlü fırsat emri değildir. | Uygulandı; JSON durumuna, SQLite'a ve rapora yazılır. |

### Naratif Avcı — gerçek kaynak kapsamı

Kaynak kodda bir adresin bulunması, canlı bağlantının başarılı olduğu anlamına gelmez. Çalışma anındaki kesin durum Naratif Avcı sayfasında her kaynağın BAĞLI, ÖNBELLEK, ERİŞİLEMEDİ, HATA, ESKİ VERİ veya BAĞLI DEĞİL durumu ile gösterilir. Kaynak seçildiğinde rolü, son başarılı erişimi, son denemesi, veri yaşı ve hata metni açılır.

| Kaynak | Kullanım ve sınır |
|---|---|
| AIXBT v3 Topics | Ücretsiz/anahtarsız konu keşfi; ilk 25 konu ile sınırlı. Konu→proje ayrıntılı eşlemesi bu kodda çağrılmıyor. |
| CoinMarketCap halka açık v3 listeleme | Anahtarsız piyasa listeleme/aktivite verisi. Haber veya bağımsız haber kaynağı olarak sayılmaz; ilk 100 kayıtla sınırlı istek yapılır. |
| DEX Screener token profiles | Anahtarsız proje/token görünürlüğü. Tek başına organik talep veya haber teyidi değildir. |
| DEX Screener community takeovers | Anahtarsız topluluk görünürlüğü. Tek başına bağımsız haber teyidi değildir. |
| CoinGecko Trending | Ücretsiz Demo erişimi için COINGECKO_DEMO_API_KEY ortam değişkeni gerekir. Anahtar yoksa devre dışıdır; gizli anahtar ayarlar dosyasına yazılmaz. |
| RSS/Atom | Varsayılan akışlar Ethereum Foundation, CoinDesk, Cointelegraph ve The Block. HTTPS adresleri ayarlar.json içindeki narrative_rss_feeds ile, aralık narrative_rss_interval_seconds ile düzenlenebilir. Her yayın akışının erişimi ayrı izlenir. |
| AIXBT konu→proje eşlemesi | Ek API erişimi/hesap yetkisi gerekebileceği için kullanılmıyor; bağlı gibi gösterilmez. |
| Santiment Individuals Free | Yalnızca ücretsiz ve güncel erişimli `active_addresses_24h` ile `dev_activity` (modern:v1) sorgulanır. Proje kataloğu sembol/ad tam eşleşmesiyle bağlanır. API anahtarı `SANTIMENT_API_KEY` ortam değişkeninden okunur. |
| Santiment kısıtlı ölçümleri | Social Volume/Dominance, Community Social Volume, transaction volume ve exchange inflow/outflow kullanılmaz: Free API erişiminde kısıtlı ölçümlerin son 30 günü kapalıdır; güncel naratif takibi için uygun değildir. |
| X | Kullanıcı kararıyla entegrasyondan vazgeçildi; hiçbir X API çağrısı yapılmaz. |
| Reddit | Data API başvurusu gönderildi; onay ve OAuth bilgileri bekleniyor. Bu aşamada veri çağrısı yapılmaz. |

Naratif motoru kaynak hatasında diğer kaynaklara devam eder. HTTP isteklerinin zaman aşımı 10 saniyedir. Kaynak aralıkları AIXBT 5 dakika, CMC/DEX profilleri/CoinGecko 10 dakika, DEX topluluk akışı 15 dakika, RSS varsayılan 15 dakikadır. Santiment proje kataloğu 30 günde bir; ücretsiz aktif adres ve geliştirici etkinliği ölçümleri 6 saatte bir sorgulanır. En fazla 30 eşleşen coin tek metrik sorgusunda toplu alınır. Free API aylık 1.000 çağrı sınırı içinde yaklaşık 241 çağrı/30 gün hedeflenir. API anahtarı yalnızca `SANTIMENT_API_KEY` ortam değişkeninden okunur. Herhangi bir kaynağın canlı erişimi yalnızca programın çalışma anında BAĞLI sonucu alınırsa doğrulanmış sayılır.

### Naratif puanı ve geçmişin yorumu

Puan; mevcut kanıta göre AIXBT konu sırası, farklı olay sayısı, bağımsız haber kaynağı sayısı, ortak evrende ilişkilendirilen proje sayısı, kaynak güncelliği, ilişkili coinlerin 24 saatlik fiyat tepkisi ve 24 saatlik hacim tepkisi bileşenlerinin kullanılabilir olanlarının ortalamasını temel alır. Önceki gözlem varsa ilgi ivmesi ayrıca hesaplanır ve taban puanı en fazla ±10 puan etkiler; nötr ivme tek başına puanı düşürmez. Mevcut olmayan bileşenler uydurulmaz, eksik kanıt listesinde kalır.

Bu eşikler ilk uygulama sezgisidir; geçmiş naratif veri setiyle kalibre edilmiş veya kârlılığı kanıtlanmış değildir. AIXBT konu sırası keşif verisidir, bağımsız haber teyidi değildir. CMC/DEX piyasa aktivitesi haber olarak değerlendirilmez. Yinelenen haberler kaynak çeşitliliğini yapay olarak artırmaz.

Naratif geçmişi motorun ilk gerçek çalıştırıldığı andan itibaren oluşur. Önceki tarihlere haber veya puan geri doldurulmaz. Bu nedenle 154 Tarihsel Geri Test aşamasının geçmiş sonuçlarına naratif katkı eklenmiş gibi davranılmaz. 154'ün teknik geçmiş sonuçları geçerliliğini korur; naratifin gelecekteki etkisi ancak bundan sonra birikecek gerçek gözlemler üzerinden değerlendirilebilir.

### Teknik radar, arayüz ve raporlama entegrasyonu

- naratif_avcisi.py bağımsız süreçtir; kaynak önbelleği, durum JSON'u, SQLite geçmişi ve ayrı log dosyası kullanır.
- binance_erken_firsat_radari.py naratif durumunu her tarama döngüsünde okur. Teknik adayla eşleşen naratif bilgisi ayrı narrative_support alanında tutulur. Teknik sinyal bulunmayan coinler ayrıca narrative_early_watch listesine yazılır.
- Fırsat Radarı'nda teknik adaylardan ayrı “Naratif erken izleme” tablosu bulunur. Buradaki coinler teknik aday veya güçlü fırsat gibi gösterilmez. Naratif Avcı sayfasında ayrıntıları açılır.
- Parite Analizi ve teknik aday ayrıntısı naratif desteğini ayrı gösterir; teknik puan, likidite kapısı ve güçlü fırsat alarmı bundan etkilenmez.
- Rapor, mevcut Cloudflare Worker sözleşmesiyle uyum için schema_version: 1 değerini korur. Teknik adayda narrative_support; ayrı narrative bölümünde naratifler, erken izleme, kaynak durumları, bildirimler ve kapsam sınırları yer alır.
- Naratif puanı tek başına güçlü fırsat/alım alarmı oluşturmaz. Program otomatik emir göndermez.

### İki canlı motorun ortak yönetimi — 155 kapsamındaki onaylı alt iş

- Üst Başlat düğmesi teknik radar ile Naratif Avcı'yı iki ayrı Python süreci olarak birlikte başlatır.
- Durdur düğmesi iki sürece kendi durdurma işaretini gönderir. Her sürecin PID/çalışma/durdurma ve hata durumu ayrı izlenir; birinin başlatma hatası diğerinin başarılı başlamasını engellemez.
- Panel kapanırken çalışan canlı süreçler için kontrollü durdurma istenir.
- Tarihsel Geri Test ayrı iş parçacığı ve kendi iptal işaretiyle çalışır. Canlı motorların Başlat/Durdur düğmeleri tarihsel geri testi başlatmaz veya durdurmaz.

### Bu aşamada değiştirilen dosyalar

- naratif_avcisi.py
- binance_erken_firsat_radari.py
- tek_motor_paneli.pyw
- analysis_report.py
- tests/test_narrative_engine.py
- tests/test_panel_ui_contract.py
- tests/windows_ui_smoke.py
- cloudflare/report-worker/test/index.test.js

Test kapsamı AIXBT/CMC/RSS ayrıştırması, sembol eşleştirme, olay tekilleştirme, kaynak hata/önbellek davranışı, geçmiş kayıt, bildirimler, puan ayrımı/ivmesi, rapor şeması, arayüz sözleşmesi, iki motorun ortak kontrolü ve Windows gezinmesini içerir. Son kod commitinde GitHub Actions doğrulaması başlatılmıştır; Windows testi, Python birim testleri, kaynak derlemesi ve Worker/Render testlerinin sonucu Actions tamamlanınca ayrıca kaydedilecektir. Canlı kaynak kontrolleri CI'da o anki dış servis durumunu gösterir; kullanıcının kendi bilgisayarındaki tüm kaynak erişimlerini veya kendi tam piyasa arşivini doğrulamaz.

**ZIP/paketleme:** Bu aşamada ZIP veya GitHub Release üretilmedi. Paketleme iş akışının ayrı açık onay gerektiren adımı başlatılmadı.

### Bu aşamada özellikle yapılmayan işler ve durma noktası

- Kullanıcının istediği Dosya Gezgini benzeri genel çalışma alanı/sekme/araç çubuğu tasarımı henüz baştan sona uygulanmadı. Şimdiki Naratif sayfası mevcut Tkinter yapısına eklenmiş işlevsel bir sayfadır; nihai görsel tasarım olarak kabul edilmez.
- Kullanıcının grafik çizimlerinin arayüzden ve koddan çıkarılması talimatı bu aşamada uygulanmadı. Mevcut grafik alanı ve ona ait testlerin kaldırılması sonraki arayüz çalışmasının açık işidir.
- 155. maddenin tamamı bitmiş sayılmaz. Yalnızca iki canlı motorun ortak Başlat/Durdur alt işi uygulanmıştır. Genel ekran düzeni, gezinme ve son 1–155 karşılaştırması bekler.
- Kullanıcıya bu tamamlanan aşama sunulacak ve görüşü alınacaktır. Bu görüş alınmadan Dosya Gezgini benzeri genel arayüz yenilemesine, grafik kaldırma işine veya başka bir sonraki geliştirme aşamasına başlanmayacaktır.


## Güncel doğrulanmış durum — 31 Ekim 2026

### Canlı Render hizmeti

- Hizmet: firsat-kontrol-market-relay
- Canlı adres: https://firsat-kontrol-market-relay.onrender.com
- Render yönetimi: https://dashboard.render.com/web/srv-dbf3n80n74is73beeeog
- Kaynak depo: https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme
- Kaynak dalı: main; otomatik dağıtım açık.
- Çalışma ortamı: Node.js. Derleme komutu: npm install --prefix render_relay --omit=dev --no-package-lock. Başlatma komutu: npm start --prefix render_relay.
- 28 Ekim 2026 saat 20:21 TRT civarında commit 008b678 başarıyla dağıtıldı; Render günlükleri sunucunun 10000 portunda hazır olduğunu ve hizmetin canlıya geçtiğini gösterdi. Bu tarihsel dağıtım doğrulaması, 31 Ekim'deki mevcut hizmet durumunu göstermez.
- CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY ve CLOUDINARY_API_SECRET değerleri Render ortam değişkenlerine girildi; gizli değerler bu README'ye, masaüstü paketine veya sohbete yazılmaz.
- Dağıtım sonrası canlı /images/manifest uç noktasından JSON biçiminde ok: true yanıtı ve görüntü kayıtları alındı. Bu, canlı hizmetin Cloudinary'den mevcut görüntü listesini okuyabildiğini doğrular; masaüstü programından canlı hizmete tam yükleme akışının uçtan uca çalıştığını tek başına kanıtlamaz.
- Masaüstü görüntü aktarımının canlı adrese geçirilmesi commit `5ae27ccf19b361c2333d6ccf10a5834dfcc46807` ile yapıldı. Bu commitin GitHub Actions doğrulaması [#40741310609](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/actions/runs/40741310609) başarıyla tamamlandı; o tarihte Render canlı hizmeti yeni kaynaktan çalışıyor ve canlı manifest `ok: true` döndürüyordu.
- 31 Ekim 2026 tarihli son canlı kontrol [Actions #41128528909](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/actions/runs/41128528909) Render `/healthz` için HTTP 503 `Service Suspended` döndürdü. Kullanım kotası sınırına ulaşıldığı için Render hizmeti askıya alınmış durumdaydı. Aynı çalıştırmada doğrudan BtcTurk USDT fiyat kontrolü 191 pariteyle başarılıydı; Render hatası Binance'in doğrudan bağlantısının başarısız olduğunu göstermez.

### Görüntü aktarımını canlıya geçirme — 28 Ekim 2026 tarihli önceki uygulama

- 28 Ekim'de doğrulanan önceki sürüm, ekran görüntüsü yükleme, manifest ve görüntü indirme işlemlerini Render görüntü geçidi üzerinden yürütüyordu.
- O sürümün kaynak değişikliği commit 5ae27ccf19b361c2333d6ccf10a5834dfcc46807 ile yapılmış, ilgili GitHub Actions doğrulaması #40741310609 başarıyla tamamlanmıştı. Bu tarihsel doğrulama, daha sonra eklenen Cloudinary doğrudan aktarım akışını test etmiş sayılmaz.
- 30 Ekim 2026'da eklenen doğrudan Cloudinary yükleme ve teslim adresi kullanımı, bu eski aktarım tarifinin yerine geçer; güncel akış aşağıdaki “Doğrudan bağlantı ve yedek yollar” bölümünde açıklanır.
- firsat-kontrol-test-relay ayrı test hizmetidir; masaüstü programının normal hedefi değildir.

Canlı manifestten görüntü listesini okuyabilmek, masaüstü programından gerçek görüntü yükleme, commit, indirme ve tekrar okuma akışının uçtan uca çalıştığını tek başına kanıtlamaz. Her sürümde bu adımların ayrı doğrulanması gerekir.

### Görsel gönderme ve doğrudan inceleme — başarıyla doğrulanmış yöntem

28 Ekim 2026'da kullanıcı tarafından panel aracılığıyla buluta gönderilen birden fazla ekran görüntüsü manifestten bulundu, görüntü baytları indirildi ve görsel içerikleri gerçekten açılıp okundu. Bu, yalnızca dosya adlarını görmek değil, pikselleri ChatGPT'nin görsel algılamasına aktarıp ekrandaki içeriği incelemek şeklinde çalıştı.

Görüntü yolu:
1. Güncel görüntü manifesti, önbellek kırıcı benzersiz sorgu parametresi eklenerek alınır.
2. Manifestteki en yeni görüntü kimliği ile görüntü baytları alınır.
3. Görüntü gerçek bir PNG/JPEG görüntüsü olarak açılır ve incelenir.

Kullanıcı “fotoğraf gönderdim”, “görsel gönderdim” veya “ekran görüntüsü gönderdim” dediğinde ilk yapılacak işlem doğrudan bulut manifestini kontrol edip en yeni görüntüyü açmaktır. Önce web araması yapılmaz, başka ekranlarda dolaşılmaz ve kullanıcıdan görüntüyü yeniden sohbete yüklemesi istenmez. Bulut erişimi başarısız olursa bu açıkça bildirilir; görüntü görülmüş gibi davranılmaz.

Masaüstü kodundaki ilgili işlevler analysis_report.py içindedir: görüntü partisi yükleme, geçici yükleme, commit, manifesti alma ve görüntüyü çekme. Sunucu tarafındaki görüntü uçları render_relay/server.js içindedir. Cloudinary anahtarları yalnızca Render ortamında tutulur. Aktif manifest en fazla üç görüntü gösterir; yükleme PNG/JPEG için tasarlanmıştır ve tek görüntünün boyut sınırı 15 MiB'dir.

### Doğrudan bağlantı ve yedek yollar — 30 Ekim 2026

Bu bölüm, bağlantı maliyetini azaltan ve doğrudan erişim başarısız olduğunda mevcut Render geçidini koruyan uygulama akışını açıklar. Hedef, veri akışını veya tarama sıklığını azaltmak değil; aynı piyasa olaylarını ve rapor/görüntü işlevlerini daha az ara sunucu trafiğiyle taşımaktır.

- **Binance ve BtcTurk REST:** İzin verilen piyasa istekleri önce resmî borsa adreslerine gider. Bağlantı/TLS gibi erişim hatalarında uygun alternatif doğrudan adresler denenir; bunlar başarısız olursa Render geçidine dönülür. Borsa kaynaklı HTTP 429/418 gibi hız sınırı yanıtları, başka bir host üzerinden tekrar edilerek aşılmaya çalışılmaz. REST yol durumu borsa ve veri türü bazında ayrı izlenir. Render yedeği çalışırken doğrudan yol 30–60 saniyede bir yeniden sınanır; Render da erişilemez olursa sistem bekleme süresini beklemeden doğrudan borsa adreslerini hemen yeniden dener.
- **Binance WebSocket:** Resmî doğrudan akış adresleri önce denenir; Render WebSocket yalnızca son yedektir. Render yedeği format=fkp1 ile 25 ms'lik küçük gruplarda kayıpsız deflate sıkıştırması kullanır. Her özgün Binance olayı satır sınırlarıyla korunur; masaüstü FKP1 işaretini ve sıkıştırmayı çözer, olayları sırayla işler. Mumlar birleştirilmez, ara olaylar atlanmaz ve tarama aralığı büyütülmez. Render yedeğinde bağlantı 60 saniyede bir yenilenerek doğrudan erişim yeniden sınanır.
- **Analiz ve durum raporları:** analysis_report.py önce raporu Cloudflare Worker'a doğrudan gönderir. Doğrudan gönderim başarısız olursa aynı gövde mevcut Render rapor geçidine yedeklenir. Gzip/ZIP biçimleri ve rapor veri yapıları korunur.
- **Ekran görüntüsü yükleme:** Masaüstü önce Render /api/images/sign-upload uç noktasından kısa bir imzalı yükleme talimatı alır. Render kimlik doğrulamasını yapar ve Cloudinary gizli anahtarını sunucuda tutarak imzayı üretir. Görüntü baytları daha sonra masaüstünden Cloudinary'ye doğrudan gönderilir. Bu doğrudan aktarım başarısız olursa mevcut Render /api/images/stage yolu yedek olarak kullanılır. Commit/abort ve manifest işlemleri Render üzerinden sürer.
- **Ekran görüntüsü indirme:** Manifestteki Cloudinary teslim adresi yalnızca beklenen Cloudinary alan adı, hesap ve dosya kimliği doğrulanırsa kullanılır. Doğrudan indirme başarısız olursa mevcut Render görüntü indirme yolu yedek olarak denenir. Önizleme, orijinal görüntü dosyasını değiştirmez.

**Çalışma sınırı:** İmzalı doğrudan yükleme için imza alma, grup commit/abort ve güncel manifest okuma hâlâ Render hizmetine erişim gerektirir. Görüntü baytlarının Cloudinary'ye doğrudan gönderilmesi veya indirilmesi, ancak bu Render kontrol/manifest adımlarından sonra mümkündür. Render hizmeti askıdaysa doğrudan Cloudinary bayt aktarımı tek başına yeni bir yükleme/manifest akışı başlatamaz; bu durum, Render yedeğinin hazır olduğu veya canlı görüntü akışının çalıştığı şeklinde yorumlanmamalıdır. Canlı hizmet kontrolü başarısızsa otomatik test sonucu bunu ayrıca belirtmelidir.

### Doğrudan ve Render canlı testleri; ZIP paketleme ayrımı — 31 Ekim 2026

- **Binance doğrudan WebSocket testi:** `render_relay/direct-binance-smoke-check.mjs` resmî Binance WebSocket adreslerini sırayla dener. Yalnızca bağlantı el sıkışmasının başarılı olmasını yeterli saymaz; BTCUSDT 1 dakikalık canlı mum mesajını gerçekten alıp doğrular. Render adresini kullanmaz.
- **Render WebSocket testi:** `render_relay/smoke-check.mjs` Render sağlık yanıtını, Render üzerinden Binance REST verisini ve `/ws/binance/stream` adresinden gerçek canlı mum mesajını ayrı şekilde doğrular.
- İki canlı test GitHub Actions içinde ayrı adımlarda yürür ve ayrı sonuç üretir. Böylece doğrudan Binance testi başarısızken Render testi, Render testi başarısızken doğrudan Binance testi ayrıca görülebilir.
- **ZIP üretimi canlı bağlantı testlerinden bağımsızdır.** Python/JavaScript doğrulamaları, birim testleri ve gerçek Windows arayüz testi başarılıysa; kullanıcı `workflow_dispatch` üzerinden `publish_package=true` açık onayıyla paketlemeyi başlatmışsa ZIP, SHA-256 ve istenen Release/artefakt yüklemesi canlı test sonuçları birleştirilmeden önce tamamlanır. Canlı testlerden biri başarısızsa Actions çalıştırması ayrıca başarısız olarak raporlanabilir; daha önce oluşturulan ZIP silinmez veya paketleme atlanmaz.
- Bu canlı ağ testleri GitHub Actions sunucusunda çalışır; kullanıcının o anda bağlı olduğu ev/telefon internetini ölçtüğü anlamına gelmez. Masaüstü programının doğrudan Binance ve Render yedeği arasında otomatik geçiş mantığı kaynak kod ve birim testleriyle ayrıca doğrulanır.

## Programın amacı ve mevcut kapsamı

Program, hızlı yükseliş potansiyeli taşıyan coinleri erken bulmaya yardımcı olan bir teknik analiz ve karar destek aracıdır. Temel amaç, kullanıcının para kazanmasına yardımcı olabilecek fırsatları erkenden tespit edip değerlendirmesini desteklemektir. Otomatik alım-satım yapmaz, borsa hesabına bağlanmaz ve emir göndermez. Güçlü fırsat ya da A/B/C sınıflandırması kârlılık öngörüsü içindir.

Mevcut kaynakta şu işlev aileleri bulunur:
- Binance Spot halka açık piyasa verisi ve WebSocket mum akışı; BtcTurk yerel USDT Spot parite listesi üzerinden ortak tarama evreni. BtcTurk fiyatı bilgi amaçlıdır; teknik mum analizi Binance verisinden yapılır.
- 5m, 15m, 30m, 1h, 4h, 1d, 1w ve 1M olmak üzere sekiz zaman dilimi; veri tazeliği ve geçmiş mum hazırlığının ayrı takibi.
- EMA, MACD, RSI, ADX, DMI, ATR ve hacim göstergeleri; kapanmış mumlardan pivot, destek/direnç, kanal ve Fibonacci seviyeleri.
- BTC piyasa bağlamı ve risk durumu; BTC'ye göre göreceli güç ve korelasyon değerlendirmesi.
- Aday puanı ve sıralaması, A/B/C aşama değerlendirmesi, veri/likidite/teyit kapıları, koşullu giriş bölgesi, stop, teknik hedefler ve geçersizleşme koşulları.
- Alarm ve sinyal geçmişi, tek motorlu Windows paneli, günlük/analiz/sorun giderme raporları ve sorun giderme ZIP'i.
- Bulut raporları için Cloudflare Worker ve piyasa verisi için ayrı Render geçidi.

Kodda işlevin bulunması, o işlevin tarihsel piyasa koşullarında kârlı çalıştığının kanıtı değildir. Gerçek piyasa verileri üzerinde sistematik backtest, kaçırılmış yükseliş/yanlış pozitif ölçümü ve maliyet sonrası net risk/getiri henüz bu README'de doğrulanmış tamamlanmış özellikler olarak gösterilemiyor.

## Tarihsel geri test — tamamlanan ilk geliştirme aşaması

- Modül: `tarihsel_geri_test.py`; mevcut `binance_mum_arsivi.py`, `radar_core.py` ve `build_trade_plan` işlevlerini kullanır. Canlı radardan ayrı bir teknik sinyal hesabı oluşturmaz.
- Çalıştırma yeri: masaüstü panelinin **Raporlar** sayfası. Parite alanı boş bırakılırsa 5m arşivinde bulunan tüm USDT pariteleri kullanılır. İsteğe bağlı parite listesi virgül veya boşlukla ayrılır. Başlangıç/bitiş takvimi UTC tarihidir; bitiş günü dahildir. Geri test ayrı bir arka plan iş parçacığında çalışır ve güvenli durdurma kontrolü sunar.
- Yeniden oynatma: her 5 dakikalık mumun kapanış anında değerlendirme yapılır. O anda tam kapanmamış mumlar dışarıda tutulur. Her zaman diliminde beklenen son mum yoksa o anki değerlendirme eksik işaretlenir; mum boşluğundan önceki veriler gösterge ısınmasına dahil edilmez.
- Raporlar: her sinyal döneminin ilk tespit anı, A/B/C gelişimi ve karar değişimleri; 1h/4h/24h ileri kapanış getirileri; 24h MFE/MAE; teknik giriş/stop/ilk hedef olayları; JSON özet ve sıkıştırılmış aday-gözlem CSV dosyası.
- Teknik plan geri testi: giriş bölgesi, stop ve ilk hedef yalnızca sonraki 5m mumlarının OHLC aralığından izlenir. Giriş ve hedef/stop aynı mumda görülürse olay sırası bilinmediği için sonuç belirsiz bırakılır. Seviye görülmesi gerçek emir dolumu sayılmaz. Tahmini komisyon varsayımı uygulanır; fiyat kayması (slippage) ve emir defteri etkisi hesaplanmaz.
- Puan karşılaştırması: arşivde geçmiş emir defteri/spread/derinlik saklanmadığı için likidite bileşeni ölçülemez. Tarihsel puan bu 5 puanı toplamdan çıkarıp ölçülebilir bileşenleri 100'e ölçekler; güçlü fırsat uygunluğu ise `DEĞERLENDİRİLEMEDİ` kalır. Bu sonuç başarısız likidite kapısı veya güçlü fırsat teyidi gibi yorumlanmaz.
- 154 geliştirme aşamasındaki tarihsel kayıt: O tarihte Naratif Avcı henüz uygulanmamıştı. 31 Ekim 2026'da sonradan eklenen canlı Naratif Avcı, geçmişe dönük kayıt üretmez; tarihsel test dönemine naratif katkısı eklenmiş gibi gösterilmez. Güncel kod ve entegrasyon durumu bu README'nin başındaki 31 Ekim güncel bölümünde kayıtlıdır.
- Kaçırılmış yükseliş sayısı, sayısal yükseliş eşiği mevcut tasarımda tanımlanmadığı için tahmin edilmez. Bu eşik ayrıca netleşmeden başarı/kaçırma oranı uydurulmaz.
- Testler: `tests/test_historical_backtest.py` zaman sınırı, mum boşluğu, ileri fiyat ufukları, aynı mumdaki belirsiz olay sırası, arşiv parite listesi ve uçtan uca rapor yazımını sınar. `tests/windows_ui_smoke.py` Raporlar ekranında geri test başlat/durdur kontrollerini gerçek Windows Tkinter penceresinde doğrular.

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
- tests/ — Python işlev testleri ve regresyon kontrolleri. Doğrudan Cloudinary imzalı yükleme/yedek yolu, rapor Cloudflare→Render yedek akışı ve Binance FKP1 WebSocket paket çözme/sıralama testleri bu kapsamda yer alır.
- .github/workflows/validate-and-package.yml — kaynak doğrulama, test ve açıkça istenen son paketleme akışı.

## Bağlantılar ve entegrasyon kullanım haritası

Bu bölüm, bir hizmet/eklenti bağlantısı yeniden kurulacağı veya bir işlev taşınacağı zaman başvuru kaydıdır. Programın kullandığı bağlantılar ile ChatGPT'nin inceleme sırasında kullandığı bağlantılar ayrıdır. URL veya gizli anahtarı değiştirmeden önce ilgili kod ve bu harita kontrol edilir.

### GitHub — kaynak kod ve testler

- Ana depo: https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme
- Güncel dal: main. Kabul edilmiş sürüm zinciri, main tamamlanıp sabitlendikten sonra yeni sürüm dallarına bir önceki sürümün eksiksiz kopyalanması esasına dayanır.
- .github/workflows/validate-and-package.yml Python derlemesini/birim testlerini, Worker testlerini, gerçek Windows Tkinter pencere/gezinme testini ve ayrı doğrudan Binance/Render canlı bağlantı kontrollerini çalıştırır. Render testinin başarısız olması doğrudan Binance testinin sonucunu gizlemez.
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
- /ws/binance/stream?streams=...: Binance genel WebSocket mum akışı. Masaüstü Render yedeğinde format=fkp1 ister; sunucu özgün olayları 25 ms'lik deflate gruplarında iletir.
- POST /api/report, /api/report/daily, /api/report/troubleshooting, /api/report/troubleshooting-zip: Cloudflare doğrudan rapor gönderimi başarısız olduğunda raporları Worker'a aktaran yedek yol.
- POST /api/images/sign-upload: masaüstüne güvenli Cloudinary doğrudan yükleme imzası ve geçici görüntü kimliği verir.
- POST /api/images/stage: Cloudinary doğrudan aktarımı başarısız olursa kullanılan mevcut Render görüntü yükleme yedeği.
- POST /api/images/commit, /api/images/abort: görüntü grubunu etkinleştirme veya geçici yüklemeleri iptal etme.
- GET /images/manifest: etkin Cloudinary görüntü listesi ve doğrulanmış doğrudan teslim adresleri.
- GET /images/{UUID}?format=base64: seçilen görüntü baytlarını JSON içinde Base64 biçiminde döndürür; küçük görüntü/önizleme sınırları korunur.

Sunucu kodu render_relay/server.js, sınırlı REST önbelleği render_relay/rest_cache.js, sunucu testleri render_relay/test/, canlı piyasa kontrolü render_relay/smoke-check.mjs içindedir. Canlı piyasa kontrolü sağlık, Binance mum verisi, BtcTurk USDT ticker'ı ve gerçek WebSocket mesajını ayrı ayrı doğrular; yalnızca hizmetin live görünmesi yeterli değildir.

### Cloudinary — görüntü dosyası saklama

- Görüntü dosyalarını Cloudinary saklar. Masaüstü, yükleme öncesinde Render /api/images/sign-upload üzerinden kimliği doğrulanmış imza bilgisi alır; ardından görüntü baytlarını Cloudinary'ye doğrudan gönderir.
- Render ortamında CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY ve CLOUDINARY_API_SECRET bulunmalıdır. API Secret yalnızca Render sunucusunda kullanılır; masaüstü kaynak koduna, yanıta veya ZIP'e konmaz. İmzalı yanıt API Key ve imzayı içerir; gizli anahtar içermez.
- İmzalı aktarım başarısız olursa masaüstü, önceki Render /api/images/stage yükleme yoluna döner. Render stage/commit/abort, en fazla üç etkin görüntü, manifest ve indirme yedekleri render_relay/server.js ile render_relay/test/cloudinary-images.test.js içinde sınanır.
- Manifestteki doğrudan teslim adresi masaüstünde tekrar doğrulanır; doğrudan Cloudinary indirmesi başarısızsa Render görüntü indirme yolu kullanılır. API Secret paylaşılmaz.

### Cloudflare — rapor saklama ve okuma

- Worker: https://firsat-kontrol-analysis-report.erdaly1947.workers.dev
- Kaynak: cloudflare/report-worker/src/index.js
- Kılavuz: cloudflare/report-worker/README.md
- Sağlık: GET /health
- Analiz: POST /api/report, oku GET /latest
- Günlük: POST /api/report/daily, oku GET /daily
- Sorun giderme JSON: POST /api/report/troubleshooting, oku GET /troubleshooting
- Devir ZIP: POST /api/report/troubleshooting-zip, indir GET /troubleshooting.zip

Masaüstü analiz/durum raporlarını yerelde reports klasöründe üretir. analysis_report.py yüklemeyi önce WORKER_BASE_URL üzerinden Cloudflare Worker'a doğrudan yapar; bu yol başarısız olursa aynı rapor gövdesini RELAY_BASE_URL üzerinden Render'a gönderir ve Render Cloudflare'a aktarır. Okuma URL'leri WORKER_BASE_URL / READ_URL üzerinden doğrudan Worker'a gider. Her iki yükleme yolu Bearer token ile kimlik doğrular. Render'daki REPORT_RELAY_TOKEN ve Cloudflare Worker'daki CLOUDFLARE_REPORT_TOKEN ayrı sunucu tarafı gizli ayarlardır; değerler koda, README'ye veya masaüstü ZIP'ine yazılmaz. Raporlara gizli bilgi konmaz.

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

Güçlü fırsat kapısının mevcut başlangıç koşulları korunur: en az 80/100 puan, uygun B/C aşaması, güncel ve yeterli veri, başarılı likidite kontrolleri, geçerli teknik plan, BTC risk kapısı ve ilk teknik hedefte en az 1,5 brüt teknik risk/getiri. Eşikler sessizce değiştirilmez. 136. karar uyarınca tasarımda sabit %0,14 giriş ve %0,14 çıkış komisyonuyla tahmini maliyet sonrası risk/getiri hesaplamak onaylanmıştır; ancak mevcut kod bu hesabı uygulamıyor. Kod ve testler tamamlanana kadar maliyet sonrası hesap uygulanmış özellik gibi gösterilmez. Teknik hedef, matematiksel 1R/2R/3R projeksiyonundan ayrıdır ve emir değildir.

### Kabul edilmiş panel tasarımı

- Üst bölüm: motor/veri durumu, BTC ana yönü, genel piyasa riski, önemli destek/direnç, kanal ve veri tazeliği.
- Aday listesi: Coin, Binance/BtcTurk USDT fiyatları, 24 saatlik fiyat değişimi, puan ve A/B/C aşaması, zaman dilimi ve veri tazeliği, BTC'ye göre göreceli güç, hacim, öne çıkma nedeni ve işlem planı durumu. Mevcut alanlar korunur; genişlik yetmezse yatay kaydırma kullanılabilir.
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
**Tasarım durumu:** 1–145 arasındaki 145 karar kaydı tutuluyor. 142–145. kararlar 29 Ekim 2026'da onaylanıp bu deftere işlendi. 136. kararın maliyet kapsamı aynı gün kullanıcının açık onayıyla revize edildi; eski “maliyet hesabı kapsam dışı” hükmü artık geçerli değildir.  
**Sonraki tasarım kararı:** 146. karar.  
**Kayıt kapsamı denetimi — 29 Ekim 2026:** Önceden mevcut 1–141 karar ile yeni eklenen 142–145 kararları birleştirilerek toplam 145 numaralı karar kaydı tutuluyor. Yeni sıradaki madde 146'dır.  
**Kodlama durumu:** Başlanmayacak; bütün tasarım kararları tamamlanana ve gerekli açık onaylar verilene kadar beklemede.

### Bağlayıcı yol haritası

1. **Tasarım kararlarını bitir:** 146. maddeden devam et. Küçük ve ayrıntılı tasarım seçimlerini asistan, kesinleşmiş kararları değiştirmeden birleştirsin; çalışma mantığını/kapsamını etkileyen önemli seçimler kullanıcıyla tek tek netleştirilsin. Kesinleşmiş kararlar yeniden sorulmasın. Tasarımın bitmesi tek başına kodlama izni değildir; kodlama için ayrıca açık onay gerekir.
2. **Her 10 yeni kesinleşmiş kararda kayıt al:** Kullanıcının son talimatı geçerlidir. Her 10 yeni onaylı karar tamamlandığında aynı README güncellenecek ve değişiklik geri okunarak doğrulanacak. Önceden kesinleşmiş kararlar sessizce değiştirilmez; açıkça revize edilen kararın nedeni kaydedilir.
3. **Sürüm 1'i mevcut program üzerinden hazırla:** Tasarım kararlarının tamamı bittikten sonra, mevcut GitHub main dalındaki programı incele. Mevcut işlevleri, dosyaları, yapılandırmaları ve testleri doğrula; eksikleri gider ve gerekli testleri çalıştır.
4. **Sürüm 1'i kullanıcı testinden geçir:** Tam ve doğrulanmış sürüm adayı kullanıcının Windows bilgisayarında kontrol edilecek. Kullanıcının bulguları düzeltilip ilgili testler tekrarlanacak. Kullanıcının son onayı gelmeden Sürüm 1 kabul edilmeyecek.
5. **Sürüm 1'i sabitle, Sürüm 2'yi ondan üret:** Sürüm 1 kabul edilip sabitlendikten sonra değiştirilmeden korunacak. Yeni tasarım kararları, Sürüm 1'in eksiksiz kopyası yeni dala aktarılıp, temel alınarak yeni dalda Sürüm 2 olarak geliştirilecek. Mevcut ve çalışan işlevler gereksiz yere yeniden yazılmayacak; yeni işlevler gerçek programa ve arayüze entegre edilecek.
6. **Eksik sürüm teslim etme:** Kullanıcıya ara çalışma veya eksik ZIP verilmeyecek. Sürümün tüm işlevleri koda uygulandıktan, ilgili testler ve son tam doğrulama geçtikten sonra tam paket hazırlanacak. Kullanıcının son test ve sürüm kabulü tamamlanmadan bir sonraki sürüme geçilmeyecek.
7. **Hesap bağlantısı ve otomatik emir yok:** Program borsa hesabına bağlanmayacak, bu herzaman göz önünde bulundurularak geliştirmeler yapılacak, kullanıcının gerçek işlemlerini izlemeyecek ve otomatik emir göndermeyecek. Başarı raporları radarın ve önerilen teknik işlem planlarının fiyat hareketine göre değerlendirilmesini kapsayacak.



#### KESİNLEŞEN 1–20. TASARIM KARARLARI

**1. Takip kapasitesi:** Erken adaylar ve işlem planı hazır pariteler birlikte takip edilecek. Aynı anda 4–5 aktif takip paritesi olacak; arka planda daha fazla parite taranabilecek.

**2. Uyarılar:** Erken adaylarda görsel bildirim, güçlü fırsat koşulları doğrulandığında belirgin sesli uyarı, takip seviyeleri için ayrı bildirimler ve veri/bağlantı sorunları için ayrı ikazlar. Aynı koşul sürerken gereksiz tekrar olmayacak. Ekranın kenarındaki tıklanabilir bildirime basıldığında ayrıntılar açılacak, kullanıcı başka sayfaya zorla geçirilmeyecek.

**3. Aktif takip listesi:** Program en güçlü 4–5 pariteyi önerecek. Ekleme ve çıkarma kararını kullanıcı verecek.

**4. İşlem planı değişiklikleri:** Eski plan korunacak, yeni plan ayrı önerilecek. Eski plan geçersizleştiğinde bu açıkça bildirilecek. Yeni plan ancak kullanıcının onayıyla aktif olacak.

**5. Aktif takip ekranı:** 4–5 özet kartı gösterilecek. Parite seçildiğinde ayrıntılı analiz ve işlem planı açılacak.

**6. Gezinme düzeni:** Ana bölümler solda sabit menüde bulunacak. Gerekirse sayfaların içinde alt sekmeler kullanılacak.

**7. Sekiz ana bölüm:**
1. Genel Bakış
2. Fırsat Radarı
3. Aktif Takip
4. Parite Analizi
5. BTC ve Piyasa
6. Planlar ve Uyarılar
7. Raporlar
8. Sistem ve Ayarlar

**8. Genel Bakış:** Önce dikkat gerektiren uyarılar ve güçlü fırsatlar, ardından piyasa durumu, veri bağlantısı ve tarama özeti gösterilecek.

**9. Fırsat Radarı:** Kompakt tablo ve aynı sayfada açılan ayrıntı alanı.

**10. Sıralama ve filtreler:** Güçlü fırsatlar ve işlem planı hazır pariteler üstte, güçlenen adaylar ortada, erken adaylar aşağıda. Durum filtresi ve parite araması bulunacak; bütün adaylara erişim korunacak.

**11. Radar tablosu alanları:** Parite, aday durumu, fiyat değişimi, hacim, Bitcoin'e (BTC) göre güç, öne çıkma nedeni ve işlem planı durumu.

**12. Ayrıntı paneli:** Tablonun sağında açılacak.

**13. Genişlik ayarı:** Tablo ve ayrıntı alanı arasındaki ayırıcı sürüklenerek ayarlanabilecek.

**14. Ayrıntı sıralaması:** Önce genel özet, sonra işlem planı ve teknik analiz bilgileri.

**15. Ayrıntı sekmeleri:** İşlem Planı, Teknik Analiz ve Grafik.

**16. Varsayılan sekme:** Parite seçildiğinde Teknik Analiz açılacak.

**17. Teknik analiz grupları:** Fiyat yapısı ve trend; göstergeler ve hacim; Fibonacci, destek ve direnç; BTC ilişkisi ve zaman dilimleri. Gruplar açılıp kapatılabilecek.

**18. Grafik:** Gerçek piyasa verisiyle çalışan fiyat grafiği; temel zaman dilimi seçimi, hacim ve gereken göstergeler. Göstergeler ayrı panellerde gösterilebilecek.

**19. Grafik katmanları:** Giriş/hedef/zarar-kes, plan geçersizliği, Fibonacci, destek/direnç ve trend çizgileri/kanallar ayrı ayrı açılıp kapatılabilecek.

**20. Temel grafik araçları:** Mum bilgileri, zaman dilimi seçimi, hacim, yakınlaştırma ve kaydırma. Kullanıcı kendi trend çizgisini ve paralel kanalını çizebilecek. Gelişmiş ve gereksiz çizim araçları ilk aşamada geliştirilmeyecek.

#### KESİNLEŞEN 21–31. TASARIM KARARLARI

**21. Bildirim ayrıntısının konumu:** Bildirime tıklanınca ayrıntı paneli sağ tarafta açılacak.

**22. Panelin açılma biçimi:** Panel mevcut sayfanın üzerine açılacak. Ana sayfanın genişliği ve düzeni değişmeyecek.

**23. Panelin kapatılması:** Yalnızca panelin sağ üstündeki X işaretiyle kapatılacak. Dışarıya tıklayarak veya Esc tuşuyla kapatma olmayacak.

**24. BtcTurk PRO çalışma alanı:** Sol menüye ayrıca BtcTurk PRO sayfası eklenecek. Binance Fırsat Radarı aynen korunacak; mevcut sekiz ana bölümün düzeni bozulmayacak.

**Binance ve BtcTurk PRO arasındaki görev dağılımı:**
- Binance: Fırsat tarama, aday sıralama ve coin seçimi.
- BtcTurk PRO: Seçilen coin için işlem yapılabilirliğini inceleme ve giriş, hedef, zarar-kes, geçersizlik seviyelerini hesaplama.
- Ortak analiz altyapısı hedefleniyor. Ayrı motor gerekip gerekmediği mevcut kod yapısı incelenmeden kesinleştirilmeyecek.
- Her borsanın kendi verileri kullanılacak. BtcTurk tarafında fiyat hassasiyeti, emir miktarı sınırları, alış-satış farkı, emir defteri ve işlem maliyetleri dikkate alınacak.

**25. Coin aktarımı:** Hem Binance'ten tek tıkla BtcTurk PRO'ya aktarım hem de BtcTurk PRO içinde bağımsız parite araması olacak.

**26. BtcTurk PRO açılışı:** Sayfaya doğrudan girildiğinde en son incelenen paritenin ayrıntı ekranı açılacak. Binance'ten coin aktarılırsa aktarılan coin otomatik seçilecek.

**27. BtcTurk'te uygun USDT paritesi bulunamazsa:** Uyarı gösterilecek; coin seçili kalacak, işlem planı hesaplanmayacak ve başka bir USDT paritesi arama seçeneği sunulacak.

**28. Binance verilerinin gösterimi:** BtcTurk PRO'da Binance fiyatı ve fiyat değişimi ayrı, küçük bir karşılaştırma alanında gösterilecek. İşlem hesabında BtcTurk verileri kullanılacak.

**29. İşlem uygunluğu:** Paritenin üst bölümünde işlem durumu gösterilecek: “İşlem yapılabilir”, “Dikkat” veya “İşlem planı oluşturulamaz”. Alış-satış farkı, emir defteri derinliği, minimum emir şartları ve maliyetler aşağıdaki ayrıntılarda incelenebilecek.

**30. Güncel olmayan BtcTurk verisi:** Uyarı gösterilecek, ancak taslak işlem planı incelenebilecek. Güncel veri geldiğinde kontrol yeniden yapılacak.

**31. Veri zamanı:** Son veri zamanı ile güncellik uyarısı birlikte gösterilecek.

#### 1–31. kararlarla birlikte verilen ortak Binance ve BtcTurk kuralları

- Kullanıcı Binance'i fırsat bulmak ve coin seçmek için kullanıyor.
- Gerçek giriş ve çıkış kararları BtcTurk PRO verilerine göre hazırlanacak.
- İşlem paritelerinde USDT kullanılacak; TL pariteleri tercih edilmiyor.
- Binance fiyatı ile BtcTurk fiyatı aynı kabul edilmeyecek.
- BtcTurk'te uygun USDT paritesi yoksa uygulanabilir işlem planı oluşturulmayacak.
- Binance ve BtcTurk verilerinin kaynağı arayüzde açıkça ayırt edilecek.
- BtcTurk sayfasının ortak analiz motorunu kullanması hedefleniyor; teknik gereklilik kod yapısı incelendiğinde değerlendirilecek.


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
- Bu defter tasarım gereksinimlerinin kaydıdır; 
## Güncel tasarım kararları ve devir noktası — 29 Ekim 2026

**Güncel durum:** 1–145 arası tasarım kararları tamamlandı. 142–145 kararları bu sohbette onaylanıp kayda işlendi. Sıradaki tasarım maddesi 146'dır.

### 101–122. karar aralığı — kaynak durumu ve karar metinleri

**Kayıt doğruluğu notu:** 101–112 için kullanıcının sağladığı ayrıntılı metinler korunuyor. Kullanıcı 29 Ekim 2026'da 113. kararın ayrıntılı metnini yeniden sağladı ve onayladı; aşağıda kayıtlıdır. Aynı gün 114–119 kararlarının ayrıntılı metinleri de sağlandı ve önceki özet kayıtlarının yerine işlendi. 120–122 için daha önce sağlanan ayrıntılı karar metinleri korunuyor.

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
- **113. Kâr hedefinin tekrar aşılması — kullanıcı tarafından 29 Ekim 2026'da yeniden sağlanıp onaylanan ayrıntılı karar:** Her kâr hedefi, aynı işlem planı içinde ilk kez doğrulandığı anda gerçekleşmiş olarak kaydedilecek. Fiyat daha sonra aynı hedefin altına düşüp yeniden üzerine çıksa bile bu durum ikinci bir hedef başarısı sayılmayacak. İlk gerçekleşme zamanı ve fiyatı korunacak. Böylece aynı hedefin tekrar tekrar aşılması, raporlardaki başarı sayısını yapay biçimde artırmayacak. Bu kural, 107, 111 ve 112. kararlarla birlikte uygulanacak. Her hedef ayrı izlenecek; daha önce kazanılmış hedef başarıları korunacak ve sonraki olaylar ayrıca kaydedilecek.
- **114. Hedefe ulaşma koşulu — kullanıcı tarafından sağlanan ayrıntılı karar metni:** Kâr hedefi, fiyatın hedef seviyesine ulaşması veya bu seviyeyi aşmasıyla gerçekleşmiş sayılacak. Mumun hedef fiyatının üzerinde kapanması gerekmeyecek. Aynı mum içinde hedef ve zarar durdurma seviyeleri görülürse, gerçekleşme sırasını belirlemek için 102. karar uygulanacak. Hedefe temas veya aşım tek başına gerçek bir emir gerçekleştiği anlamına gelmeyecek.
- **115. Hedef fiyat ile gözlemlenen fiyatın kaydı — kullanıcı tarafından sağlanan ayrıntılı karar metni:** Kâr hedefi gerçekleştiğinde iki ayrı değer kaydedilecek: planlanan hedef fiyatı, yani işlem planında belirlenen hedef seviyesi; ve gözlemlenen fiyat, yani hedefin aşıldığı mumda görülen en yüksek veya en düşük fiyat. Gözlemlenen fiyat, gerçekleşmiş bir alım-satım fiyatı olarak gösterilmeyecek. Program emir göndermediği için yalnızca piyasa fiyatının hedefe ulaştığı doğrulanmış olacak. Bu ayrım, hedef başarısının gerçek işlem gerçekleşmesiyle karıştırılmasını önleyecek.
- **116. Hedef gerçekleşmesinin veriyle doğrulanması — kullanıcı tarafından sağlanan ayrıntılı karar metni:** Kâr hedefi, ilgili fiyat verisinin geçerli ve yeterli olması hâlinde gerçekleşmiş sayılacak. Fiyat verisi eksikse, bozuksa veya hedefe ulaşıldığını doğrulamaya yetmiyorsa hedef başarısı kaydedilmeyecek; sonuç Belirsiz olarak işaretlenecek. Eksik veri başarı veya başarısızlık oranına katılmayacak ve nedeni raporda belirtilecek. Bu kural, 102 ve 105. kararlarla uyumlu biçimde uygulanacak. Mevcut kararlar değiştirilmeyecek; kodlamaya başlanmayacak.
- **117. Olay zamanının kaydedilmesi — kullanıcı tarafından sağlanan ayrıntılı karar metni:** Kâr hedefi, zarar durdurma veya geçersizleşme olayı kaydedilirken, olayın doğrulandığı en küçük güvenilir zaman dilimi esas alınacak. Daha kısa zaman dilimindeki veriler olayı doğruluyorsa o veriler kullanılacak. Olayın tam gerçekleşme saniyesi belirlenemiyorsa kesin bir saat uydurulmayacak; ilgili mumun zaman aralığı ve kullanılan zaman dilimi kaydedilecek. Böylece raporlarda olay zamanı ile zamanın kesinlik düzeyi birbirinden ayrılacak.
- **118. Fiyatın hedef seviyesini boşlukla aşması — kullanıcı tarafından sağlanan ayrıntılı karar metni:** Fiyat hedef seviyesine işlem gerçekleştiği gözlemlenmeden, bir sonraki gözlemlenen fiyat doğrudan hedefin ötesinde olacak şekilde sıçrarsa hedefe ulaşılmış sayılacak. Ancak program, hedef fiyatından gerçekten işlem yapılmış gibi kayıt tutmayacak. Planlanan hedef fiyatı, gözlemlenen fiyat ve doğrulama zamanı ayrı saklanacak. Bu kural yalnızca fiyat verisi hedefin aşıldığını güvenilir biçimde doğruladığında uygulanacak. Böylece hedef başarısı kaydedilirken gerçekleşmiş emir varmış izlenimi oluşturulmayacak.
- **119. Fiyat hassasiyeti ve yuvarlama — kullanıcı tarafından sağlanan ayrıntılı karar metni:** Hedef, giriş ve zarar durdurma seviyelerinin karşılaştırılmasında mümkün olan en yüksek mevcut fiyat hassasiyeti kullanılacak. Ekranda gösterilen yuvarlanmış fiyatlar, gerçekleşme kararını belirlemeyecek. Böylece görüntüleme amacıyla yapılan yuvarlamalar nedeniyle hedef veya zarar durdurma yanlışlıkla gerçekleşmiş ya da gerçekleşmemiş sayılmayacak.
- **120. Yinelenen olay kayıtlarının önlenmesi — kullanıcı tarafından sağlanan karar metni:** Aynı kâr hedefi, zarar durdurma veya geçersizleşme olayı veri akışının tekrarlanması ya da sistemin yeniden başlaması nedeniyle birden fazla kez kaydedilmeyecek. Program, olayları ilgili işlem planı, hedef ve olay türü üzerinden ayırt edecek. Daha önce kaydedilmiş aynı olay yeniden geldiğinde mevcut kayıt korunacak; başarı sayısı ve raporlar ikinci kez artırılmayacak.
- **121. Sonradan gelen veri düzeltmeleri — kullanıcı tarafından sağlanan karar metni:** Daha sonra gelen güvenilir piyasa verileri önceki bir olay kaydını değiştiriyorsa, program eski kaydı sessizce silmeyecek veya üzerine yazmayacak. Düzeltilmiş sonuç yeniden değerlendirilecek; önceki kayıt, yeni sonuç, düzeltme nedeni ve doğrulama zamanı korunacak. Performans raporlarında en son doğrulanmış sonuç esas alınacak.
- **122. Düzeltilen verilerin raporlara yansıması — kullanıcı tarafından sağlanan karar metni:** Bir olayın sonucu sonradan düzeltildiğinde, bu değişiklikten etkilenen başarı oranları, toplam ölçümler ve ilgili grafikler en son doğrulanmış sonuçlara göre yeniden hesaplanacak. Daha önce oluşturulmuş raporların geçmiş sürümleri korunacak. Böylece güncel sonuçlar doğru hesaplanırken önceki raporlarla aradaki fark da izlenebilecek.


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

### Kesinleşmiş kararlar: 133–145

- **133. Sinyal başarısının ölçülmesi:** Aynı fiyat geçmişi üzerinden iki ayrı değerlendirme yapılır. **Radar başarısı:** Yükselişin ne kadar erken tespit edildiği, dönem içindeki en yüksek yükseliş ve en büyük düşüş. **Teknik plan başarısı:** Giriş, hedefler, zarar durdurma ve geçersizleşme koşullarının gerçekleşmesi. Aynı fiyat verisi iki ayrı sistemde yeniden toplanmaz.
- **134. Birden fazla hedefin ölçülmesi:** Her hedefin durumu ayrı değerlendirilir. Hangi hedeflere ulaşıldığı ve en yüksek ulaşılan hedef, gerçekleşen olay kayıtlarından türetilir. Aynı bilgi için ikinci bir olay kaydı oluşturulmaz.
- **135. Sonuçların sınıflandırılması:** Hedefe ulaşma, zarar durdurma, geçersizleşme, sürenin dolması, girişin gerçekleşmemesi ve belirsizlik değerlendirilir. Birden fazla olay gerçekleşebileceğinden yalnızca tek sonuç etiketiyle yetinilmez. Olayların sırası korunur. Sıra güvenilir biçimde belirlenemiyorsa tahmin yürütülmez; sonuç belirsiz kaydedilir.
- **136. Maliyet sonrası teknik risk/getiri tahmini — 29 Ekim 2026'da kullanıcının açık onayıyla revize edildi:** İşlem planındaki giriş fiyatı temel alınır; her kâr hedefi ve zarar-kes çıkışı ayrı değerlendirilir. Komisyon varsayımı sabittir: girişte %0,14 ve çıkışta %0,14. Aynı tutarlı giriş ve çıkışta bu yaklaşık %0,28 toplam komisyon demektir; hacim kademesi veya emir türüne göre oran değiştirilmez. Brüt risk/getiri ile tahmini maliyet sonrası net risk/getiri ayrı gösterilir. Fiyat kayması yalnızca BtcTurk alış-satış farkı/emir defteri verisi yeterliyse tahmin edilir; veri yoksa oran uydurulmaz, eksik olduğu açıkça gösterilir. Bu hesap tahmindir; gerçek emir, dolum, tahsil edilmiş komisyon veya gerçek işlem kârı değildir. Program otomatik emir göndermez. Eski “komisyon/kayma hesabı kapsam dışı” hükmü bu revizyonla geçersizdir.
- **137. Teknik planın başarı koşulu:** Bir planın hedef başarısı sayılabilmesi için giriş koşulu gerçekleşmiş olmalıdır. Giriş gerçekleşmeden hedefe ulaşılması radarın fiyat hareketini tespit başarısına yazılır; teknik planın hedef başarısı sayılmaz. Giriş gerçekleşmişse hedef, zarar durdurma ve geçersizleşme olayları değerlendirilir. Giriş gerçekleşmezse plan, gerçekleşmiş işlem gibi başarılı veya başarısız sayılmaz. Olay sırası güvenilir biçimde belirlenemiyorsa sonuç belirsizdir.
- **138. Giriş koşulunun belirlenmesi:** Sinyalden sonraki kapanmış ve güvenilir mumun en düşük ve en yüksek fiyatı giriş bölgesiyle kesişirse giriş bölgesine temas kaydedilir. Teknik plan ayrıca kapanış, kırılım veya başka bir teyit koşulu gerektiriyorsa giriş ancak bu koşul gerçekleştiğinde doğrulanır. Ek teyit yoksa bölgeye temas yeterlidir. Geçmiş plan koşulları sonradan değiştirilerek eski sonuçlar yeniden yazılmaz. Aynı mumda giriş, hedef veya zarar durdurma olaylarının sırası belirlenemiyorsa tahmin yapılmaz.
- **139. Giriş öncesinde geçersizleşme:** Giriş gerçekleşmeden geçersizleşme koşulu oluşursa plan **“Giriş öncesi geçersizleşti”** olarak kaydedilir. Gerçekleşmiş işlem zararı sayılmaz. Radarın fiyat hareketini tespit başarısı ölçülmeye devam eder. Teknik planın geçersizleşmesi, 1 saatlik, 4 saatlik ve 24 saatlik radar ölçümlerini sonlandırmaz.
- **140. Hedefe ulaşıldığında zarar durdurma seviyesi:** Başlangıçta belirlenen hedefler ve zarar durdurma seviyesi sabit kalır. Bir hedefe ulaşılması zarar durdurma seviyesini kendiliğinden değiştirmez. Seviyeyi değiştiren bir kural varsa önceden belirlenmiş olmalıdır. Geçmiş plan koşulları sonradan oluşan fiyat hareketlerine göre geriye dönük değiştirilmez. Hedef ve zarar durdurma temasları ortak fiyat verisinden değerlendirilir.
- **141. Radar ölçümünün başlangıç fiyatı — kesinleşti:** 1 saatlik, 4 saatlik ve 24 saatlik sinyal sonrası radar ölçümlerinde başlangıç fiyatı, sinyali oluşturan kapanmış mumun kapanış fiyatıdır. Veri gecikmesi nedeniyle daha sonraki bir fiyat başlangıç referansı yapılmaz. Bu karar, **81–82. kararlardaki erken/geç/kaçırılan yükseliş sınıflandırması için kullanılan izleme başlangıcı fiyatını değiştirmez**; iki referans farklı ölçüm amaçlarına aittir. Geçmiş ölçümlerin başlangıç fiyatı sonradan değiştirilmez.

### Kesinleşmiş kararlar: 142–145

- **142. BtcTurk PRO'nun ana menü konumu:** BtcTurk PRO, sol ana menüde diğer çalışma alanlarından ayrı, doğrudan seçilebilir bir madde olacak. Daha önce çizilen sekiz bölümlü menü listesi kesinleşmiş nihai isim/sıra listesi sayılmayacak; içerik ve sıralama ekranların bütün tasarımıyla uyumlu biçimde kapatılacak. BtcTurk PRO'nun ayrı madde olması kesinleşmiştir.
- **143. Ortak pencere iskeleti:** Tek pencerenin solunda sabit ana gezinme menüsü, üstte ortak durum satırı ve ortak işlem kontrolleri, ortada seçilen bölümün çalışma alanı bulunacak. Mevcut çalışan işlevler ve düğmeler kaldırılmayacak; yerleri, ihtiyaç halinde sayfa bazında daha düzenli sunulacak. Bu karar kodun uygulandığını göstermez.
- **144. Genel Bakış ekranı:** Mevcut üst durum satırı ve işlem kontrolleri korunacak. Genel Bakış içinde piyasa durumu/önemli fırsatlar ve aday tablosu merkezde; seçili coin ayrıntısı sağda; tanılama ve son kayıtlar altta, gerektiğinde daraltılabilir biçimde sunulacak. Mevcut BTC ayrıntısı, motor başlatma/durdurma, parite güncelleme, rapor, sorun giderme ZIP'i, seviye takibi, sesli bildirim/ses testi/ses düzeyi, yazı boyutu ve ekran görüntüsü yükleme işlevleri kaybolmayacak. Bildirim ayrıntısı, önceki karara göre sayfa üzerine sağdan açılır. Taslak görsellerdeki örnek fiyatlar gerçek piyasa verisi değildir.
- **145. Fırsat Radarı tablosu:** Mevcut sütunlar ve karar bilgisi korunarak şu alanlar tek tabloda sunulacak; genişlik yetmezse yatay kaydırma kullanılacak: Coin; Binance USDT fiyatı; BtcTurk USDT fiyatı; 24 saatlik fiyat değişimi; puan ve A/B/C aşaması; zaman dilimi ve veri tazeliği; BTC'ye göre göreceli güç; hacim; öne çıkma nedeni; işlem planı durumu. Mevcut tablonun dokuz sütunlu test sözleşmesi şu anki kod/test durumudur; yeni tasarımın tam uygulandığı anlamına gelmez. Gerekli kod/test uyumu ileride ayrıca onaylanan kodlama aşamasında yapılacak.

### Kesinleşmiş tasarım kararları: 146–153

- **146. Aktif Takip ekranı ve kartları:** Seçilen 4–5 Binance USDT paritesi iki sütunlu kart düzeninde gösterilecek. Kullanıcı parite ekleyip çıkarabilecek, sıralamayı değiştirebilecek ve ayrıntıya geçebilecek.
- **147. Parite Analizi ve grafik ekranı:** Büyük fiyat grafiği solda; analiz ayrıntıları sağda olacak. Göstergeler, zaman dilimleri, giriş/hedef/stop, Fibonacci, destek/direnç ve ilgili plan bilgileri grafikle birlikte değerlendirilecek. Bu tasarım hedefidir; kodda uygulanmış olduğu anlamına gelmez.
- **148. BTC ve Piyasa ekranı:** Öncelik BTC durumu, BTC Dominance ve piyasa genişliği göstergelerinde olacak. TOTAL/TOTAL2/TOTAL3 ancak güvenilir veri kaynakları doğrulanırsa eklenecek.
- **149. Planlar ve Uyarılar ekranı:** Tek ekranda aktif/yeni/tamamlanmış/geçersiz planlar ile uyarı geçmişi filtrelenebilecek. Seçilen kayıtların ayrıntısı sağdan açılacak.
- **150. Raporlar ekranı:** Tek Raporlar ekranında iki ayrı bölüm bulunacak: radarın erken tespit performansı ve teknik işlem planı sonuçları. Dönem/coin/borsa filtreleri olacak; brüt ve tahmini net risk/getiri ayrı gösterilecek.
- **151. Sistem ve Ayarlar ekranı:** Tek ekran, sistem/veri durumu, analiz ayarları, uyarılar ve görünüm gibi net bölümlere ayrılacak. Mevcut çalışan kontroller korunacak. Gelecekteki ayar değişiklikleri geçmiş ölçümlerin koşullarını geriye dönük değiştirmeyecek.
- **152. BtcTurk PRO ekranı:** BtcTurk PRO tek bir çalışma alanında sunulacak. Binance keşif ve sıralama motoru olarak kalacak; seçilen aday için BtcTurk PRO verileriyle ayrı teknik değerlendirme/plan oluşturulacak. BtcTurk fiyatı, mumları ve yeterli olduğunda emir defteri/spread verileri kullanılacak. Binance ve BtcTurk fiyatları birbirine karıştırılmayacak; eksik veri açıkça belirtilecek.

- **153. Naratif Avcısı:** Hem teknik radarın bulduğu adayları naratif verisiyle destekleyecek hem de naratifin önce öne çıkardığı coinleri erken izlemeye taşıyacak. Naratif puanı teknik puandan ayrı kalacak; güçlü alarm mevcut teknik fırsat koşullarını karşılayan adaylar için üretilecek.

### 153. Naratif Avcısı — tamamlanmış tasarım maddesi

**Amaç:** Naratif Avcısı, piyasanın hangi temalara yöneldiğini erken fark etmeye ve teknik göstergeler henüz fırsatı yakalamamışken de coinleri erken takibe almaya yardımcı olacak. Ayrı bir işlem karar sistemi değil; mevcut Fırsat Radarı, Parite Analizi ve Analiz Raporu ile bağlantılı bir keşif ve destek katmanı olarak tasarlanacak. Kodlama başlamadı; bu bölüm kabul edilmiş tasarım hedeflerini kaydeder.

#### Kesinleşmiş alt kararlar: 153.1–153.11

- **153.1 — Binance aday sıralaması:** Ayrı Naratif Puanı ve naratif aşaması etiketi kullanılacak. Naratif sinyali adayların erken takip/sıralama önceliğini etkileyebilecek; mevcut 100 puanlık teknik skor ve güçlü fırsat koşulları değişmeyecek. Etkisi ileride ölçülecek.
- **153.2 — Tarama sıklığı:** Kaynağa göre otomatik tarama yapılacak. Güncellenme hızı ve erişim sınırları farklı olan kaynaklar farklı aralıklarla sorgulanacak; gereksiz tekrarlar önbellekle azaltılacak.
- **153.3 — Kaynak arızası:** Bir kaynak çalışmazsa tüm akış durmayacak. Uygun yedek devreye girecek, kalan kaynaklar çalışmayı sürdürecek ve eksik veri durumu gizlenmeyecek.
- **153.4 — Başlangıç kaynakları:** AIXBT'nin erişilebilir ücretsiz konu verisi, CoinGecko Demo API, DEX Screener'ın herkese açık API'leri, ücretsiz RSS/Atom haber akışları ve proje/borsaların resmî duyuruları başlangıçta değerlendirilecek. CoinMarketCap'in ücretsiz API uçları ikincil piyasa kaynağı olacak. Mevcut Binance piyasa verileri teknik doğrulamada kullanılacak. X, Reddit ve Santiment gibi ek kaynaklar ancak gerekli erişim ücretsiz ve izinli biçimde doğrulanırsa etkinleştirilecek. Ücretli servis veya API zorunlu olmayacak. Kaynaklar katı ve değişmez bağımlılıklar değildir; yeni ücretsiz kaynaklar sonradan eklenebilir, erişilemeyenler akışı iptal ettirmez.
- **153.5 — Tek kaynaklı sinyal:** Tek kaynaktan bulunan naratif kaybedilmeyecek; erken izlemeye alınabilecek. Kaynak/güven durumu ve eksik doğrulama belirtilecek; ek kanıtlar geldikçe değerlendirme güncellenecek.
- **153.6 — Naratif Puanı:** Elde bulunan kanıtlar birleştirilecek: ilgi artış hızı, veri güncelliği, kaynak çeşitliliği, haber/katalizör, farklı projelere yayılma ve fiyat-hacim tepkisi. Bütün veriler her naratifte bulunmak zorunda değil; eksikler ve güven düzeyi gösterilecek.
- **153.7 — Yaşam evreleri:** Başlangıç, Yayılma, Güçlenme, Aşırı Isınma, Zayıflama ve Belirsiz etiketleri kullanılacak. Aşama eldeki kanıta göre atanacak.
- **153.8 — Geçmiş takibi:** Naratif puanı, aşaması, kaynakları ve ilişkili coinleri zaman içinde kaydedilecek. İlk görülme zamanı korunacak; ilgi değişimi önceki gözlemlerle karşılaştırılacak. Kaynağın geçmiş verisi yoksa takip ilk gözlemden itibaren başlayacak.
- **153.9 — Tarama kapsamı:** Ortak Binance–BtcTurk USDT evreninin tamamı coin odaklı taramaya dahil edilecek. Kaynak izin verirse toplu sorgu kullanılacak; haber akışları topluca alınıp içerikleri coin/proje adları ve bağlamıyla eşleştirilecek. Teknik motorun henüz öne çıkarmadığı coinler de kapsanacak.
- **153.10 — Coin eşleştirmesi:** Coin sembolü, adı, proje adı, alternatif adları ve içerik bağlamı birlikte değerlendirilecek. Şüpheli eşleşmeler silinmeyecek ama belirsiz işaretlenecek; kesin eşleşmelerle aynı güven düzeyinde gösterilmeyecek.
- **153.11 — Yinelenen haberler:** Aynı gelişme tek naratif olayı olarak birleştirilecek. Aynı haberi yeniden yayımlayan kaynaklar kaydedilebilecek ancak bağımsız doğrulama sayısını yapay olarak artırmayacak.

#### Kesinleşmiş alt kararlar: 153.12–153.15

- **153.12 — Ana kart ve ayrıntı görünümü:** Naratif Avcısı ana listesinde yalnızca naratif adı/aşaması, ilişkili coinler, ilgi değişimi ve güven/veri durumu gösterilecek. İlişkili coinler Binance ve BtcTurk PRO'nun ortak USDT parite evreninden eşleştirilecek. Karta tıklanınca kaynaklar, gelişmeler, gözlem tarihçesi ve piyasa tepkisi ayrıntıda açılacak.
- **153.13 — Sıralama:** Artan ilgi gösteren, eldeki kanıtlarla desteklenen ve henüz aşırı ısınmamış naratifler üst sıralarda değerlendirilecek. Veri eksiği olan naratifler gizlenmeyecek; eksik doğrulama ve güven durumu belirtilecek.
- **153.14 — Filtreleme:** Naratifler yaşam aşamalarına ve ilgi değişimine göre filtrelenebilecek.
- **153.15 — Bildirimler:** Yeni bir naratif tespit edildiğinde veya Yayılma ya da Güçlenme aşamasına geçtiğinde, neden öne çıktığını ve veri güven durumunu açıklayan bildirim oluşturulacak. Bu bildirim kendi başına güçlü fırsat alarmı veya alım sinyali olmayacak.

#### Bütünleşik çalışma: iki yönlü fırsat keşfi

1. **Teknik radar önce bulursa:** Teknik açıdan öne çıkan coinle eşleşen naratif bilgisi adayın gerekçesine eklenecek ve öncelik değerlendirmesini destekleyebilecek.
2. **Naratif önce bulursa:** Yeni bir gelişme veya artan ilgiyle öne çıkan coin, teknik puanı henüz yüksek olmasa veya güçlü teknik sinyal oluşmamış olsa bile erken izlemeye alınabilecek. Aday, teknik motorun sonraki değerlendirmelerinde takip önceliği kazanabilecek; teknik sinyal henüz oluşmadı diye kaybolmayacak.

Her iki yol aynı aday değerlendirmesinde birleşecek. Naratif puanı, mevcut 100 puanlık teknik puandan ayrı tutulacak; sıralama ve takip önceliğini etkileyebilecek, ancak teknik eşikleri, likidite kontrollerini veya güçlü fırsat koşullarını geçersiz kılamayacak. Naratif desteği tek başına güçlü alarm üretmeyecek. Güçlü alarm için mevcut güçlü fırsat koşullarının sağlanması gerekecek. Naratif bilgisi olmayan teknik adaylar da yalnızca bu nedenle otomatik olarak elenmeyecek.

#### Arayüz entegrasyonu

- **Naratif Avcısı:** Temayı keşfetmek ve izlemek için sade özet kartları ve tıklanınca açılan ayrıntılar.
- **Fırsat Radarı:** Bir adayın teknik nedenlerle mi, naratif kaynaklı erken izleme nedeniyle mi öne çıktığı açıkça anlaşılacak. Erken izleme durumu, güçlü fırsat alarmıyla karıştırılmayacak.
- **Parite Analizi:** Coin teknik olarak incelenirken naratif desteği de kısa bir alanda görünecek. Tema/aşama, ilgi yönü ve güven/veri durumu gösterilecek; kaynak ve gelişme ayrıntıları gerektiğinde açılacak. Böylece naratif bilgisi teknik incelemeden kopmayacak ama grafik alanını da kalabalıklaştırmayacak.
- **Analiz Raporu:** Naratif adı/aşaması, ilişkili coinler, ilk ve son gözlem zamanı, kaynak özeti/bağlantıları, ilgi değişimi, piyasa tepkisi ve eksik veri durumu ayrı bölümde yer alacak.
- **Geçmiş ve ölçüm:** Naratif puanı, aşaması, kaynakları ve ilişkili coinleri zaman içinde korunacak. Naratifin aday önceliğine katkısı ileride ölçülebilecek. Kaynağın geçmiş verisi yoksa kayıt ilk gözlemden başlayacak.
- **Basitlik:** Yeni bir ana arayüz veya bağımsız işlem sistemi eklenmeyecek. Mevcut sayfalar arasında gerekli bağlantılar kurulacak; ayrıntılar kullanıcı gerektiğinde açacak şekilde sunulacak.

Analiz Raporu'na naratif verisi eklemek, raporun kendiliğinden bu ChatGPT sohbetine mesaj göndermesi anlamına gelmez; doğrudan sohbet aktarımı ayrıca tasarlanmalıdır.

**153. tasarım kararı:** 153.1–153.15 onaylandı ve tasarım tamamlandı. Tasarımın kod karşılığı, kaynak kapsamı, testler ve henüz bağlı olmayan kaynaklar bu README'nin başındaki 31 Ekim güncel uygulama bölümünde ayrı ayrı kaydedilmiştir.


### 154. Tarihsel geri test ve ölçüm yöntemi — onaylandı

Bu madde, programın geçmişteki bir tarihte o an elinde bulunan verilerle nasıl karar vereceğini yeniden oynatıp, daha sonra gerçekleşen fiyat hareketleriyle karşılaştırarak gerçek tespit başarısını ölçmek için kabul edilmiştir. Bu bir tarihsel geri testtir; geçmiş grafiğe bugünkü bilgiyi taşıyarak değerlendirme yapmak değildir.

- Her test anında yalnızca o ana kadar gerçekten mevcut olan güvenilir kapanmış mumlar, göstergeler, piyasa/veri durumu ve o anda erişilebilir olmuş naratif kayıtları kullanılacak. Sonradan ortaya çıkan veri veya haber geçmişteki kararın girdisi olamayacak.
- O test anında oluşan adaylar, puanlar, A/B/C aşamaları, erken izlemeler, güçlü fırsat sinyalleri, öne çıkma nedenleri ve teknik plan seviyeleri kaydedilecek. Sonraki mumlar kronolojik sırayla ilerletilecek ve gerçek fiyat davranışıyla karşılaştırılacak.
- Radarın erken tespit başarısı ile teknik işlem planının sonucu ayrı raporlanacak. Radar için sinyal anından sonraki fiyat hareketi ve 1 saat/4 saat/24 saat ölçümleri; teknik plan için giriş koşulunun gerçekleşmesi, hedef, stop ve geçersizleşme olayları kullanılacak. Teknik plan hedef başarısı, giriş gerçekleşmeden yazılmayacak.
- Olayların sırası güvenilir biçimde belirlenemiyorsa sonuç tahmin edilmeyecek, belirsiz kaydedilecek. Güvenilir geçmiş mum verisi veya gerekli alanlar yoksa ilgili ölçüm “değerlendirilemedi” olarak işaretlenecek; otomatik olarak başarısız sayılmayacak.
- Sabit ve gerekçesiz bir geçmiş uzunluğu dayatılmayacak. Kullanılabilir güvenilir geçmişin kapsadığı dönem kullanılacak; yeterli örnek ve mümkün olduğunca farklı piyasa koşullarını temsil eden dönemler gözetilecek. Test, programın gerçek zamanlı kullandığı mum çözünürlüklerini ve karar mantığını geriye dönük taklit edecek.
- Naratifin geçmişteki etkisi yalnızca ilgili tarihte gerçekten erişilebilir naratif geçmişi varsa ölçülecek. Naratif geçmişinin bulunmaması, teknik radar veya teknik plan ölçümünü geçersiz kılmayacak.
- Radarın erken/geç tespiti, yakalanan ve kaçırılan yükselişler, sinyal sonrasındaki en yüksek yükseliş/en büyük düşüş ile teknik planın giriş, hedef, stop, geçersizleşme sonuçları ayrı gösterilecek. Brüt sonuçlar ve 136. kararda kabul edilen %0,14 giriş + %0,14 çıkış komisyon varsayımına göre tahmini maliyet sonrası sonuçlar birbirine karıştırılmayacak.

**154. maddenin durumu:** Kullanıcı onayladı. Bu madde tasarım ve değerlendirme yöntemini kesinleştirir; geri test motorunun kodlandığı veya ölçümlerin çalıştırıldığı anlamına gelmez.

#### Sıradaki tasarım maddeleri

- **154. Tarihsel geri test ve ölçüm yöntemi — onaylandı:** Geçmiş bir zaman noktasında program yalnızca o ana kadar gerçekten mevcut olan güvenilir verilerle yeniden çalıştırılacak. O anda oluşan adaylar, puanlar, A/B/C aşamaları, erken izlemeler, güçlü fırsat sinyalleri, gerekçeler ve teknik plan seviyeleri kaydedilecek; ardından sonraki mumlar zaman sırasıyla ilerletilip gerçek fiyat davranışıyla karşılaştırılacak. Geleceğe ait veri geçmişteki karara sızdırılmayacak. Elde bulunan güvenilir geçmiş verinin kapsadığı süre kullanılacak; yeterli veri ve farklı piyasa koşullarının temsil edilmesi gözetilecek, sabit ve gerekçesiz bir geçmiş süresi varsayılmayacak. Radarın erken tespit başarısı ile teknik işlem planının başarısı ayrı ölçülecek. Teknik planın hedef başarısı için giriş koşulunun gerçekleşmiş olması gerekecek; hedef, stop ve geçersizleşme olayları zaman sırasıyla değerlendirilecek. Olay sırası veya veri güvenilir biçimde belirlenemiyorsa sonuç belirsiz bırakılacak. Tarihsel naratif verisi yalnızca gerçekten mevcut olduğu dönemlerde değerlendirilecek; bulunmaması başarısızlık sayılmayacak. Brüt sonuçlar ile 136. kararındaki sabit komisyon varsayımına göre tahmini maliyet sonrası sonuçlar ayrı gösterilecek.
- **155. Bütün ekranların son tasarım tutarlılığı kontrolü:** Menü ve sayfa isimleri/sırası, ortak gezinme, mevcut düğme ve işlevlerin korunması, ekranlar arasındaki tutarlılık ve 1–155 gereksinimlerinin son kontrolü. Önceki çalışma listesindeki maliyet kapsamı çelişkisi 136. kararın revizyonuyla çözülmüştür; bu konu yeniden sorulmayacak.

146–155 tamamlanınca 1–155 tasarım gereksinimleri ile ana daldaki kod tekrar karşılaştırılacak, eksikler ve çelişkiler öncelik sırasına konacaktır. Kod uygulaması, test/dağıtım değişikliği ve ZIP hazırlığı için ayrı açık onay beklenecektir.

### Aynı sinyalin yeniden oluşması ve ortak kayıt ilkesi

- Önceki sinyalin 24 saatlik ölçümü devam ederken mevcut kayıt korunur.
- Aynı sinyalin tekrar bildirilmesi yeni ölçüm oluşturmaz.
- Gerçekten yeni bir sinyal oluşursa benzersiz kimliğiyle yeni ölçüm kaydı açılır.
- Önceki ve yeni ölçümler birbirini değiştirmeden sürer.
- 133–135. kararlar birlikte uygulanır: fiyat verisi ve olaylar ortak tutulur; farklı başarı ölçümleri bu kayıtlardan türetilir.

### Güncel devir noktası

- **Son tamamlanmış ana karar:** 154 — Tarihsel geri test ve ölçüm yöntemi.
- **Sıradaki ana karar:** 155 — Bütün ekranların son tasarım tutarlılığı kontrolü.
- **Tamamlanan 153 alt kararları:** 153.1–153.15.
- **Kesinleşen 154. madde:** Geçmiş veriyi o tarihte bilinebilen bilgilerle kronolojik olarak yeniden oynatma; radar başarısını teknik plan başarısından ayrı ölçme; eksik veri ve olay sırası belirsizliğini dürüstçe işaretleme.
- **Kodlama:** Ayrı ve açık kullanıcı onayı olmadan başlanmayacak.


- ** kural:** Karar defterinin tek yetkili kaynağı bu README'nin `main` dalındaki güncel sürümüdür; kullanıcıya danışmadan yazılacak metin kendisine sunulmadan buraya kayıt yapılamaz burda düzeltme yapılamaz.

- **Mevcut program durumu:** Tasarım kararlarında hedef olarak yazılması, ilgili işlevin programda mevcut veya test edilmiş olduğu kontrol edilir, inceleme ve doğrulamayla belirlenir kullanıcı onayıyla koda uygulanır.

Yeni sohbet 155. tasarım maddesinden devam etmelidir. 1–154 arasındaki kesinleşmiş tasarım kararları tekrar sorulmayacak.


---

## Güncel karar güncellemesi — 30 Ekim 2026

Bu bölüm, aşağıdaki 154. ve 155. maddelerin **en güncel durum kaydıdır**. Önceki bölümlerde sıradaki madde olarak yer alan 155 ifadesi, bu güncellemedeki tamamlanma durumuyla birlikte okunmalıdır.

### 154. Tarihsel geri test ve ölçüm yöntemi — tamamlandı ve onaylandı

Kullanıcı 154. maddeyi onaylamıştır. Tasarım kararı kesinleşmiştir ve yeniden sorulmayacaktır. Geçmiş test anında yalnızca o tarihte gerçekten erişilebilir veri kullanılacak; adaylar, sinyaller ve teknik plan seviyeleri kaydedilecek, sonraki mumlar kronolojik olarak ilerletilerek gerçek fiyat davranışıyla karşılaştırılacaktır. Radarın erken tespit başarısı ile teknik plan sonuçları ayrı ölçülecek; eksik veri veya belirsiz olay sırası uydurulmayacak.

154. maddenin ilk tasarım kaydında kodun henüz yazılmadığı belirtilmişti. **31 Ekim 2026 güncel uygulama durumu** aşağıdaki “154 uygulama durumu” bölümünde kayıtlıdır; bu eski cümle artık güncel kod durumunu tanımlamaz.

### 155. Bütün ekranların son tasarım tutarlılığı kontrolü — devam ediyor

155. madde henüz tamamlanmamıştır. Şu ana kadar geliştirme yöntemi ve iki motorun ana kontrollerle çalıştırılmasına ilişkin kararlar kesinleşmiştir. Menünün nihai ad ve sıralaması dahil bütün ekran tutarlılığı kontrolü tamamlanmış değildir.

#### 155 kapsamında kullanıcı tarafından onaylanan geliştirme yöntemi

1. Önce mevcut `main` dalındaki kaynak kodu ve testler salt okunur biçimde incelenir. İşlevler “mevcut karşılığı var”, “kısmen karşılanıyor”, “eksik”, “çelişkili” veya “doğrulanamadı” şeklinde sınıflandırılır.
2. Kritik çalışma aksaklıkları ve güvenilirliği etkileyen eksikler önem sırasına konur.
3. Kritik temel düzeltmelerden sonra yeni arayüz ve eksik motor işlevleri aşamalı olarak geliştirilir.
4. Her aşamada ilgili testler çalıştırılır; bu kontroller nihai bütünleşik testin yerini almaz.
5. Son aşamada ekranlar, motorlar, veri akışı, düğmeler ve paketlenmiş Windows programı birlikte doğrulanır.

Bu sıra onaylanmış geliştirme yöntemidir; kendi başına kod değişikliği yapma izni değildir.

#### 155 kapsamında Başlat/Durdur kararı — onaylandı

- **Başlat:** Teknik analiz motoru ile Naratif Avcısı birlikte başlatılacak.
- **Durdur:** Teknik analiz motoru ile Naratif Avcısı birlikte durdurulacak.
- Her motorun gerçek çalışma durumu ayrı ve anlaşılır biçimde izlenebilir olmalıdır.
- Bir motorun veya naratif kaynağının hata vermesi hâlinde diğer motorun davranışı, kontrollü durdurma ve hata bildirimi ayrıntıları güncel kod ve mimari incelendikten sonra netleştirilecektir; bunlar henüz ayrı bir kesin tasarım kararı değildir.

**30 Ekim 2026 tarihli önceki kod fotoğrafı:** O incelemede Başlat düğmesinin yalnızca teknik radarı yönettiği görülmüştü. Bu ifade 31 Ekim güncel uygulama kaydıyla geçersiz kalmıştır; mevcut kodda iki canlı motorun ortak Başlat/Durdur yönetimi eklenmiştir.

#### 155'in kalan işi

- Menü ve ekran isimleri/sırası ile ortak gezinme tutarlılığını kontrol etmek.
- Mevcut düğme, kontrol ve işlevlerin kaybolmamasını sağlamak.
- 1–155 arasındaki gereksinimlerde eksik veya çelişkili noktaları, kesinleşmiş kararları tekrar açmadan son kez gözden geçirmek.
- Önceki öneri olarak sunulan on ekranlık menü sırası kullanıcı tarafından onaylanmamıştır; nihai menü kararı olarak kaydedilmemiştir.

### Çalışma sınırı ve yeni başlangıç noktası

- Genel çalışma kuralı olarak kod, test, dağıtım ve paketleme değişikliklerinde gereken kullanıcı onayı korunur.
- 31 Ekim güncel uygulama kaydı: Kullanıcı Naratif Avcı'nın kodlanmasına, iki canlı motorun birlikte yönetilmesine ve bütünleşik testine bu sohbette açıkça izin verdi; bu kod çalışması bu izin kapsamında yapıldı.
- Tasarım hedefi, kaynakta mevcut davranış ve testle doğrulanmış davranış ayrı tutulur.
- 30 Ekim salt okunur inceleme başlangıç talimatı tamamlanmış tarihsel kayıttır; bu aşamadaki onaylı kod uygulamasının yerine geçmez.
### Bütünleşik arayüz ve motor doğrulaması — 30 Ekim 2026

- `tek_motor_paneli.pyw` çok sayfalı arayüz entegrasyonundan sonra mevcut otomatik doğrulama iş akışı yeniden çalıştırılacaktır.
- Bu kayıt yalnızca test tetikleme ve sonuç takibi içindir; ZIP oluşturma veya GitHub Release yayımlama izni vermez.
- Test kapsamı: Python kaynak derleme kontrolü, Python birim testleri, bulut geçidi ve rapor Worker testleri, Render geçidi testleri ve yapılandırılmış canlı bağlantı kontrolleri.

---

## Sürekli kod değişikliği kaydı ve 1–155 izleme kuralı — 31 Ekim 2026

Bu kural kullanıcı tarafından açıkça istenmiş ve onaylanmıştır. Takip ve README kayıt işlemleri için ayrıca onay istenmez.

### 155 dışında istenen kod değişiklikleri

- Kullanıcının 1–155 tasarım maddelerinin dışında ayrıca talep ettiği her kod değişikliği, 155. maddeye aitmiş gibi gösterilmeden ayrı kayıt olarak tutulur.
- Her kayıt; talebin ne olduğunu, **neden istendiğini**, etkilenen dosya/işlevleri, uygulama durumunu, yapılan testleri ve sonucunu, ilgili GitHub commit kimliğini ve README'ye kaydedilip kaydedilmediğini belirtir.
- Talep henüz uygulanmadıysa “talep edildi / uygulanmadı”; kod değişikliği yapıldıysa “uygulandı”; test edilmediyse “doğrulanmadı” olarak açıkça işaretlenir. Yalnızca README'ye yazılmış olması kodun uygulandığı anlamına gelmez.
- Yeni bir 155 dışı kod değişikliği yapıldığında gerekçesi ve sonucu bu bölümün altında ayrı bir kayıt olarak eklenir. Sonradan düzeltme yapılırsa önceki kayıt silinmez; durum ve yeni commit bilgisi güncellenir veya ek kayıtla izlenir.

### 1–155 maddelerinin sürekli durum takibi

Her madde birbirinden ayrı şu başlıklarda izlenir:

1. **Tasarım kararı:** Bekliyor, kullanıcı tarafından onaylandı veya tamamlandı.
2. **Kod karşılığı:** Mevcut, kısmen mevcut, eksik, çelişkili veya henüz doğrulanmadı.
3. **Uygulama:** Başlanmadı, sürüyor veya kodda uygulandı.
4. **Test/doğrulama:** Çalıştırılmadı, başarılı, başarısız veya değerlendirilemedi.
5. **README kaydı:** Uygulama ve test sonucu gerekçesiyle kaydedildi ya da henüz kaydedilmedi.

“Uygulandı” ve “README'ye kaydedildi” iki ayrı durumdur. Bir madde ancak kaynak kod karşılığı ve ilgili doğrulama incelendiğinde uygulanmış sayılır. Uygulanan her değişikliğin hangi maddeyi karşıladığı, hangi dosyalarda yapıldığı ve hangi testle doğrulandığı README'de izlenir. Henüz uygulanmamış tasarım kararları uygulanmış gibi gösterilmez. 1–155 maddelerinin mevcut durumları da çalışma boyunca bu ayrımla kontrol edilir; kesinleşmiş kararlar kullanıcı açıkça değiştirmedikçe yeniden açılmaz.

### Çalışma kurallarının değişmesi

Çalışma yöntemini, onay akışını veya burada yazılı bağlayıcı kuralları değiştirmeden önce kullanıcıya değişiklik önerisi ve gerekçesi sunulur; **açık onay alınmadan kural değiştirilmez ve yeni kural uygulanmaz.** Kullanıcının bu bölümde açıkça verdiği talimat, bu izleme ve kayıt düzeninin kendisi için onaydır.

Bu izleme/kayıt yetkisi, kaynak kodu, testleri, dağıtımı veya paketlemeyi değiştirmek için gereken mevcut açık onay şartını kaldırmaz. Yalnızca talep ve gerçekleşen işlerin durumunu takip etme ve onaylanmış değişiklikleri gerekçeleriyle README'ye kaydetme işlemleri için ayrıca onay gerekmez.

### 154 uygulama durumu — 31 Ekim 2026

**Tasarım kararı:** Kullanıcı tarafından onaylandı.  
**Kod karşılığı:** Uygulandı; mevcut mum arşivi ve canlı teknik analiz çekirdeğiyle entegre edildi.  
**Test/doğrulama:** Otomatik testler başarılı; gerçek kullanıcı bilgisayarındaki tam tarihsel arşivle çalışma henüz doğrulanmadı.  
**README kaydı:** Bu bölümde kaydedildi.

Uygulanan dosyalar:
- `tarihsel_geri_test.py` — kapanmış 5 dakikalık mumların kronolojik yeniden oynatılması, geçmiş zaman noktasında aday üretimi, A/B/C ve karar değişimlerinin kaydı, 1h/4h/24h ileri getiri, 24 saatlik MFE/MAE, teknik giriş-stop-hedef olayları ve JSON/CSV.GZ raporları.
- `binance_mum_arsivi.py` — arşivdeki pariteleri listeleme işlevi.
- `radar_core.py` — tarihsel puanlama yolu; arşivlenmemiş geçmiş likiditeyi başarısız saymama ve ölçülebilen puanı ayrı gösterme.
- `tek_motor_paneli.pyw` — Raporlar ekranına parite/tarih seçimi, başlat/durdur, ilerleme ve sonuç özeti.
- `tests/test_historical_backtest.py` ve `tests/windows_ui_smoke.py` — tarihsel geri test ve gerçek Windows panel entegrasyon testleri.

**Son doğrulama:** GitHub Actions [#41178554903](https://github.com/erdaly1947-max/firsat-kontrol-paneli-gelistirme/actions/runs/41178554903). Python birim testlerinin 145'i başarılı; kaynak derleme, ayar JSON doğrulaması, JavaScript testleri, Render yerel testleri ve Windows Tkinter arayüz testi başarılı. Doğrudan Binance WebSocket ve BtcTurk fiyat kontrolleri de başarılı. Genel Actions sonucu, canlı Render ve buna bağlı görüntü/Cloudinary kontrollerinde Render hizmetinin HTTP 503 `Service Suspended` yanıtı vermesi nedeniyle başarısızdır. Bu, tarihsel geri test birim testlerinin başarısız olduğu anlamına gelmez. ZIP oluşturma adımı bu doğrulama çalıştırmasında ayrıca talep edilmediğinden atlanmıştır.

**Kapsam sınırları:** Geçmiş emir defteri/spread/derinlik arşivlenmediği için tarihsel likidite ve güçlü fırsat teyidi “değerlendirilemedi” kalır. Tarihsel Naratif Avcı gözlemleri henüz yoktur. Sayısal “kaçırılmış yükseliş” eşiği tasarımda ayrıca tanımlanmadığından bu ölçüm üretilmez. Aynı 5 dakikalık mumda giriş ile hedef/stop görülürse olay sırası belirsiz bırakılır. Otomatik testler örnek arşiv üzerinde uçtan uca çalışmıştır; kullanıcının kendi bilgisayarındaki tam arşiv üzerinde gerçek veri çalıştırması henüz yapılmamıştır.

### 31 Ekim 2026 durum güncellemesi — önceki durma talimatı yerine geçti

Kullanıcı Tarihsel Geri Test'i değerlendirmiş ve kabul ettikten sonra Naratif Avcı kodlamasına geçilmesine açıkça izin vermiştir. Naratif Avcı'nın 153.1–153.15 kapsamındaki ilk uygulaması, teknik radar bağlantısı, ortak canlı motor kontrolleri ve rapor/arayüz entegrasyonu main dalına eklenmiştir. Bundan sonraki durma noktası, bu uygulama ve test sonuçlarının kullanıcıya sunulmasıdır. Kullanıcının görüşü alınmadan genel Dosya Gezgini arayüz yenilemesine veya grafiklerin koddan çıkarılmasına başlanmayacaktır.

---

## Reddit Data API entegrasyonu — kullanım kapsamı ve kota politikası (31 Ekim 2026)

Bu kayıt kullanıcının açık talebiyle eklenmiştir. Reddit entegrasyonu, kullanıcının kendi Windows bilgisayarında çalışan kişisel Fırsat-Kontrol Paneli için, yalnızca kendi piyasa kararlarını destekleyen **tek kullanıcılı ve ticari olmayan** bir işlevdir. Program başkalarına sunulan, ücretlendirilen, reklamlı veya abonelikli bir ürün/hizmet olarak kullanılmayacaktır. Bu kullanım, ticari API erişimi talebi olarak tanımlanmayacaktır; akademik araştırma projesi olarak da sunulmayacaktır.

### Resmî erişim ön koşulu

- Bu entegrasyon Reddit içinde çalışan bir Devvit uygulaması değil, harici Windows/Python masaüstü programıdır. Reddit'in güncel geliştirici belgeleri harici Python entegrasyonları için Data API yolunu ve Devvit'in desteklemediği kullanım durumlarında Reddit Help üzerinden erişim talebini tarif eder.
- Reddit Responsible Builder Policy (5 Ekim 2026 güncellemesi), API üzerinden Reddit verisine erişmeden önce talep gönderilmesini ve açık onay alınmasını zorunlu kılar. Bu, kişisel kullanımın ticari sayıldığı anlamına gelmez; ticari olmayan harici API erişimi için de onay ön koşuludur.
- Reddit erişim onayı alınmadan API çağrısı yapılmayacak ve kaynak BAĞLI gösterilmeyecektir.
- Erişim yalnızca OAuth ile, doğru ve tanımlayıcı User-Agent (istemci tanımı) kullanılarak yapılacaktır. Kimlik veya kullanım amacı gizlenmeyecektir.
- İlk uygulama salt okunur olacaktır. Gönderi, yorum, oy veya özel mesaj gönderilmeyecek; özel/kapalı topluluk verisi alınmayacaktır.
- Reddit gönderileri yapay zekâ modeli eğitmek için kullanılmayacaktır. Duygu sınıflandırması yerel ve kurallı (sözlük/ölçüt tabanlı) yöntemle yapılacaktır.

### Tutumlu ücretsiz kota politikası — ilk uygulama sınırları

| Ayar | Başlangıç sınırı |
|---|---:|
| Yenileme aralığı | 30 dakika |
| İstek üst sınırı | Saatte 2; günde toplam 48 |
| Her yanıtta alınacak gönderi | En fazla 50 |
| Sayfalama | İlk aşamada kapalı |
| Yorumları ayrıca çekme | İlk aşamada kapalı |
| Ham gönderi verisinin yerel saklanması | En fazla 48 saat |
| Yetkili kota başlıklarını izleme | X-Ratelimit-Used, X-Ratelimit-Remaining, X-Ratelimit-Reset |

Bu sınırlar Reddit'in izin verdiği kotanın tamamını tüketmek için değil, gereksiz trafik oluşturmadan düşük başlangıç kullanımını garanti etmek içindir. İstek sınırı tüm Reddit taraması için ortak bütçedir; her topluluk veya coin için ayrı ayrı 2 istek/saat hakkı oluşturmaz. Kalan kota azalırsa sorgu aralığı uzatılır. HTTP 429 yanıtında Reddit'in bildirdiği sıfırlanma süresi beklenir; alternatif alan adı, farklı hesap veya başka bir yöntemle sınır aşılmaz. Geçici bağlantı hatalarında artan bekleme uygulanır.

Silindiği tespit edilen gönderi ve ona bağlı içerik/kayıtlar kaldırılacaktır. Yazar adı ve kullanıcı kimliği gereksiz yere saklanmayacaktır. Ham gönderi içeriği 48 saatten uzun tutulmayacak; uzun dönemli takip için yalnızca gerekli toplulaştırılmış duygu/yoğunluk ölçümleri değerlendirilecektir.

### Tek seferlik kullanıcı yetkilendirmesinin anlamı — netleştirme

“Reddit hesabındaki tek seferlik yetkilendirme”, ChatGPT hesabını Reddit'e bağlamak değildir. Amaç, Fırsat-Kontrol Paneli masaüstü uygulamasının Reddit Data API erişimini kullanıcının kendi Reddit hesabıyla OAuth üzerinden yetkilendirmesidir.

İşlem sırası birbirinden ayrı iki adımdır:
1. Reddit'in harici Data API uygulaması için istediği geliştirici erişim kaydı/onayı ve uygulama kimliğinin edinilmesi. Bu adım tamamlanmadan masaüstü uygulaması için geçerli OAuth bağlantısı açılamaz.
2. Kod entegrasyonu tamamlandıktan sonra panelin “Reddit'e bağlan” akışının Reddit'in resmî izin ekranını açması. Kullanıcı burada bir kez izin verir; panel OAuth erişim belirtecini ve yenileme bilgisini yalnızca yerel bilgisayarda güvenli biçimde saklar. Kimlik bilgileri sohbete veya GitHub'a yazılmaz.

ChatGPT'nin Reddit hesabına bağlanması veya asistanın Reddit hesabını kullanması bu işin parçası değildir. Reddit içeriklerini Naratif Avcı, kendi uygulama bağlantısı üzerinden toplar ve işler.

### Kullanıcıdan beklenen işlem ve entegrasyon durumu

- Kullanıcı kendi Reddit hesabıyla harici Data API erişim talebini Reddit Help üzerinden gönderecektir. Başvuruda uygulamanın tek kullanıcılı, kişisel, ticari olmayan ve yerel Windows masaüstü aracı olduğu; kapsamının yalnızca izin verilen herkese açık kripto topluluklarından sınırlı sayıda gönderiyi salt okunur biçimde almak ve yerelde özetlemek olduğu açıkça belirtilecektir.
- Devvit'in uygun olmama nedeni: bu program Reddit içinde çalışan bir uygulama değil, kullanıcının kendi bilgisayarında çalışan mevcut Python masaüstü programıdır.
- Başvuru bağlantısı: https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164
- Reddit erişim onayından sonra verilecek OAuth istemci bilgileri sohbete veya GitHub'a yazılmayacak; yalnızca kullanıcının kendi bilgisayarındaki ortam değişkenlerinde saklanacaktır.
- Kullanıcı erişim onayını ve gerekli kimlik bilgilerini yerel olarak hazırlayana kadar kaynak durumu **BAĞLI DEĞİL / ONAY BEKLİYOR** kalacaktır.

**Mevcut kod durumu:** Bu bölüm kota ve kullanım politikasını kaydeder; Reddit API bağlantısının kodlandığı veya canlı test edildiği anlamına gelmez. Entegrasyon kodu, testler, README uygulama kaydı ve gerçek OAuth erişim doğrulaması ayrı ayrı tamamlanıp doğrulanacaktır.



### Reddit başvuru takibi — 31 Ekim 2026

- **Başvuru durumu:** Kullanıcı Reddit Data API erişim talebini 31 Ekim 2026 tarihinde gönderdi. Reddit, “Your request was successfully submitted.” mesajıyla talebin alındığını bildirdi.
- **Mevcut aşama:** Başvuru alınmış durumda; bu mesaj erişim onayı değildir. Değerlendirme/yanıt bekleniyor. API erişim onayı ve gerekli istemci bilgileri gelmeden Reddit API çağrısı yapılmayacak; kaynak bağlı gösterilmeyecek.
- **Referans numarası:** Reddit'in alındı mesajında parantez içinde yer alan harf-rakam dizisi kullanıcı tarafından saklanacaktır. Bu kimlik README'ye veya kaynak koda kopyalanmayacaktır.
- **Takip:** 7 Kasım 2026 tarihinde e-posta ve Reddit başvuru durumu kontrol edilecek. Yanıt yoksa referans numarası kullanılarak takip adımı değerlendirilecek.
- **Hatırlatma:** Kullanıcıya Reddit başvurusunu yeniden gündeme getirip durumunu kontrol etmesi hatırlatılacaktır.

**Kod durumu:** Bu kayıt yalnızca başvuru ve takip durumunu belgelendirir. Reddit API entegrasyon kodu henüz uygulanmış veya canlı test edilmiş sayılmaz.


---

## Ücretsiz kaynak entegrasyonları — 31 Ekim 2026 güncel durum

### CoinMarketCap Keyless Public API

Resmî Keyless Public API, desteklenen uç noktalar için hesap, kayıt, e-posta, API anahtarı veya kredi kartı gerektirmez. Çağrılar `https://pro-api.coinmarketcap.com/public-api` kökünü kullanır; `X-CMC_PRO_API_KEY` başlığı gönderilmez. Keyless çağrılar ortak IP kota havuzunu kullanır. HTTP 429 yanıtında Retry-After değeri dikkate alınır; kademeli bekleme (en fazla 6 saat), önbellek ve seri çağrı kullanılır.

Entegrasyonda kullanılan uç noktalar:
- `/v3/cryptocurrency/listings/latest`: İlk 100 piyasa listelemesi.
- `/v1/cryptocurrency/map`: Ortak USDT evrenindeki coinleri CMC ID ile eşleştirme.
- `/v3/cryptocurrency/quotes/latest`: Benzersiz CMC ID eşleşmesi bulunan coinlerin toplu USD fiyat/hacim verisi.
- `/v1/global-metrics/quotes/latest`: Toplam piyasa değeri/hacmi ve BTC/ETH hâkimiyeti.
- `/v3/fear-and-greed/latest`: Korku ve Açgözlülük.
- `/v1/altcoin-season-index/latest`: Altcoin Sezon Endeksi.
- `/v3/index/cmc100-latest` ve `/v3/index/cmc20-latest`: CMC100/CMC20 endeksleri.

Yenileme aralıkları: listeleme, fiyat/hacim ve Global Metrics 1 saat; ID Map 6 saat; Korku/Açgözlülük 1 saat; Altcoin Sezonu 4 saat; CMC100/20 6 saat. Sembol çakışmalarında coin kimliği tahmin edilmez. Genel piyasa göstergeleri yalnızca bağlam bilgisidir; teknik puanı, teknik güçlü fırsat kapısını veya teknik alarm koşullarını değiştirmez. Coin fiyat/hacim verisi mevcut naratif piyasa tepkisi alanını tamamlar; teknik radar puanına aktarılmaz.

Resmî doküman: https://coinmarketcap.com/api/documentation/pro-api-reference/keyless-public-api/

### TrendKia News

- Herkese açık MCP adresi: `https://trendkia.com/mcp`; API anahtarı, hesap veya kart bilgisi kullanılmaz.
- Streamable HTTP MCP bağlantısı kurulur; `initialize`, `tools/list` ve `tools/call` adımları doğrulanır.
- `list_recent_articles` en fazla 30 son yazıyı 30 dakikada bir getirir.
- Kripto ve ilgili makroekonomi içerikleri süzülür; tarih yoksa, gelecek tarihliyse veya 72 saatten eskiyse güncel haber olarak alınmaz.
- Başlık, kısa özet, yayın tarihi, kategori ve kaynak bağlantısı saklanır; tam metin kopyalanmaz.
- Kaynak hata/kota/önbellek durumu Naratif Avcı kaynak listesinde gösterilir.
- TrendKia haberleri naratif haber kanıtıdır; teknik puanı ve güçlü fırsat koşullarını değiştirmez.

### Investing.com ekonomik takvimi

Investing.com herkese açık veri API'si sunmadığını açıkça belirtir. Ücretsiz ekonomik takvim sayfası vardır; ayrıca web siteleri için ücretsiz widget sağlar. Widget'ın şartları kabul edilmeden üretilmemesi gerekir. Bu masaüstü uygulamasında **BTC ve Piyasa** sayfasına Türkçe Investing.com Ekonomik Takvimini varsayılan tarayıcıda açan düğme eklenir. Sayfa içeriği uygulamaya çekilmez, kopyalanmaz, saklanmaz veya naratif/teknik puana aktarılmaz. Böylece ücretsiz resmi takvim sayfası kullanılırken veri yeniden dağıtımı veya izinsiz otomatik erişim yapılmaz.

Resmî kaynaklar:
- API politikası: https://www.investing-support.com/hc/en-us/articles/115005473825-Do-You-Offer-API-Access-at-Investing-com
- Ücretsiz araç/widget bilgisi: https://www.investing-support.com/hc/en-us/articles/360002357417-Use-our-data
- Türkçe ekonomik takvim: https://tr.investing.com/economic-calendar/index

### Erişim veya içerik kullanım izni bekleyenler

- **The Fly:** Ücretsiz geliştirici planı olsa da içerik toplama/birleştirme ve türetilmiş ürün kullanımı için izin belirsizdir. Koddan otomatik çağrı yapılmaz.
- **Reddit:** Data API başvurusu için açık onay ve OAuth bilgileri beklenir; onay gelene kadar çağrı yapılmaz.
- **AIXBT Topic→Project:** Ayrıntılı eşleme yetkisi doğrulanmadığı için çağrılmaz; ücretsiz Topics ilk 25 akışı korunur.
- **Investing.com widget verisi:** Takvim sayfası uygulamadan açılır. Widget'ın HTML içeriği masaüstü uygulamasına çekilmez; veri erişim lisansı varsayılmaz.
- **X:** Önceki karara uygun olarak entegrasyon dışı kalır.

### Test kapsamı

Yeni testler CMC Keyless yanıt yapıları, USD quote dizisi, ID çakışması, toplu fiyat yanıtı, piyasa/sentiment göstergeleri, TrendKia MCP metin ayıklama/tarih filtresi, SSE aktarımı ve 429 bekleme süresini kapsar. Canlı MCP/CMC erişimi ve genel Actions sonucu, GitHub Actions tamamlandığında ayrıca raporlanır. ZIP veya Release bu test sonucuyla otomatik olarak onaylanmış sayılmaz.
