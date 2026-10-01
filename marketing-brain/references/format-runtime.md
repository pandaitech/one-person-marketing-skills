# Runtime: log fail dan format entri

Runtime ialah log **tambah sahaja** (append-only) bagi segala yang berlaku dalam kerja marketing harian — apa yang dijadualkan/di-post, maklum balas pengguna, dan angka prestasi. Ia berbeza daripada brain: brain simpan fakta dan corak yang **sudah disahkan**; runtime simpan **sejarah mentah** yang belum tentu masuk brain.

## Struktur folder

```
<folder kerja marketing>/
  marketing-brain.md        # curated, kecil, dibaca setiap skill setiap kali jalan
  bank-content.md           # idea S-tier daripada rakaman sendiri, dengan status
  bank-kajian.md            # kajian/rujukan A-tier, dengan status
  runtime/
    log-2026-10.md          # satu fail sebulan, tambah sahaja
    log-2026-11.md
```

- **`marketing-brain.md`** — lihat `format-brain.md`.
- **`bank-content.md`** dan **`bank-kajian.md`** — bank idea, format di bawah.
- **`runtime/log-YYYY-MM.md`** — satu fail bagi setiap bulan kalendar. Bila bulan baharu bermula, buka fail baharu (`log-2026-11.md`); jangan sambung dalam fail bulan lama. Kalau folder `runtime/` atau fail bulan semasa belum wujud, cipta ia.

## Peraturan fail runtime

- **Tambah sahaja.** Jangan sunting atau padam entri lama. Betulan pun jadi entri baharu (contohnya maklum balas yang membatalkan entri sebelumnya).
- Setiap entri ialah **satu blok pendek** bermula dengan tajuk `### YYYY-MM-DD HH:MM — <skill atau "pengguna">`.
- Susun ikut tarikh, entri terbaharu di **bawah** (bukan atas macam brain bahagian 7).
- Guna medan `- **Label:** nilai` yang relevan sahaja untuk jenis entri itu — tak perlu isi semua medan setiap kali.

## Format entri: tiga contoh konkrit

### 1. Content dijadualkan/diposkan

```markdown
### 2026-10-03 07:15 — content-repurposer
- **Jenis:** content
- **Sumber:** bank-content.md → "Live IG: kenapa ramai gagal FB Ads bab hook" (baris 4)
- **Platform:** Threads (thread bersiri)
- **Tajuk/hook:** "3 sebab hook FB ads anda gagal — dan bukan sebab bajet"
- **Waktu jadual:** 2026-10-03 08:00
- **Status:** draf
```

Bila status berubah (draf → diluluskan → posted), tambah entri baharu yang rujuk entri asal — jangan sunting entri asal:

```markdown
### 2026-10-03 08:05 — pengguna
- **Jenis:** content
- **Berkaitan:** thread "3 sebab hook FB ads anda gagal" (2026-10-03 07:15)
- **Status:** diluluskan
```

### 2. Maklum balas pengguna

```markdown
### 2026-10-05 21:40 — pengguna
- **Jenis:** maklum balas
- **Berkaitan:** thread "3 sebab hook FB ads anda gagal" (2026-10-03)
- **Nota:** "Hook ni lemah, terlalu panjang. Jangan guna perkataan 'bajet' dalam hook."
```

### 3. Prestasi (content atau iklan)

```markdown
### 2026-10-06 09:00 — meta-ads-daily-report
- **Jenis:** prestasi
- **Item:** Iklan "Angle Ibu Bekerja" (FB, objective Messages)
- **Metrik:** Spend RM180, 22 result, kos/result RM8.18 (sasaran RM15)
- **Waktu post/run:** pagi (7:30–9:00)
- **Keputusan:** Tambah bajet
```

Medan lain yang boleh guna ikut keperluan: `Platform`, `Pillar`, `Angle`, `Format`, `Views/Reach`, `Engagement`, `Cost per result`, `Hari berjalan`.

## Format bank idea

### `bank-content.md` — idea S-tier daripada rakaman/pengalaman sendiri

Jadual markdown, satu baris satu idea:

```markdown
| Tarikh rekod | Sumber | Idea/topik | Kenapa S-tier | Status |
|---|---|---|---|---|
| 2026-09-20 | Live IG 2026-09-18 | Kenapa ramai gagal FB Ads bab hook, bukan bajet | Pengalaman sebenar, ramai tanya dalam komen | belum guna |
| 2026-09-22 | Sembang dengan pelanggan tetap | Cerita pelanggan yang mula jual guna WhatsApp sahaja | Bukti sosial, spesifik, ada angka | dah guna 2026-10-03 |
```

Lajur **Status**: `belum guna` atau `dah guna YYYY-MM-DD` (tarikh ia dipakai kali terakhir — satu idea boleh dipakai lebih sekali dengan angle berbeza, kemas kini tarikh setiap kali).

### `bank-kajian.md` — kajian/rujukan A-tier

```markdown
| Tarikh rekod | Tajuk kajian | Penulis/Tahun | Dapatan utama | Link/citation | Status |
|---|---|---|---|---|---|
| 2026-09-15 | Attention spans in short-form video | Ismail & Tan, 2025 | 3 saat pertama tentukan 60% kekal tonton | https://... | belum guna |
```

Lajur **Status** sama format macam `bank-content.md`.

## Bila skill tulis ke bank

Selepas skill content guna satu item daripada bank (`bank-content.md` atau `bank-kajian.md`), kemas kini lajur **Status** baris itu jadi `dah guna YYYY-MM-DD` (tarikh hari ini) — dalam pass yang sama dengan menulis entri runtime. Kalau AI tak boleh tulis fail terus, beri baris jadual yang dikemas kini untuk pengguna tampal sendiri.

## Peraturan baca runtime untuk skill content

**Skill content jangan sekali-kali baca runtime penuh.** Sebelum mula kerja, baca **tajuk dan topik/hook sahaja** daripada entri **14 hingga 28 hari lepas** (cukup fail bulan semasa, dan fail bulan lepas kalau tarikh 14–28 hari jatuh merentasi dua bulan) — tujuannya semata-mata elak ulang topik/hook yang sama. Jangan proses medan lain (metrik, maklum balas penuh) pada langkah ini; itu kerja mod "Kemas kini brain dari runtime" dalam skill `marketing-brain`.

## Penamaan fail bulanan

`runtime/log-YYYY-MM.md`, contohnya `runtime/log-2026-10.md` untuk Oktober 2026. Guna bulan kalendar semasa entri ditulis (waktu Malaysia), bukan bulan yang dirujuk oleh kandungan entri.
