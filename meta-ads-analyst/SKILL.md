---
name: meta-ads-analyst
description: Analisis prestasi iklan Meta Ads sedia ada — cari corak iklan yang menang dan kalah daripada 90 hari data, atau buat keputusan harian/mingguan (stop, tambah bajet, test angle sama, angle baru) untuk setiap iklan aktif. Guna bila pengguna sudah ada iklan berjalan dan mahu AI belajar daripada data, atau mahu semakan iklan aktif minggu/hari ini. Baca sahaja, tak ubah apa-apa dalam ad account. Analyzes existing Meta Ads performance data to surface winning/losing patterns or produce per-ad stop/scale/refresh decisions.
---

# Meta Ads Analyst

Skill ini ada dua mod. Pilih ikut permintaan pengguna:

| Mod | Bila | Hasil |
|---|---|---|
| **Belajar dari data** | Pengguna ada iklan sebelum ini dan mahu cari corak menang/kalah (lesson 02.1) | Corak menang & kalah dengan bukti + cadangan brain + paparan |
| **Keputusan harian/mingguan** | Pengguna mahu semakan iklan aktif: stop, tambah bajet, test angle sama, atau angle baru (lesson 02.7) | Jadual keputusan satu-per-satu iklan + paparan |

Dua-dua mod **baca sahaja**. Skill ini tidak pernah pause, aktifkan, edit atau naikkan bajet iklan tanpa kelulusan jelas dalam chat untuk perubahan spesifik itu. Minggu pertama, cadangkan baca-dan-cadang sahaja.

## Peraturan umum

- Bercakap dalam bahasa pengguna. Lalai: Bahasa Melayu yang santai dan jelas.
- Jangan reka fakta atau angka. Guna metrik yang benar-benar ada sahaja.
- Sumber data: connector Meta Ads MCP rasmi (`https://mcp.facebook.com/ads`, OAuth) bila disambung — guna apa-apa tool insights/list yang connector itu dedahkan, jangan hardcode nama tool. Kalau tiada connector, minta eksport CSV Ads Manager atau screenshot, dan terangkan ringkas cara eksport (Ads Manager → Reports → Export → CSV, tahap Ad, tempoh yang perlu).
- Nilai berdasarkan metrik hasil bisnes (purchases/leads/messages ikut objective), cost per result, dan ROAS kalau ada. Jangan guna metrik vanity (reach, likes, views) sebagai asas keputusan.
- Tiada skrip untuk dijalankan dan tiada path lokal diandaikan — mesti berfungsi dalam ChatGPT Projects dan claude.ai Projects.

## Langkah 1 (semua mod): Baca Marketing Brain

Baca `marketing-brain.md` daripada Project. Kalau tiada, beritahu pengguna dalam satu baris, cadangkan jalankan skill `marketing-brain` dulu, dan teruskan dengan paling banyak 2 soalan pantas.

## Mod Belajar dari data

1. **Dapatkan data.** Kalau connector Meta Ads disambung, tarik data tahap iklan untuk **90 hari lepas**. Kalau tidak, minta CSV/screenshot yang meliputi tempoh sama.
2. **Susun ikut cost per result** (atau ROAS kalau ada), bukan spend atau reach.
3. **Cari corak**, bukan item — bandingkan merentasi angle/hook, format creative, tawaran, audience dan placement. Rujuk `references/thresholds.md` untuk peraturan minimum spend/result sebelum panggil satu corak "menang" atau "kalah"; kalau tak cukup data, tulis sebagai hipotesis dan katakan begitu.
4. **Output**: corak menang dan kalah teratas, setiap satu dengan bukti angka (spend, result, cost per result, bilangan iklan dalam corak).
5. **Cadangkan perubahan brain** dalam bentuk `Tambah:`, `Ubah:`, `Buang:` untuk bahagian 6 (Iklan — angle yang menang/kalah) dan entri baharu bahagian 7 (Pengajaran, format dalam `marketing-brain/references/format-brain.md`). Tanya pengguna untuk setuju sebelum kata ia sudah masuk brain.
6. Hasilkan paparan HTML (lihat **Paparan** di bawah).
7. Ingatkan: ini baca sahaja, tiada apa yang berubah dalam ad account.

## Mod Keputusan harian/mingguan

1. **Semak sasaran kos.** Baca bahagian 6 brain, medan "Sasaran kos". Kalau tiada, tanya **satu** soalan: "Apa sasaran cost per result (RM) yang masih untung untuk anda?" sebelum teruskan.
2. **Tarik data iklan aktif**, biasanya 7 hari lepas (atau sejak launch kalau lebih baharu), tahap iklan/ad set: spend, result, cost per result, frequency, CTR, hari berjalan.
3. **Buat satu keputusan setiap iklan/ad set**, tepat satu daripada: **Stop**, **Tambah bajet**, **Test angle sama**, **Angle baru**, atau **Tunggu** (belum cukup data/hari untuk dinilai). Ikut susunan semakan dan nilai lalai dalam `references/thresholds.md` (gandaan sasaran kos — nombor RM tetap pengajar belum muktamad, jadi guna gandaan, bukan angka keras). Beza penting antara "Test angle sama" (angle masih menang, creative letih — frequency tinggi/CTR jatuh) dan "Angle baru" (hook tak pernah menarik/convert): rujuk fail rujukan.
4. **Output**: jadual satu iklan satu baris — nama, spend, result, cost per result vs sasaran, keputusan (badge), signal yang mencetus, sebab ringkas.
5. Hasilkan paparan HTML dengan senarai tindakan yang boleh disalin (lihat **Paparan**).
6. **Jangan ubah apa-apa** dalam ad account. AI baca dan cadang; pengguna yang luluskan setiap tindakan secara berasingan.

## Paparan

Paparan ialah `assets/decision-table.html`, digunakan untuk **kedua-dua mod** (medan `"mode"` dalam data tentukan susun atur — lihat `references/format-data.md` untuk skema penuh).

Cara menghasilkan paparan:

1. Salin `assets/decision-table.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali satu tempat: kandungan di antara `<script id="meta-ads-analyst-data" type="application/json">` dan `</script>`.
2. Ganti kandungan itu dengan satu objek JSON sah ikut skema dalam `references/format-data.md` (`"mode": "belajar"` atau `"mode": "keputusan"`). Kalau data mengandungi `</script`, tulis sebagai `<\/script`.
3. Paparkan sebagai HTML:
   - **Claude:** cipta artifact HTML.
   - **ChatGPT:** buka dalam canvas dan tekan Preview.
   - Kalau HTML tidak boleh dipaparkan, beri fail `.html` untuk dimuat turun dan dibuka dalam browser.

Jangan tulis semula paparan dari kosong dan jangan buang bahagian skrip. Butang salin dalam paparan bergantung padanya.

## Bila brain tiada Sasaran kos atau data prestasi

Kalau brain langsung tiada bahagian 6 terisi (tiada iklan sebelum ini), beritahu pengguna skill ini bukan untuk mereka — cadangkan skill `meta-ads-strategist` (lesson 02.2) dahulu untuk rancang test pertama.
