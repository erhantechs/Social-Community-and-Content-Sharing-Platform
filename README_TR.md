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
