---
name: meta-ads-daily-report
description: Setup Google Sheet + task berjadual untuk laporan Meta Ads harian, atau jalankan laporan pagi ini — tarik data semalam dan 7 hari lepas, banding dengan sasaran kos dalam Marketing Brain, beri keputusan (Stop, Tambah bajet, Test angle sama, Angle baru atau Tunggu) untuk setiap iklan aktif dengan sebab, tulis ke Google Sheets, dan beri ringkasan yang boleh dibaca dalam 30 saat. Guna bila pengguna mahu setup laporan iklan pagi, jalankan/uji laporan harian, atau sebut "Task 2 laporan iklan". Read-only — never edits the ad account. Daily Meta Ads report skill: one-time Google Sheet + scheduled-task setup, then a daily read-only report with decision flags written to Sheets.
---

# Meta Ads — Laporan Harian

Lesson 02.8. Skill ini buat analisis iklan (dari `meta-ads-analyst`) berjalan sendiri setiap pagi, dan tulis hasilnya ke Google Sheets supaya pengguna cuma buka satu sheet dan luluskan.

Skill ini ada dua mod:

| Mod | Bila | Hasil |
|---|---|---|
| **Setup** | Google Sheet laporan belum wujud, atau pengguna minta "setup laporan iklan" | Sheet baharu (tab `Harian` + `Ringkasan`) + prompt Task 2 untuk ditampal dalam ChatGPT |
| **Laporan harian** | Task berjadual jalan setiap pagi, atau pengguna minta "jalankan laporan hari ini" | Baris baharu dalam Sheet + ringkasan pendek dalam chat |

## Peraturan umum

- Bercakap dalam bahasa pengguna. Lalai: Bahasa Melayu santai dan jelas.
- **Read-only mutlak.** Skill ini tak boleh stop, hidupkan, edit atau naikkan bajet apa-apa iklan. Ia cuma baca data dan cadang. Sebarang perubahan sebenar kena kelulusan pengguna dalam chat langsung — bukan dalam laporan berjadual.
- Jangan reka data. Kalau satu metrik tiada (contohnya frekuensi tak keluar dari connector), tulis `-` dan sebut dalam ringkasan.
- Data iklan datang dari connector Meta Ads MCP rasmi (`https://mcp.facebook.com/ads`). Jangan andaikan nama tool tertentu — guna apa sahaja tool baca data yang connector itu sediakan.
- Tulis output ke Google Sheets melalui connector Google Drive/Sheets bila tersedia. Kalau task berjadual tak boleh guna connector (masih disahkan guru), **fallback**: keluarkan blok CSV siap format dalam chat + ringkasan biasa, dan beritahu pengguna secara jelas yang ini fallback manual, bukan auto-write.
- Nilai ambang keputusan (RM, hari, dsb.) dalam `references/threshold-keputusan.md` mesti sama dengan skill `meta-ads-analyst`. Kalau pengguna ubah satu, ingatkan mereka ubah yang satu lagi.

## Langkah 0: Baca Marketing Brain

Sebelum apa-apa mod, baca `marketing-brain.md` dari Project — khusus bahagian **6. Iklan**, medan **Sasaran kos**.

- Kalau brain tiada, atau bahagian 6 masih `(belum pasti)`: beritahu pengguna, dan tanya satu soalan: *"Apakah sasaran kos per hasil (RM) anda? Contohnya RM15 untuk satu lead."* Guna nilai itu untuk sesi ini sahaja; cadangkan mereka masukkan ke brain (skill `marketing-brain`) supaya skill lain juga nampak.
- Kalau ada: guna nilai itu sebagai asas semua ambang keputusan (lihat `references/threshold-keputusan.md`).

## Mod Setup (sekali sahaja)

1. **Sahkan nama Sheet.** Cadangkan `Report Iklan – <nama bisnes>` (nama bisnes dari brain). Kalau pengguna sudah ada sheet, guna nama sedia ada dan tambah tab yang tiada.
2. **Bina struktur tab** ikut `references/sheet-format.md` dengan tepat — nama tab, susunan lajur dan format setiap lajur. Tab `Harian` satu baris setiap iklan setiap hari; tab `Ringkasan` satu baris setiap hari.
   - Kalau connector Sheets ada: cipta/kemas kini sheet terus.
   - Kalau tiada: beri jadual markdown struktur tu untuk pengguna cipta sendiri, dan sebut ini fallback.
3. **Beri prompt Task 2.** Salin templat dari `references/prompt-task.md` (Task 2 "Laporan iklan", 7:00 pagi waktu Malaysia). Kalau pengguna sebut dah kena had 5 task (lesson 01.9), beri variant gabungan "Satu task, banyak kerja" dari fail yang sama dan terangkan ia gabung Task 1 (content) + Task 2 (laporan) dalam satu task harian dengan dua bahagian arahan.
4. **Suruh test-run sekali.** Minta pengguna jalankan task itu secara manual sekali (butang "Run now" dalam ChatGPT) sebelum bergantung padanya esok pagi. Sahkan baris pertama masuk dengan betul dalam Sheet sebelum tutup sesi setup.

## Mod Laporan Harian (setiap kali dijalankan)

1. Baca brain (Langkah 0) untuk sasaran kos semasa.
2. **Tarik data** melalui Meta Ads MCP: semua iklan **aktif** sahaja, metrik semalam (tarikh penuh, waktu Malaysia) dan 7 hari lepas (untuk trend frekuensi/CTR).
3. **Kira dan bandingkan** setiap iklan dengan sasaran kos. Guna peraturan dalam `references/threshold-keputusan.md` untuk tandakan satu daripada lima keputusan: **Stop**, **Tambah bajet**, **Test angle sama**, **Angle baru**, atau **Tunggu** (data belum cukup) — dengan sebab satu baris setiap satu (contoh: "Kos per hasil RM32 vs sasaran RM15, 4 hari berturut-turut").
4. **Tambah baris** ke tab `Harian` (satu baris setiap iklan) dan satu baris ringkasan ke tab `Ringkasan`, ikut format dalam `references/sheet-format.md`. Jangan timpa baris lama.
5. **Balas dalam chat** dengan ringkasan pendek yang boleh dibaca dalam 30 saat atas telefon — format dalam `references/sheet-format.md` bahagian "Ringkasan chat": jumlah spend, jumlah hasil, kos per hasil vs sasaran, tiga tindakan utama hari ini, dan apa-apa luar biasa (spend melonjak, delivery berhenti, frekuensi tinggi).
6. **Kalau hari ini Jumaat**, tambah satu baris di penghujung ringkasan mencadangkan satu entri Pengajaran baharu untuk brain (contohnya angle yang konsisten menang/kalah minggu ini), dan rujuk pengguna ke skill `marketing-brain` (tambah ke brain) untuk masukkannya.

## Bila fallback CSV digunakan

Kalau connector Sheets tak boleh ditulis (task berjadual atau sebaliknya), keluarkan:
1. Blok CSV siap format (lajur sama macam tab `Harian`) yang pengguna boleh salin-tampal ke Sheet.
2. Ringkasan chat biasa (Langkah 5 di atas).
3. Satu baris jelas: *"Tak dapat tulis terus ke Google Sheets kali ni — salin blok CSV di atas ke tab Harian secara manual."*

## Contoh

Lihat `examples/contoh-laporan.md` untuk satu ringkasan pagi sebenar (bisnes rekaan "Nasi Lemak Mak Jah", RM).
