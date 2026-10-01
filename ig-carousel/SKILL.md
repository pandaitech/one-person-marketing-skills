---
name: ig-carousel
description: Tukar satu sumber (transkrip kelas/webinar, kertas kajian, artikel/berita, atau transkrip klip video pendek) kepada carousel Instagram 6–9 slide yang lengkap — pilih satu angle, rancang urutan, semak kualiti, dan papar sebagai kanvas 1080×1350 boleh muat turun PNG. Guna bila pengguna ada sumber content dan nak "buat carousel", "jadikan IG carousel", atau "carousel untuk kajian/artikel ni". Turns one source (class transcript, research paper, article, or short-clip transcript) into a complete, downloadable Instagram carousel.
---

# IG Carousel

Satu sumber (transkrip, kertas kajian, artikel, atau klip video) jadi satu
carousel Instagram siap — teks dikunci, gaya visual dipilih, dan paparan boleh
dimuat turun sebagai PNG terus dari chat (Claude artifact atau ChatGPT canvas).

Skill ini gabungkan tiga peringkat kerja dalam satu jalan: **pilih angle →
rancang slide → semak kualiti → render**. Rujukan penuh setiap peringkat ada
dalam `references/`; fail ini ringkasan alur kerja.

## Langkah 0: Baca sumber dan brain

1. Baca sumber penuh yang pengguna beri. Sumber yang disokong:
   - **Transkrip kelas/webinar/video** — auto daripada Zoom/Riverside/Descript,
     atau minta ChatGPT/Claude transkripkan fail audio/video yang dimuat naik.
   - **Kertas kajian** (PDF, link, atau abstrak/ringkasan yang ditampal).
   - **Artikel/berita** (teks ditampal atau link).
   - **Transkrip klip video pendek** (TikTok/Reels/YouTube Shorts).

   Kalau tiada satu pun sumber ini diberi, tanya pengguna nak guna yang mana.
2. Baca `marketing-brain.md` daripada Project kalau ada. Guna gaya bahasa
   (bahagian 2), CTA utama (bahagian 3) dan content pillar (bahagian 5). Kalau
   brain tiada atau `(belum pasti)` pada bahagian penting, sebut satu baris dan
   teruskan dengan andaian paling selamat — jangan berhenti tunggu brain.
3. **Sebelum mula:** kalau ada folder `runtime/`, baca tajuk/topik entri
   **14–28 hari lepas** sahaja (`marketing-brain/references/format-runtime.md`)
   supaya topik/angle tak berulang. Jangan baca runtime penuh.

## Langkah 1: Pilih SATU angle

Baca `references/plan-and-gates.md` bahagian 1–2. Ringkasnya:

- Bekukan sumber: asing fakta, tafsiran, inferens.
- Kalau pengguna dah beri angle, itu kunci skop — jangan tukar.
- Kalau belum, bandingkan sehingga 3 calon angle dengan skor berat (nilai
  audience, kelainan, bukti boleh kesan, kekuatan berdiri sendiri, sesuai
  carousel, kesegaran), lulus hard gate, pilih satu.
- Untuk kertas kajian: dapatan mesti wujud dalam kajian — jangan reka angka.

Kalau tiada calon lulus hard gate, beritahu pengguna apa bukti/keputusan yang
hilang dan jangan teruskan render dengan angle lemah.

## Langkah 2: Rancang urutan slide (6–9 slide)

Baca `references/plan-and-gates.md` bahagian 3. Tulis dulu penjelasan penuh,
baru pecah jadi slide. Satu idea satu slide. Slide 1 = hook (`layout: cover`).
Slide terakhir = CTA daripada brain, atau `resolution` kalau tiada CTA.
Kertas kajian wajib satu slide `layout: source` dengan citation penuh. Rekod
`copy density` setiap slide (short/medium/long); `overfull` mesti dipendekkan
atau dipecah sebelum render.

Bentangkan rancangan ringkas dalam chat (senarai slide: nombor, layout, satu
baris isi) untuk pengguna nampak susunan sebelum render — bukan JSON penuh.

## Langkah 3: Semak kualiti

Baca `references/plan-and-gates.md` bahagian 4. Jalankan lapan ujian (satu-
tesis, pembaca sejuk, jambatan/pergantungan, buang, pertindihan, jejak sumber,
penutup, ketumpatan mudah alih). Betulkan slide yang gagal sebelum render.
Jangan tunjuk hasil ujian penuh kepada pengguna melainkan diminta — cukup
sebut kalau ada slide yang dibetulkan/dibuang dan kenapa.

## Langkah 4: Pilih gaya visual

Baca `references/style-reference.md`.

- **Ada rujukan (pengguna tampal/muat naik screenshot carousel yang disuka):**
  ekstrak token `theme` (warna, rasa fon, jenis layout, penjajaran, hiasan)
  daripada imej itu.
- **Tiada rujukan:** guna warna brand daripada `marketing-brain.md`; kalau
  brain pun tiada warna, guna lalai neutral `carousel.html`.

Untuk ratio teks:seni, margin selamat 1080×1350 dan pilihan hiasan CSS, lihat
`references/visual-and-layout.md`. Mod lalai **tiada** penjanaan imej AI —
`carousel.html` sendiri sudah jadi reka bentuk penuh (tipografi + warna +
hiasan CSS). Kalau pengguna secara eksplisit nak slide berilustrasi, lihat
**Mod pilihan** di bawah.

## Langkah 5: Render paparan

1. Salin `assets/carousel.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali
   kandungan blok `<script id="carousel-data" type="application/json">`.
2. Isi JSON ikut skema penuh dalam `references/format-carousel.md`
   (`business`, `topic`, `theme`, `slides[]`, `caption`).
3. Paparkan sebagai HTML:
   - **Claude:** cipta artifact HTML.
   - **ChatGPT:** buka dalam canvas dan tekan Preview.
   - Kalau HTML tidak boleh dipaparkan, beri fail `.html` untuk dimuat turun
     dan dibuka dalam browser.
4. Beritahu pengguna: setiap slide boleh dimuat turun sebagai PNG (butang di
   bawah setiap kad) atau semua sekali sebagai ZIP (butang atas). Kalau
   persekitaran sekat eksport (sandbox canvas), paparan sendiri akan tunjuk
   amaran dan cadangkan screenshot manual — tak perlu risau ia gagal senyap.
5. Tulis juga caption penuh dalam chat (bukan hanya dalam paparan), supaya
   pengguna boleh terus salin walaupun paparan tak dibuka.

Jangan tulis semula `carousel.html` dari kosong dan jangan buang bahagian
skrip — butang eksport/salin bergantung padanya.

## Selepas siap: tulis ke runtime

Lepas carousel siap dipaparkan, tambah satu entri ke `runtime/log-YYYY-MM.md`
ikut format `marketing-brain/references/format-runtime.md` (tarikh, platform
IG, sumber, angle/hook, status draf). Kalau angle datang daripada
`bank-content.md` atau `bank-kajian.md`, tanda baris itu `dah guna <tarikh>`.
Kalau AI tak boleh tulis fail terus, keluarkan teks entri runtime (dan baris
bank yang dikemas kini) untuk pengguna tampal sendiri.

## Edit ikut chat

Pengguna boleh minta pindaan ringkas selepas paparan keluar, cth. *"slide 3
panjang sangat, pendekkan"*, *"tukar warna aksen jadi hijau"*, *"buang slide 5"*,
*"tukar layout slide 2 jadi list"*. Kemas kini JSON sahaja (bukan struktur
fail), semak semula ketumpatan/gate yang terjejas, dan republish paparan yang
sama (jangan cipta artifact/canvas baharu melainkan pengguna minta versi lain
untuk dibandingkan).

## Mod pilihan: slide berilustrasi

Kalau pengguna secara eksplisit nak imej/ilustrasi dijana AI pada setiap slide
(bukan sekadar reka bentuk teks), baca `references/image-generation-chatgpt.md`
untuk templat prompt setiap slide. Guna copy yang sudah dikunci daripada
Langkah 2 — jangan biar model imej tulis semula ayat. Paling sesuai dalam
ChatGPT (penjanaan imej terus); dalam Claude, cadangkan pengguna guna alat imej
pilihan mereka dengan prompt yang sama.

## Peraturan umum

- Jangan reka fakta, angka, atau citation yang tiada dalam sumber. Untuk kertas
  kajian, citation (pengarang/tahun/tajuk atau link) wajib pada slide `source`
  dan caption.
- Imej yang dijana AI (mod pilihan) bukan bukti — jangan guna untuk gantikan
  screenshot/hasil sebenar.
- Bercakap dan tulis dalam suara brand daripada brain; kalau tiada brain, guna
  Bahasa Melayu santai dan jelas secara lalai.
- Jangan publish/jadualkan post — skill ini render paparan sahaja. Kalau
  pengguna nak jadualkan, cadangkan skill lain (Post-bridge/Postiz) yang
  tersedia dalam Project, dan tunggu pengesahan eksplisit sebelum apa-apa draf.
