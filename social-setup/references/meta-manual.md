# Meta: mod manual (pengguna buat sendiri, AI pandu)

Pandu pengguna **satu langkah pada satu masa**. Hantar satu langkah, kemudian tunggu pengguna balas "siap" (atau tanya soalan) sebelum hantar langkah seterusnya. Setiap langkah: tajuk pendek, pautan kalau ada, 2 hingga 4 arahan klik. Jangan hantar semua langkah sekali gus.

Kalau pengguna tersekat, minta dia terangkan apa yang dia nampak di skrin (atau hantar screenshot **tanpa token**), dan bantu dari situ. Nama butang Meta kadang-kadang berubah; cari yang paling hampir.

Sebelum mula, semak pengguna dah ada: Facebook Page yang dia urus, Instagram professional (Business atau Creator) yang disambung ke Page, akaun Threads public, dan Business Portfolio yang ada Page dan IG tu.

## A. Sediakan app

1. **Login Meta for Developers.** Buka https://developers.facebook.com/apps, klik **Continue with Facebook**.
2. **Create app.** Klik **Create App**. Nama app: **Content API**. Klik **Next**.
3. **Pilih 3 use case:** **Manage everything on your Page**, **Manage messaging & content on Instagram**, **Access the Threads API**. Klik **Next**. Kalau Meta tak benarkan pilih ketiga-tiga, pilih Page dan Instagram dulu; tambah Threads kemudian di **Use cases › Add use case**.
4. **Pilih Business Portfolio** yang ada Page dan Instagram. Klik **Next** sampai app dicipta.
5. **Tambah permission.** **Use cases**, **Customize** use case Page: tambah `pages_manage_posts` dan `pages_read_engagement`. **Customize** use case Instagram, pilih **API setup with Facebook login** (bukan Instagram login): tambah `instagram_basic` dan `instagram_content_publish`.

## B. Token Facebook + Instagram

6. **Semak aset.** Buka https://business.facebook.com/settings. **Accounts › Instagram accounts**: pastikan IG ada. **Accounts › Pages**: pastikan Page ada. Kalau IG tiada, klik **Add** dan login Instagram.
7. **System user.** **Users › System users**. Dah ada satu (contohnya dari setup Meta Ads)? Guna yang sama. Kalau belum: **Add**, nama **Content API**, role **Admin**.
8. **Assign assets.** Klik **Assign assets**. Pages: pilih Page, **Full control**. Instagram accounts: pilih IG, **Full control**. Apps: pilih **Content API**, **Full control**. Klik **Assign assets**.
9. **Generate token (jangan copy lagi ke chat).** Klik **Generate token**. App: **Content API**. Expiration: **Never**. Tanda `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`. Klik **Generate token**. Biarkan tab ni terbuka; token akan ditampal dalam wizard di langkah akhir. Permission tak keluar? Balik ke langkah 5.
10. **Page ID & Instagram ID.** Buka https://developers.facebook.com/tools/explorer. Tampal token dalam kotak **Access Token** (di situ sahaja, bukan dalam chat). Taip `me/accounts?fields=name,id,instagram_business_account`, klik **Submit**. Catat `id` Page dan `id` dalam `instagram_business_account`.

## C. Token Threads

11. **Threads Tester.** **Use cases**, **Customize** **Access the Threads API**: pastikan `threads_basic` dan `threads_content_publish` ada. **App roles › Roles › Add People › Threads Tester**, masukkan username Threads.
12. **Terima jemputan** di telefon: app Threads, **Settings › Account › Website permissions › Invites › Accept**.
13. **Generate token Threads.** Balik ke **Customize** Threads, bahagian **User Token Generator**, klik **Generate Access Token**. Biarkan terbuka untuk langkah akhir.

## D. Langkah akhir: masukkan token

Bila pengguna siap langkah 13, jalankan wizard (lihat SKILL.md, "Langkah akhir"). Beritahu pengguna: "Wizard dah dibuka dalam browser. Terus ke kotak di bawah, tampal Token Facebook + Instagram, Page ID, Instagram Business ID dan Token Threads, kemudian klik **Sahkan & Simpan**." Langkah dalam wizard boleh dilangkau; pengguna dah buat semuanya.
