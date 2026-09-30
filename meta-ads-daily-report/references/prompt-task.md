# Prompt Task 2 — Laporan iklan

Ini Task 2 dari had 5 task berjadual ChatGPT (lesson 01.7). Satu task sahaja untuk semua iklan — jangan buat satu task setiap iklan atau satu task setiap campaign.

## Task 2 biasa (Laporan iklan sahaja)

**Nama task:** `Laporan iklan`
**Jadual:** setiap hari, 7:00 pagi waktu Malaysia (Asia/Kuala_Lumpur)
**Connector diperlukan:** Meta Ads MCP (`https://mcp.facebook.com/ads`) dan Google Sheets/Drive

**Arahan untuk ditampal dalam task:**

```
Jalankan skill meta-ads-daily-report, mod Laporan Harian, untuk akaun iklan saya.
Baca marketing-brain.md dari Project untuk sasaran kos.
Tarik data semalam dan 7 hari lepas untuk semua iklan aktif dari Meta Ads MCP.
Bandingkan setiap iklan dengan sasaran kos dan tandakan keputusan (Stop, Tambah
bajet, Test angle sama, Angle baru, atau Tunggu) ikut ambang dalam skill.
Tulis baris baharu ke Google Sheet "Report Iklan – <nama bisnes>", tab Harian
dan Ringkasan. Jangan ubah, stop, hidupkan atau naikkan bajet apa-apa iklan —
laporan sahaja. Beri saya ringkasan pendek boleh baca dalam 30 saat.
```

Gantikan `<nama bisnes>` dengan nama sheet sebenar dari Mod Setup.

## Variant gabungan — "Satu task, banyak kerja"

Guna ini **hanya** kalau pengguna sudah kena had 5 task (Plus) atau pelan mereka, dan mahu gabungkan Task 1 (content harian, dari skill `marketing-brain`/repurposer) dengan Task 2 (laporan iklan) dalam **satu** task harian. Jadualkan pada waktu yang sesuai untuk kedua-dua bahagian siap sebelum pengguna bangun — contohnya 6:45 pagi supaya laporan 7 pagi tetap tepat masa.

**Nama task:** `Content + Laporan harian`
**Jadual:** setiap hari, 6:45 pagi waktu Malaysia

**Arahan untuk ditampal dalam task:**

```
Buat dua kerja berasingan, dalam susunan ini, dan laporkan kedua-dua hasil
dalam satu balasan:

BAHAGIAN 1 — Content harian
Baca Marketing Brain. Tulis post hari ini ikut siri minggu ni. Jadualkan
semuanya ke Post-bridge pada masa yang sesuai untuk setiap platform.

BAHAGIAN 2 — Laporan iklan
Jalankan skill meta-ads-daily-report, mod Laporan Harian. Tarik data semalam
dan 7 hari lepas untuk semua iklan aktif dari Meta Ads MCP, banding dengan
sasaran kos dalam brain, tandakan keputusan ikut ambang dalam skill, dan tulis
ke Google Sheet "Report Iklan – <nama bisnes>". Jangan ubah apa-apa dalam ad
account — laporan sahaja.

Beri ringkasan pendek untuk kedua-dua bahagian, boleh baca dalam 30 saat.
```

## Test-run sebelum bergantung padanya

Sebelum tinggalkan task berjadual berjalan sendiri esok pagi:

1. Dalam ChatGPT, buka task yang baru dicipta dan tekan **Run now** (atau padanan "jalankan sekarang").
2. Semak Google Sheet — pastikan baris baharu masuk dalam tab `Harian` dan `Ringkasan` dengan lajur betul, bukan kosong atau tersalah susun.
3. Baca ringkasan chat yang task hasilkan — pastikan ia sebut spend, hasil, kos per hasil sebenar (bukan `-` semua, tanda connector tak sambung dengan betul).
4. Kalau connector Sheets gagal semasa test-run, sahkan fallback CSV keluar dengan betul dan pengguna faham mereka kena salin-tampal manual esok pagi sehingga isu itu selesai.
5. Hanya lepaskan task berjalan automatik selepas test-run pertama berjaya.
