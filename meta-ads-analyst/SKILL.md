---
name: meta-ads-analyst
description: Analisis prestasi iklan Meta Ads sedia ada — audit visual satu produk (gambaran, struktur, iklan terbaik/terburuk, corak menang, titik perubahan, pembaziran, kesimpulan) daripada data sejarah, atau buat keputusan harian/mingguan (stop, tambah bajet, test angle sama, angle baru) untuk setiap iklan aktif. Guna bila pengguna sudah ada iklan berjalan dan mahu audit penuh satu produk, atau mahu semakan iklan aktif minggu/hari ini. Baca sahaja, tak ubah apa-apa dalam ad account. Analyzes existing Meta Ads performance data to produce a visual account audit report or per-ad stop/scale/refresh decisions.
---

# Meta Ads Analyst

Skill ini ada dua mod. Pilih ikut permintaan pengguna:

| Mod | Bila | Hasil |
|---|---|---|
| **Audit akaun** | Pengguna ada iklan sebelum ini dan mahu audit penuh satu produk — corak menang/kalah, struktur, titik perubahan, pembaziran (lesson 02.1) | Laporan audit visual 7 seksyen + cadangan brain |
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

## Mod Audit akaun

1. **Kumpul input.** Tanya produk yang diaudit, tempoh, harga jualan, dan untung kasar setiap jualan. Kalau akaun ada beberapa produk, tanya juga filter (nama kempen atau landing link) untuk asingkan produk itu daripada yang lain.
2. **Dapatkan data.** Connector Meta Ads disambung: tarik data tahap iklan untuk tempoh dan filter produk yang diminta (campaign/adset/ad, spend, result, cost per result, frequency, CTR, bulanan). Tiada connector: minta eksport CSV yang meliputi tempoh dan produk sama.
3. **Kira 7 seksyen:**
   - **Gambaran**: jumlah spend, result, cost per result, ROAS (kalau ada dan tidak mengelirukan) untuk tempoh penuh; pecahan bulanan spend + cost per result.
   - **Struktur**: bilangan kempen, pecahan objektif, ABO vs CBO, bilangan ad set, bilangan iklan.
   - **Iklan terbaik vs terburuk**: 5 termurah dan 5 termahal ikut cost per result; abaikan iklan dengan spend bawah RM50; sertakan thumbnail creative bila connector bagi.
   - **Corak menang**: hook, format, tawaran, market, audience setiap corak yang menang, sebagai tag/ikon pendek — bukan ayat.
   - **Titik perubahan**: pecahan bulanan cost per result, frequency, CTR; tanda bulan yang prestasi berubah dan sebab paling mungkin (creative letih / harga / musim / audience).
   - **Pembaziran**: jumlah RM dibelanja tanpa result langsung, dan iklan paling membazir.
   - **Kesimpulan**: 3 pengajaran satu baris; sasaran cost per result yang masih untung, dikira daripada untung kasar setiap jualan; 3 idea iklan baru untuk test seterusnya.
4. **Isi JSON** ikut `references/format-audit.md` dan render paparan (lihat **Paparan audit** di bawah).
5. **Simpan** fail paparan sebagai `audit-iklan.html` dalam folder kerja pengguna.
6. **Cadangkan ringkasan brain**: `Tambah:`, `Ubah:`, `Buang:` untuk bahagian 6 (Iklan) brain — sasaran kos, angle menang, angle kalah — ikut format sedia ada `marketing-brain/references/format-brain.md`. Tanya pengguna untuk setuju sebelum kata ia sudah masuk brain.

Mod Keputusan harian/mingguan boleh ambil sasaran cost per result terus daripada kad kesimpulan audit, bukan tanya pengguna semula.

## Mod Keputusan harian/mingguan

1. **Semak sasaran kos.** Baca bahagian 6 brain, medan "Sasaran kos". Kalau tiada, tanya **satu** soalan: "Apa sasaran cost per result (RM) yang masih untung untuk anda?" sebelum teruskan.
2. **Tarik data iklan aktif**, biasanya 7 hari lepas (atau sejak launch kalau lebih baharu), tahap iklan/ad set: spend, result, cost per result, frequency, CTR, hari berjalan.
3. **Buat satu keputusan setiap iklan/ad set**, tepat satu daripada: **Stop**, **Tambah bajet**, **Test angle sama**, **Angle baru**, atau **Tunggu** (belum cukup data/hari untuk dinilai). Ikut susunan semakan dan nilai lalai dalam `references/thresholds.md` (gandaan sasaran kos — nombor RM tetap pengajar belum muktamad, jadi guna gandaan, bukan angka keras). Beza penting antara "Test angle sama" (angle masih menang, creative letih — frequency tinggi/CTR jatuh) dan "Angle baru" (hook tak pernah menarik/convert): rujuk fail rujukan.
4. **Output**: jadual satu iklan satu baris — nama, spend, result, cost per result vs sasaran, keputusan (badge), signal yang mencetus, sebab ringkas. Kalau ada folder `runtime/` dalam folder kerja, tambah juga satu entri prestasi ringkas setiap keputusan (`marketing-brain/references/format-runtime.md`) supaya mod "Kemas kini brain dari runtime" skill `marketing-brain` boleh belajar daripadanya kemudian.
5. Hasilkan paparan HTML dengan senarai tindakan yang boleh disalin (lihat **Paparan keputusan**).
6. **Jangan ubah apa-apa** dalam ad account. AI baca dan cadang; pengguna yang luluskan setiap tindakan secara berasingan.

## Paparan audit

Paparan Mod Audit akaun ialah `assets/audit-report.html`.

1. Salin `assets/audit-report.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali satu tempat: kandungan di antara `<script id="meta-ads-audit-data" type="application/json">` dan `</script>`.
2. Ganti kandungan itu dengan satu objek JSON sah ikut skema dalam `references/format-audit.md`. Tinggalkan seksyen keluar sepenuhnya kalau data tiada — paparan tunjuk "tiada data" untuk seksyen itu sahaja. Kalau data mengandungi `</script`, tulis sebagai `<\/script`.
3. Paparkan sebagai HTML:
   - **Claude:** cipta artifact HTML.
   - **ChatGPT:** buka dalam canvas dan tekan Preview.
   - Kalau HTML tidak boleh dipaparkan, beri fail `.html` untuk dimuat turun dan dibuka dalam browser.
4. Simpan fail yang dipaparkan sebagai `audit-iklan.html` dalam folder kerja pengguna.

## Paparan keputusan

Paparan Mod Keputusan harian/mingguan ialah `assets/decision-table.html` (medan `"mode": "keputusan"` dalam data — lihat `references/format-data.md` untuk skema penuh).

1. Salin `assets/decision-table.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali satu tempat: kandungan di antara `<script id="meta-ads-analyst-data" type="application/json">` dan `</script>`.
2. Ganti kandungan itu dengan satu objek JSON sah ikut skema dalam `references/format-data.md`. Kalau data mengandungi `</script`, tulis sebagai `<\/script`.
3. Paparkan sebagai HTML ikut cara yang sama di atas (artifact / canvas Preview / fail `.html`).

Jangan tulis semula mana-mana paparan dari kosong dan jangan buang bahagian skrip. Butang salin dalam paparan bergantung padanya.

## Bila brain tiada Sasaran kos atau data prestasi

Kalau brain langsung tiada bahagian 6 terisi (tiada iklan sebelum ini), beritahu pengguna skill ini bukan untuk mereka — cadangkan skill `meta-ads-strategist` (lesson 02.2) dahulu untuk rancang test pertama.
