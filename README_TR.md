<p align="center">
  <img src="static/images/logo.svg" alt="SocialHub" height="56">
</p>

# SocialHub — Sosyal Topluluk ve İçerik Paylaşım Platformu

Django ile geliştirilmiş, modern bir sosyal medya web uygulaması. Kullanıcılar profil oluşturabilir, gönderi (yazı + görsel) paylaşabilir, birbirlerini takip edebilir, gönderileri beğenip yorum yapabilir, 24 saatlik hikâyeler paylaşabilir, kişiselleştirilmiş bir akış görebilir, herkese açık içerikleri keşfedebilir ve ilgi alanlarına göre öneriler alabilir.

Arayüz, modern bir sosyal medya panosundan ilham alınarak tasarlandı: solda profil kartı ve birincil navigasyon, ortada kart tabanlı akış, sağda hikâyeler / öneriler / ilgi alanı tavsiyeleri.

> Django dersi dönem ödevi olarak hazırlandı. Proje, sunulduğu gibi deploy edilebilir kalitede yazıldı.

---

## İçindekiler

1. [Özellikler](#özellikler)
2. [Teknoloji yığını](#teknoloji-yığını)
3. [Proje yapısı](#proje-yapısı)
4. [Modeller ve mimari](#modeller-ve-mimari)
5. [Kurulum](#kurulum)
6. [Ortam değişkenleri](#ortam-değişkenleri)
7. [Testleri çalıştırma](#testleri-çalıştırma)
8. [Demo verisi yükleme](#demo-verisi-yükleme)
9. [Ekran görüntüleri](#ekran-görüntüleri)
10. [Deployment](#deployment)
11. [Notlandırma kriterleriyle eşleşme](#notlandırma-kriterleriyle-eşleşme)
12. [Lisans](#lisans)

---

## Özellikler

### Temel
- **Kimlik doğrulama** — kayıt, giriş, çıkış, parola sıfırlama (Django built-in).
- **Kullanıcı profilleri** — kayıt sırasında otomatik oluşturulur. Avatar, kapak görseli, biyografi, konum, web sitesi, ilgi alanları. Profil sayfası gönderi sayısı, takipçi ve takip edilen sayılarını gösterir.
- **Gönderiler (CRUD)** — metin, opsiyonel görsel, konum ve görünürlük (`herkese açık`, `sadece arkadaşlar`, `özel`) ile oluşturma, okuma, güncelleme, silme.
- **Beğeni** — tek tıkla aç/kapat; AJAX, sayfa yenileme yok.
- **Yorumlar** — ekleme ve silme (sadece yazar veya gönderi sahibi silebilir).
- **Takip et / takipten çık** — yönlü ilişkiler; AJAX.
- **Kişiselleştirilmiş akış** — takip ettiklerinin gönderileri + kendi gönderilerin. Filtreler: *Recents*, *Friends*, *Popular*.
- **Keşfet (Explore)** — tüm herkese açık gönderiler; ilgi alanına göre filtrelenebilir.
- **Hikâyeler** — 24 saat sonra otomatik silinen geçici görsel paylaşımları.
- **Arama** — gönderi (içerik / konum / yazar / etiket) ve kullanıcı (isim / kullanıcı adı) araması.
- **Hashtag (`#etiket`) ve mention (`@kullanıcı_adı`)** — gönderi metnindeki etiketler tıklanabilir bağlantılara dönüşür; bahsi geçen kullanıcı bildirim alır.
- **Bildirimler** — biri gönderini beğendiğinde, yorum yaptığında, seni takip ettiğinde veya seni etiketlediğinde bildirim alırsın. Sidebar'da okunmamış bildirim rozeti.
- **İlgi alanı tavsiyeleri** — renkli ilgi alanı çipleri; explore akışını etikete göre filtreleyebilir.
- **Sayfalama** — akışta 10, explore'da 12 gönderi/sayfa.
- **Responsive** — masaüstü, tablet ve mobil düzenleri.

### Gelişmiş
1. **Auth + yetkilendirme** — Django auth + custom signup formu (email zorunlu, parola sıfırlama dahil).
2. **İzinler** — class-based view'lar `UserPassesTestMixin` ile sadece yazarın gönderiyi düzenleyip silebilmesini sağlar; yorumları yalnızca yazarı veya gönderi sahibi silebilir.
3. **AJAX dinamik beğeni ve takip** — `fetch()` + JSON endpoint'leri.
4. **Arama ve filtreleme** — gönderiler ve kullanıcılar üzerinde çok alanlı arama; `#hashtag` aramaları özel olarak tanınır.
5. **Sayfalama** — Django `Paginator` her uzun listede.
6. **Sorgu optimizasyonu** — `select_related` + `prefetch_related`; gönderi sayıları `Subquery(Count)` ile annotate edilir (cartesian join sorununu engeller).
7. **DB constraint'leri** — `UniqueConstraint` aynı kullanıcının aynı gönderiyi iki kez beğenmesini ve aynı kullanıcıyı iki kez takip etmesini, `CheckConstraint` kendini takip etmeyi DB seviyesinde engeller.
8. **24 saatlik hikâyeler** — `expires_at` timestamp ile otomatik gizleme.
9. **Sidebar cache** — sağ kolon (öneriler, hikâyeler, ilgi alanları) 60 saniye boyunca per-user cache'lenir.
10. **Honeypot anti-spam** — gizli `website_url` alanı bot kayıtlarını engeller.
11. **Login rate limiting** — IP başına 5 dakika içinde 10 başarısız denemeden sonra 429.

---

## Teknoloji yığını

| Katman      | Araç                                       |
|-------------|--------------------------------------------|
| Backend     | Django 4.2, Python 3.11+                   |
| Veritabanı  | SQLite (dev) — Postgres'e kolayca geçilebilir |
| Frontend    | Bootstrap 5.3, Bootstrap Icons, custom CSS |
| Formlar     | Django ModelForm                            |
| AJAX        | `fetch` API + JSON endpoint'leri            |
| Statik     | WhiteNoise (production'da compressed manifest) |
| Görsel      | Pillow                                      |
| Sunucu      | Gunicorn (production); Django dev server (local) |

---

## Proje yapısı

```
Social Community and Content Sharing Platform/
├── manage.py
├── requirements.txt
├── Procfile                    # Render / Heroku için
├── runtime.txt
├── .env.example
├── .gitignore
├── README.md / README_TR.md
├── socialhub/                  # Django project (settings, urls)
├── accounts/                   # users, profiles, follows, interests
│   ├── models.py / views.py / forms.py / urls.py / signals.py
│   ├── throttle.py             # login rate limiting
│   └── tests.py
├── posts/                      # posts, images, comments, likes, stories
│   ├── models.py / views.py / forms.py / urls.py
│   ├── templatetags/post_extras.py   # hashtag/mention linkifier
│   └── management/commands/seed.py
├── notifications/              # in-app notifications + context processor
├── templates/
│   ├── base.html / partials/ / posts/ / accounts/ / registration/
│   ├── notifications/ / errors/
├── static/css/ static/js/
├── docs/screenshots/           # screenshot dosyaları buraya
└── media/                      # kullanıcı yüklemeleri
```

---

## Modeller ve mimari

```
User (Django auth)
 └─1:1─ Profile (avatar, cover, bio, location, website, interests m2m)
 └─m:n─ Follow → User      (UniqueConstraint + CheckConstraint(no self-follow))
 └─1:n─ Post (body, image, visibility, interests m2m)
 │       └─1:n─ PostImage   (ekstra galeri görselleri)
 │       └─1:n─ Comment     (gönderi silinince cascade)
 │       └─1:n─ Like        (UniqueConstraint per user/post)
 └─1:n─ Story               (24 saatte expires_at ile gizlenir)
 └─1:n─ Notification        (recipient/actor/verb/post)

Interest (Music, Cooking, Hiking, …)
 └─m:n─ Profile, Post
```

Önemli tasarım kararları:
- `Profile`, built-in `User`'ın bir-bir uzantısı (custom AbstractUser yerine) — Django auth'u sade tutar, migration başağrısı yaratmaz.
- `Follow`, `ManyToManyField(through=...)` yerine bağımsız bir model — zaman damgalı sıralama ve bildirimler için temiz.
- Beğeniler `UniqueConstraint` kullanır — race condition imkânsız.
- Gönderilerin `visibility` alanı detail view'da sunucu tarafında doğrulanır.
- Akış sorgusu `like_count`, `comment_count` ve `is_liked`'i tek round-trip'te annotate eder — N+1 yok.

---

## Kurulum

### Ön gereksinimler
- Python 3.11+
- pip

### Adımlar

```bash
# 1. Projeyi klonla
git clone <repo-url>
cd "Social Community and Content Sharing Platform"

# 2. Sanal ortam (önerilir)
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS / Linux

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. Ortam dosyasını kopyala
copy .env.example .env           # Windows
# cp .env.example .env           # macOS / Linux

# 5. Migration'ları çalıştır
python manage.py migrate

# 6. Superuser oluştur
python manage.py createsuperuser

# 7. (Opsiyonel) Demo verisi yükle — 8 kullanıcı, gönderiler, takipler, beğeniler, yorumlar
python manage.py seed

# 8. Geliştirme sunucusunu başlat
python manage.py runserver
```

http://127.0.0.1:8000/ adresini aç. Kök URL akışa yönlendirir.

`seed` çalıştırdıysan, herhangi bir demo kullanıcı ile giriş yapabilirsin:
- Kullanıcı: `george_lobko`, `vitaly_boyko`, `nick_shelburne`, `brittni_lando`, `ivan_shev`, `anatoly_p`, `lolita_earns`, `silena`
- Parola: `DemoPass!234`

---

## Ortam değişkenleri

| Değişken                | Varsayılan                      | Notlar |
|-------------------------|---------------------------------|--------|
| `DJANGO_SECRET_KEY`     | (insecure default — değiştir!)  | Üret: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG`          | `true`                          | Production'da `false` yap. |
| `DJANGO_ALLOWED_HOSTS`  | `localhost,127.0.0.1,*`         | Production'da gerçek domain'leri yaz. |
| `DJANGO_EMAIL_BACKEND`  | console backend                 | SMTP için: `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` | — | SMTP ayarları (parola sıfırlama mailleri için) |

---

## Testleri çalıştırma

```bash
python manage.py test
```

Test seti şunları kapsar:
- Kayıt → kullanıcı + profil oluşturulur, aynı email reddedilir
- Login / logout akışları
- Profil sayfası render ve "edit profile" auth gereksinimi
- Takip et / takibi bırak (kendini takip etmeme + unique constraint + AJAX JSON)
- Kullanıcı arama
- Gönderi oluşturma / hızlı gönderi / boş gönderi reddi / login gereksinimi
- Gönderi update & delete izinleri (yalnızca yazar)
- Beğeni / beğeniyi geri al / unique constraint / AJAX JSON
- Yorum oluşturma, sadece yazar veya gönderi sahibi silebilir
- Akış filtreleri (sadece kendi + takip ettikleri), explore (tüm public), gönderi araması
- Hikâye 24 saat expiry mantığı
- Görünürlük kontrolleri (private/friends/public, takipçi/non-takipçi)
- Mention & hashtag çıkarma + bildirim oluşturma
- Like / Comment / Follow / Mention bildirim oluşumu
- Honeypot field bot kayıtlarını engeller
- 10 başarısız login denemesi sonrası 429

**52 test, hepsi yeşil.**

---

## Demo verisi yükleme

```bash
python manage.py seed              # demo verisi ekler
python manage.py seed --clear      # önce temizler, sonra yeniden ekler
```

8 ilgi alanı, 8 demo kullanıcı (biyo + ilgi alanı ile), rastgele gönderi / takip / beğeni / yorum oluşturur. Kurulumdan hemen sonra dolu bir dashboard görmek için kullan.

---

## Ekran görüntüleri

`docs/screenshots/` klasörüne aşağıdaki isimlerle PNG bırak; README otomatik gösterir:

| Sayfa | Dosya |
|-------|-------|
| Akış (sidebar + gönderiler + öneriler) | `feed.png` |
| Explore (public gönderiler, ilgi filtreleri) | `explore.png` |
| Profil (kapak, avatar, istatistikler) | `profile.png` |
| Yorumlu gönderi detayı | `post_detail.png` |
| Login | `login.png` |
| Kayıt | `signup.png` |
| Mobil görünüm | `mobile.png` |

Yakalama yönergesi için bkz. `docs/screenshots/README.md`.

---

## Deployment

### Render (önerilen ücretsiz tier)

1. Projeyi GitHub'a pushla.
2. https://render.com'da **Web Service** oluştur.
3. Repo'yu bağla. Render `Procfile`'ı otomatik algılar.
4. Build command:
   ```
   pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
   ```
5. Start command:
   ```
   gunicorn socialhub.wsgi
   ```
6. **Environment** bölümünde:
   - `DJANGO_SECRET_KEY` = (yeni rastgele string)
   - `DJANGO_DEBUG` = `false`
   - `DJANGO_ALLOWED_HOSTS` = `senin-app.onrender.com`
7. **Create Web Service**'e bas.

### PythonAnywhere

1. Projeyi PythonAnywhere'e yükle veya `git clone` yap.
2. Virtualenv oluşturup `pip install -r requirements.txt`.
3. **Web** sekmesinde WSGI dosyasını `socialhub.wsgi`'ye yönlendir.
4. Static mapping ekle: `/static/` → `<project>/staticfiles`, `/media/` → `<project>/media`.
5. Console'da:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --no-input
   python manage.py createsuperuser
   ```
6. Web app'i reload et.

### Production notları

- WhiteNoise statik dosyaları sıkıştırılmış olarak serve eder (yalnızca `DEBUG=False` iken `STATICFILES_STORAGE`).
- Medya dosyaları (kullanıcı yüklemeleri) varsayılan olarak yerel diske gider. Render free tier'da kalıcı disk ekle; production'da S3 + `django-storages` öner.
- `DEBUG=False` iken `SECURE_*` cookie flag'leri, `XSS` filter, `X-Frame-Options=DENY` etkinleşir.

---

## Notlandırma kriterleriyle eşleşme

| Kriter                       | Pts | Nasıl karşılanıyor |
|------------------------------|-----|---------------------|
| Core Functionality           | 25  | Tüm zorunlu özellikler (auth, posts CRUD, görseller, beğeni, yorum, takip, akış, explore, arama, profil, hikâyeler) implement edildi. |
| Database Design              | 15  | Sekiz ilişkili model, FK + M2M, `related_name`, timestamp'ler, `__str__`, indeksler, beğeni/takip için `UniqueConstraint`, kendini takip etmeye karşı `CheckConstraint`. |
| Frontend & UX                | 15  | Bootstrap + custom dashboard CSS, sidebar nav, profil kartı, kart tabanlı feed, hikâyeler grid, öneriler, ilgi çipleri, composer, hover state'ler, empty state'ler, hata mesajları. |
| Advanced Features            | 15  | Auth + permissions, AJAX beğeni & takip, arama (hashtag desteği dahil), sayfalama, sorgu optimizasyonu, DB constraint'leri, signal'ler, custom 404/500, hashtag/mention linkifier, honeypot, login rate limit, sidebar cache. |
| Code Quality                 | 10  | App'ler concern'e göre ayrılmış; N+1 yok; class-based view'lar; thin view'lar. |
| Documentation                | 10  | Bu README + `README.md` (İngilizce) + `seed` komutu + her modülde docstring. |
| Testing                      | 5   | 52 test: kayıt, giriş, takip, gönderi CRUD, izinler, beğeni, yorum, akış filtreleri, hikâye expiry, görünürlük, mention/hashtag, bildirim oluşumu, honeypot, throttle. |
| Deployment                   | 5   | `requirements.txt`, `Procfile`, `runtime.txt`, `.env.example`, WhiteNoise, security header'ları, Render & PythonAnywhere notları. |
| **Bonus**                    | 5   | Bildirimler (okunmamış sayaç + context processor), 24 saatlik hikâyeler, ilgi tabanlı içerik filtresi, hashtag/mention sistemi, seed komutu. |

---

## Lisans

MIT — özgürce öğren, fork'la, uyarla.

---

## Demo hesaplar

`python manage.py seed` çalıştırdıktan sonra aşağıdaki hesaplarla giriş yapabilirsin.

> ⚠️ **Bu bilgiler yalnızca geliştirme içindir.** Projeyi herkese açık bir sunucuya deploy etmeden önce mutlaka değiştir (veya `python manage.py seed --clear` ile demo veriyi sil ve kendi kullanıcılarını oluştur).

### Admin (yönetici)

| URL | Kullanıcı adı | Parola |
|-----|---------------|--------|
| `http://127.0.0.1:8000/admin/` | `admin` | `AdminPass!234` |

Henüz admin oluşturmadıysan:
```bash
python manage.py createsuperuser
```

### Demo kullanıcılar (10 adet — hepsinin parolası aynı)

> **Tüm demo kullanıcılar için parola:** `DemoPass!234`

| # | Kullanıcı adı | Ad Soyad | Konum | Meslek |
|---|----------|----------|-------|--------|
| 1 | `emma_wilson` | Emma Wilson | Stockholm, İsveç | Ürün tasarımcısı |
| 2 | `liam_anderson` | Liam Anderson | Dublin, İrlanda | Backend mühendisi |
| 3 | `sophia_martinez` | Sophia Martinez | Lizbon, Portekiz | Seyahat yazarı |
| 4 | `noah_thompson` | Noah Thompson | Banff, Kanada | Dağ rehberi & fotoğrafçı |
| 5 | `olivia_garcia` | Olivia Garcia | Madrid, İspanya | Pasta şefi |
| 6 | `ethan_roberts` | Ethan Roberts | Berlin, Almanya | Bağımsız oyun geliştirici |
| 7 | `isabella_walker` | Isabella Walker | Bali, Endonezya | Yoga eğitmeni |
| 8 | `mason_cooper` | Mason Cooper | New Orleans, ABD | Caz davulcusu |
| 9 | `ava_mitchell` | Ava Mitchell | Cape Town, Güney Afrika | Deniz biyologu |
| 10 | `lucas_bennett` | Lucas Bennett | Atina, Yunanistan | Mimar |

Her demo kullanıcının gerçek avatarı, kapak görseli, fotoğraflı gönderileri, 1–2 hikâyesi, takip ilişkileri, beğeni ve yorumları otomatik olarak `seed` komutuyla oluşturulur.

---

## Bu projede Django'nun kullanımı ve önemi

Bu proje bilinçli olarak "Django öncelikli" tasarlandı. Gördüğünüz hemen her özellik — kimlik doğrulamadan admin panele, kullanıcının yüklediği görsellerden JSON API yanıtlarına kadar — Django'nun zaten var olan, sahada test edilmiş ve sıfırdan yazılsa haftalar alacak bir parçasına yaslanıyor.

Aşağıda, projedeki kullanım yerleriyle birlikte hangi Django özelliklerinin hangi sorunu çözdüğü anlatılıyor; böylece kaynağı okurken neden Django'nun seçildiği netleşiyor.

### 1. MVT (Model-View-Template) mimarisi

Tüm depo, beş odaklı uygulamada çoğaltılan **Django MVT üçlüsü** etrafında düzenli:

| Katman | Görevi | Örnekler |
|--------|--------|----------|
| **Modeller** (`models.py`) | Veriyi ve onu koruyan kuralları tanımlar | `Post`, `Profile`, `Follow`, `Like`, `Story`, `Conversation`, `Notification`, `Block`, `Bookmark` |
| **View'lar** (`views.py`) | HTTP isteğini yanıta çevirir, iş kurallarını uygular | `feed_view`, `post_create`, `toggle_like`, `PostUpdateView`, `thread`, `notification_dropdown` |
| **Template'ler** (`templates/`) | Django template diliyle HTML üretir | `base.html` (dashboard kabuğu), `_post_card.html` ve `_comment.html` gibi tekrar kullanılabilir parça'lar |

Projeyi birden fazla app'e (`accounts`, `posts`, `notifications`, `messaging`, `api`) bölmek de Django geleneği — her app bağımsız test edilebilir, çıkarılabilir ve başka projede yeniden kullanılabilir.

### 2. ORM ve ilişkisel bütünlük

Sosyal platformlar ilişkilerle yaşar: kim kimi takip ediyor, hangi gönderiyi beğendin, hangi yorum hangi yoruma cevap. Django'nun **ORM**'u bunu düz Python ile modellememizi ve doğruluğun veritabanı tarafından korunmasını sağlar:

- **`ForeignKey` ve `ManyToManyField`** kullanıcıları gönderilere, gönderileri ilgi alanlarına, yorumları (cevaplar için) parent yorumlara bağlar.
- **`UniqueConstraint`** veritabanı seviyesinde aynı beğeninin (`Like`), aynı takibin (`Follow`), aynı bookmark'ın (`Bookmark`) ve aynı engelin (`Block`) iki kez oluşmasını engeller — race condition'a karşı bile.
- **`CheckConstraint`** kullanıcının kendini takip etmesini veya kendini engellemesini DB tarafında engeller, view koduna güvenmek zorunda kalmaz.
- **Özelleştirilmiş `QuerySet` annotation'ları** — [`posts/views.py`](posts/views.py) içindeki `annotate_posts` her gönderiye `like_count`, `comment_count`, `is_liked` ve `is_bookmarked` alanlarını **tek** SQL sorgusunda ekler — N+1 problemi yok.

Yani sosyal grafiğin gerçeği şemada yaşıyor; view koduna dağılmış değil.

### 3. Hazır kimlik doğrulama (auth)

`django.contrib.auth` hazır olarak ne lazımsa veriyor: güvenli parola hashleme (varsayılanda PBKDF2), session yönetimi, login/logout view'ları, parola sıfırlama mailleri, `@login_required` decorator'ı ve `User` modeli. Bunu `User`'ı subclass etmek yerine **bir-bir `Profile`** ile genişlettik — daha basit, migration baş ağrısı az.

Üstüne **gizli honeypot signup alanı** ve **cache tabanlı login throttle** (`accounts/throttle.py`) ekleyerek bot kayıtlarını ve brute-force denemelerini durduruyoruz.

### 4. Bedava admin panel

Projedeki her model `admin.py`'de kaydedildiği anda `/admin/`'de tam bir CRUD arayüzü kazanıyor. Sosyal bir platform için bu çok büyük bir kazanç: gönderi moderasyonu, kullanıcı banlama, takip grafiğini inceleme, bildirim ve konuşmalara bakma — hiçbir ek view yazmadan. Django'nun en az takdir edilen süper güçlerinden biri.

### 5. Form'lar, doğrulama ve dosya yüklemeleri

Django'nun **`ModelForm`**'u HTML form'ları doğrudan modellere bağlar, validasyon otomatik gelir. Signup, profil düzenleme, gönderi oluşturma, yorum ve hikâye'lerde kullanıyoruz. Dosya yüklemeleri (avatar, kapak, gönderi fotoğrafı, hikâye görseli) `ImageField` üzerinden direkt çalışır — Django dosyayı `MEDIA_ROOT`'a yazar ve dev'de servis eder. `posts/forms.py` içindeki özel validator'lar dosya boyutu ve content-type kurallarını uygular.

### 6. Template'ler, Django template dili ve özel tag'ler

Template engine inheritance (`base.html`), parça dosyalar (tekrar kullanılan `_post_card.html`), context processor'lar (`unread_notification_count` her sayfada erişilebilir) ve özel template tag'leri ([`posts/templatetags/post_extras.py`](posts/templatetags/post_extras.py) içindeki `linkify_post` `@mention` ve `#hashtag`'leri tıklanabilir bağlantılara çevirir — HTML escape edildikten sonra, güvenli şekilde) destekler.

### 7. Signal'ler — otomatik yan etkiler

Yeni bir `User` oluşturulduğunda, [`accounts/signals.py`](accounts/signals.py) içindeki `post_save` signal'i sayesinde otomatik olarak bir `Profile` da oluşur. View katmanı bunu yapmayı asla unutamaz. Like, comment, follow ve mention'lardan tetiklenen bildirimler de eylemin yanında oluşturuluyor — yan etkiler ait oldukları yere yakın kalıyor.

### 8. URL yönlendirme ve ters çözümleme (reverse)

URL config her app için namespace'lenmiş (`accounts:profile`, `posts:detail`, `messaging:thread`...). Template ve view'lar hep `{% url %}` ve `reverse()` kullanıyor — hard-coded path yok — bu sayede bir URL'i yeniden adlandırmak tüm bağlantıları otomatik günceller.

### 9. Django REST Framework entegrasyonu

`/api/` katmanı için Django'nun class-based view'ları üzerine kurulmuş **DRF** eklendi. ViewSet'ler, serializer'lar, permission class'ları, throttling, token auth ve OpenAPI üretimi (`drf-spectacular`) Django uygulamasının geri kalanıyla temizce kompoze oluyor — aynı auth, aynı modeller, aynı veritabanı. `/api/docs/` adresindeki Swagger UI tamamen serializer + viewset meta verisinden otomatik üretiliyor.

### 10. Django'nun bedava verdiği güvenlik özellikleri

Django, projenin otomatik faydalandığı sağduyulu varsayılanlarla geliyor:

- Her POST formunda **CSRF koruması**.
- Template'lerde **varsayılan HTML escape** — XSS opt-in, opt-out değil.
- ORM ile **parametrik SQL sorguları** — query parametresinden SQL injection imkansız.
- **Clickjacking koruması** (`X-Frame-Options: DENY`) — production için settings.py'da açık.
- **Güvenli session cookie'leri, HSTS, secure proxy header'ları** — `DEBUG=False`'ta otomatik açılıyor.
- PBKDF2 ile **parola hashleme** (Argon2'ye geçilebilir).

Auth ve SQL'i el ile yazsaydık aylarca güvenlik denetimi gerekecekti. Django bu güvenli varsayılanları ilk günden veriyor.

### 11. Migration'lar

Bu projedeki her şema değişikliği — `Comment.parent`, `Block`, `Bookmark`, `CommentLike`'ı eklemek, `Story.expires_at`'i indekslemek — bir migration dosyası olarak izleniyor. `python manage.py migrate` onları sırayla uygular; `seed --clear` üstüne demo veriyi yeniden basar. Şema evrimi her takım arkadaşı veya production deploy'u için tekrarlanabilir.

### 12. Test framework'ü

84 test signup, login, gönderi CRUD, izinler, beğeni/iptal, yorumlar ve cevaplar, takip/bırakma, engeller, bookmark'lar, hikâye süresi, görünürlük, mention, hashtag, throttling, honeypot'u kapsıyor — hepsi `django.test.TestCase` ile, her çalıştırmada izole bir transactional test veritabanı kuruluyor. CI (`.github/workflows/ci.yml`) push'larda otomatik çalıştırıyor.

### Bu proje için neden Django doğru framework?

Sosyal topluluk platformu tam olarak Django'nun tasarlandığı senaryo:

1. **Çok sayıda ilişkili varlık** (kullanıcılar, gönderiler, yorumlar, takipler...) → ORM + admin burada parlıyor.
2. **Auth kritik** → kendi yapma; `django.contrib.auth` yeterli.
3. **İçerik moderasyonu önemli** → bedava admin panel haftalar kazandırıyor.
4. **Dönem ödevi süresi** → "pilleri dahil" felsefesi tek geliştiriciye günler içinde teslim imkanı veriyor.
5. **Gelecekteki ölçeklenme** → trafik artınca SQLite → Postgres'e `DATABASE_URL` ile, yerel medya → S3'e `django-storages` ile geçilebilir, arka plan işleri için Celery eklenebilir — framework projeyle birlikte büyüyor.

Kısaca: Django sıkıcı (ama temel) %80'i — auth, admin, ORM, form'lar, güvenlik, migration'lar — sağlıyor, böylece bu repo'daki tasarım ve özellik geliştirmenin tamamı sosyal platforma özgü %20'ye odaklanabildi: feed'ler, hikâyeler, mention'lar, karanlık mod, bildirimler, mesajlaşma ve dashboard UI'ı.

---

## 🚀 Projeyi kendi bilgisayarında çalıştır — adım adım

GitHub'dan repo'yu indirdin ve ne yapacağını bilmiyor musun? Bu rehber seni "sıfırdan" "tamamen dolu bir sosyal platforma giriş yapmış" hâle yaklaşık 5 dakikada götürür.

### Adım 0 — Gerekenleri kontrol et

| Araç | Minimum sürüm | Kontrol komutu |
|------|---------------|----------------|
| **Python** | 3.11 veya üstü | `python --version` |
| **pip** | Python ile birlikte gelir | `pip --version` |
| **Git** *(opsiyonel — sadece `git clone` kullanırsan)* | herhangi yeni sürüm | `git --version` |

Eğer `python --version` "command not found" diyorsa veya 3.10 ya da daha eski gösteriyorsa, önce https://www.python.org/downloads/ adresinden en yeni Python'u kur. **Windows'ta kurulum sırasında "Add Python to PATH" kutucuğunu işaretle.**

### Adım 1 — Kodu indir

**Seçenek A — Git ile (tavsiye edilen):**
```bash
git clone https://github.com/erhantechs/Social-Community-and-Content-Sharing-Platform.git
cd Social-Community-and-Content-Sharing-Platform
```

**Seçenek B — ZIP indirme:**
1. GitHub sayfasında yeşil **`Code`** butonuna tıkla → **Download ZIP**
2. ZIP'i kullanışlı bir yere çıkar
3. Çıkardığın klasörde bir terminal aç

### Adım 2 — Sanal ortam (virtual environment) oluştur *(şiddetle tavsiye edilir)*

Sanal ortam, bu projenin kütüphanelerini bilgisayarındaki diğer her şeyden ayrı tutar.

```bash
# Oluştur
python -m venv .venv

# Aktifleştir
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate
```

Aktifleştirdikten sonra terminal prompt'unun başında `(.venv)` görmen gerekir. Bundan sonra her `python` ve `pip` komutu bu izole ortamda çalışır.

> **PowerShell hatası: "running scripts is disabled"?**
> Bir kerelik şunu çalıştır: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, sonra tekrar aktifleştir.

### Adım 3 — Gerekli Python paketlerini kur

```bash
pip install -r requirements.txt
```

Bu, `requirements.txt`'de listelenen Django, DRF, Pillow, WhiteNoise ve birkaç diğer kütüphaneyi indirir. Genelde 30-60 saniye sürer.

### Adım 4 — Ortam dosyasını ayarla

```bash
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env
```

Yerel geliştirme için varsayılanları aynı bırakabilirsin. Bu dosya sadece `SECRET_KEY`, `DEBUG` ve email/veritabanı ayarlarını override etmek istersen var.

### Adım 5 — Veritabanını oluştur

```bash
python manage.py migrate
```

Bu komut, Django'nun ve uygulamaların ihtiyaç duyduğu tüm tablolarla yeni bir `db.sqlite3` dosyası oluşturur. `Applying ... OK` satırlarından oluşan uzun bir liste görmen gerekir.

### Adım 6 — Admin hesabını oluştur

```bash
python manage.py createsuperuser
```

İstendiğinde bir kullanıcı adı, email (opsiyonel) ve parola gir. Bu hesap `/admin/` paneline giriş yapmak için kullanacağın hesap.

### Adım 7 *(opsiyonel ama tavsiye edilir)* — Demo veriyi yükle

Doldurulmuş bir dashboard'u hemen görmek ister misin? Şunu çalıştır:

```bash
python manage.py seed
```

Bu komut 10 demo kullanıcıyı gerçek avatar, kapak görseli, gönderi, hikâye, takip, beğeni ve yorumlarla birlikte oluşturur. Görsellerin picsum.photos / pravatar.cc'den inmesini bekle — yaklaşık 30 saniye. (İnternet yoksa otomatik olarak gradient placeholder'lara düşer.)

Bu bittikten sonra **`emma_wilson`** kullanıcı adı + **`DemoPass!234`** parola ile giriş yapabilirsin (veya 10 demo kullanıcıdan herhangi biri — yukarıdaki *Demo hesaplar* tablosuna bak).

### Adım 8 — Sunucuyu başlat

```bash
python manage.py runserver
```

Şunu görmen gerekir:

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### Adım 9 — Tarayıcıda aç

Aşağıdaki adresleri ziyaret et:

| URL | Ne göreceksin |
|-----|---------------|
| http://127.0.0.1:8000/ | Feed'e yönlendirir (giriş gerekli) |
| http://127.0.0.1:8000/posts/ | Kişiselleştirilmiş feed |
| http://127.0.0.1:8000/posts/explore/ | Herkese açık gönderiler |
| http://127.0.0.1:8000/admin/ | Admin paneli (Adım 6'daki superuser ile) |
| http://127.0.0.1:8000/api/docs/ | İnteraktif API dokümantasyonu (Swagger UI) |
| http://127.0.0.1:8000/healthz/ | Sağlık kontrolü JSON `{"status":"ok"}` |

### Adım 10 *(opsiyonel)* — Test setini çalıştır

```bash
python manage.py test
```

`Ran 84 tests in ...s` ve sonrasında `OK` görmen gerekir. Herhangi bir test başarısız olursa ortamında bir şey yanlış demektir.

---

### 🔧 Sık karşılaşılan sorunlar ve hızlı çözümler

| Belirti | Çözüm |
|---------|-------|
| `python: command not found` | python.org'dan Python 3.11+ kur. Windows'ta "Add Python to PATH" kutucuğunu işaretle. |
| `ModuleNotFoundError: No module named 'django'` | Venv'i aktifleştirmeyi unuttun (Adım 2) veya Adım 3'ü atladın. |
| `OperationalError: no such table: ...` | Adım 5'i atladın. `python manage.py migrate` çalıştır. |
| Port 8000 kullanımda | `python manage.py runserver 8001` — farklı port kullanır. |
| PowerShell'de venv aktifleştirirken izin reddi | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` çalıştır, tekrar dene. |
| Giriş "Too many login attempts" (429) hatası | Rate limit'e takıldın. 5 dakika bekle veya dev sunucusunu yeniden başlat. |

### 🛑 Sunucuyu nasıl durdurursun

Sunucunun çalıştığı terminalde **`Ctrl + C`** tuşlarına bas.

Daha sonra geri döndüğünde, sadece **Adım 2 (venv aktifleştir)** ve **Adım 8 (runserver)**'ı tekrarlaman yeter — geri kalan her şey zaten kurulmuş durumda.

---

Hepsi bu kadar. Artık yerel olarak çalışan, tam işlevsel bir SocialHub'a sahipsin. Yukarıda kapsanmayan bir sorunla karşılaşırsan GitHub'da bir issue aç veya README'nin daha üst kısımlarındaki *Kurulum* ve *Deployment* bölümlerine bak — çoğu kenar durum orada belgelenmiş.
