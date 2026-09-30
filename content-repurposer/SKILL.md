---
name: content-repurposer
description: Tukar satu content asal (rakaman live, kelas, video atau transkrip) kepada video pendek (cari highlight), carousel Instagram, atau post bertulis (Threads, newsletter). Guna bila pengguna ada rakaman/transkrip/content lama dan nak "repurpose", "cari highlight", "buat carousel", atau "tukar jadi Threads/newsletter". Turns one piece of original content into short-video highlights, a carousel, or written posts.
---

# Content Repurposer

Satu content asal (live, kelas, video) boleh jadi banyak format: video pendek, carousel, post bertulis. Skill ini ada tiga mod yang guna sumber yang sama.

| Mod | Bila | Hasil |
|---|---|---|
| **Video pendek** | Pengguna ada rakaman/transkrip, nak cari bahagian untuk video pendek | ~10 highlight berperingkat + paparan pemilih |
| **Carousel** | Pengguna nak carousel Instagram | 7 slide + caption + paparan |
| **Post bertulis** | Pengguna nak Threads/newsletter | 5 post Threads + 1 newsletter |

Kalau pengguna tak nyatakan mod, tanya yang mana satu (atau tiga-tiga sekali, guna sumber content yang sama — itu maksud "1 content original untuk semua platform").

## Peraturan umum

- **Langkah 1, semua mod:** baca `marketing-brain.md` dari Project. Kalau tiada, sebut dalam satu baris, cadangkan jalankan skill `marketing-brain` dulu, dan teruskan dengan paling banyak 2 soalan pendek.
- Tulis dalam suara brand daripada brain bahagian **2. Brand & gaya bahasa**, dan elakkan perkataan yang ditandakan sebagai dielak.
- Guna content pillar (bahagian 5) untuk label setiap highlight/post, dan CTA utama (bahagian 3) dalam caption.
- Kalau brain kosong atau `(belum pasti)` pada bahagian yang penting (contohnya CTA), sebut dalam satu baris dan teruskan dengan andaian paling selamat.
- Jangan reka fakta, angka atau testimoni yang tiada dalam sumber content atau brain.

## Mod: Video pendek

**Input:** transkrip dengan timestamp. Kalau pengguna tiada transkrip, terangkan ringkas: transkrip auto daripada Zoom/Riverside/Descript, atau minta ChatGPT/Claude transkripkan fail audio/video yang dimuat naik. Timestamp mesti ada — tanpanya highlight tak boleh dipotong.

1. Baca transkrip penuh.
2. Cari lebih kurang 10 highlight yang **berdiri sendiri**, 20–90 saat setiap satu. Untuk setiap satu:
   - Timestamp mula dan tamat
   - Hook: baris 3 saat pertama yang buat orang berhenti scroll
   - Sebab ia menarik (satu ayat)
   - Cadangan teks di skrin (on-screen text)
   - Caption dengan CTA daripada brain
   - Content pillar (daripada brain bahagian 5)
3. Susun ikut kekuatan, terkuat dulu.
4. Bentangkan sebagai senarai dalam chat, **dan** hasilkan paparan HTML (lihat **Paparan** di bawah).
5. Sebut langkah seterusnya: potong dengan tool video pengguna sendiri, atau hantar senarai timestamp yang dipilih kepada editor. Paparan ada butang "salin dipilih" untuk ini.

## Mod: Carousel

7 slide lalai: 1 hook, 5 value, 1 CTA. Boleh ubah bilangan kalau pengguna minta.

1. Ringkaskan isi content asal.
2. Susun ikut slide: slide 1 hook (buat orang stop dan swipe), slide 2–6 satu idea setiap slide (maksimum ~20 perkataan setiap slide), slide 7 CTA daripada brain.
3. Tulis caption penuh untuk post (boleh lebih panjang daripada teks slide).
4. Hasilkan paparan HTML (lihat **Paparan** di bawah).
5. Terima arahan edit ringkas, contohnya "slide 3 terlalu panjang, pendekkan", dan hasilkan semula paparan.
6. Nota: paparan ini untuk semak teks dan susunan sahaja; ia tidak eksport gambar. Pengguna reka slide sebenar dalam Canva/Figma atau tool design mereka, guna teks daripada paparan/senarai.

## Mod: Post bertulis

Output dalam chat sahaja, tiada paparan HTML.

1. Ambil idea utama daripada content asal.
2. **5 post Threads**, sudut pandang berbeza-beza, setiap satu berdiri sendiri (tak perlu post lain untuk faham), bawah 500 aksara.
3. **1 newsletter**: 3 pilihan subject line, badan 300–600 perkataan, gaya lebih peribadi dan panjang daripada Threads.
4. Tunjukkan beza gaya antara Threads (pendek, bercakap) dan newsletter (panjang, peribadi).

## Paparan

Dua paparan HTML, satu untuk setiap mod yang ada paparan:

- **Video pendek:** `assets/highlight-picker.html`. Skema data di `references/format-highlights.md`.
- **Carousel:** `assets/carousel-preview.html`. Skema data di `references/format-carousel.md`.

Cara menghasilkan paparan (sama untuk kedua-dua):

1. Salin fail asset **sepenuhnya, tanpa mengubah apa-apa** kecuali kandungan dalam blok `<script id="...-data" type="application/json"> ... </script>` (id tepat: `highlight-data` untuk pemilih highlight, `carousel-data` untuk carousel).
2. Ganti kandungan itu dengan JSON yang sah ikut skema dalam `references/`. Elakkan aksara `</script` mentah dalam nilai teks.
3. Paparkan sebagai HTML:
   - **Claude:** cipta artifact HTML.
   - **ChatGPT:** buka dalam canvas dan tekan Preview.
   - Kalau HTML tidak boleh dipaparkan, beri fail `.html` untuk dimuat turun dan dibuka dalam browser.

Jangan tulis semula paparan dari kosong dan jangan buang bahagian skrip. Butang salin dalam paparan bergantung padanya. Kalau brain ada warna brand/accent, boleh masukkan dalam JSON (`accent`) untuk paparan carousel guna warna itu; kalau tiada, paparan guna warna neutral lalai.

## Lepas hasil

- Tawarkan jadualkan sebagai draf melalui Post-bridge atau Postiz kalau connector itu ada dalam Project. **Jangan sekali-kali publish/aktifkan terus** — draf sahaja, sehingga pengguna sahkan dalam chat.
- Cadangkan apa nak log balik ke brain lepas post keluar dan dapat prestasi: highlight/hook/pillar mana yang dipilih dan kenapa (bahagian 5 — Content), untuk jalankan skill `marketing-brain` mod Kemas kini lepas seminggu.
