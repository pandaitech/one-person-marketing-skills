# Format Google Sheet "Report Iklan"

Sheet ini ada dua tab. Nama tab dan nama lajur mesti **tepat** seperti di bawah — jangan tambah, buang atau susun semula lajur. Task berjadual dan laporan akan datang bergantung pada susunan ini kekal sama setiap hari.

## Tab `Harian`

Satu baris setiap iklan, setiap hari. Baris baharu ditambah di **bawah** baris sedia ada (jangan timpa).

| Lajur | Format | Contoh |
|---|---|---|
| `tarikh` | YYYY-MM-DD (tarikh data, bukan tarikh laporan dijalankan) | 2026-09-29 |
| `campaign` | nama campaign, apa adanya dari Meta Ads | Promo Raya – Sales |
| `ad set` | nama ad set | Angle Harga |
| `ad` | nama ad/creative | Video – Testimoni Aminah |
| `spend` | nombor RM, 2 titik perpuluhan, tanpa simbol `RM` dalam sel | 87.50 |
| `hasil` | bilangan result (ikut objective: lead/purchase/message) | 4 |
| `kos per hasil` | nombor RM, 2 titik perpuluhan; tulis `-` kalau hasil = 0 | 21.88 |
| `CTR` | peratus, 1 titik perpuluhan, dengan simbol `%` | 1.8% |
| `frekuensi` | nombor, 1 titik perpuluhan; tulis `-` kalau tiada dari connector | 2.4 |
| `keputusan` | satu daripada: `Stop`, `Tambah bajet`, `Test angle sama`, `Angle baru`, `Tunggu` | Tambah bajet |
| `sebab` | satu ayat pendek, angka konkrit | Kos per hasil RM12 vs sasaran RM15, stabil 4 hari |

## Tab `Ringkasan`

Satu baris setiap hari (gabungan semua iklan aktif hari itu).

| Lajur | Format | Contoh |
|---|---|---|
| `tarikh` | YYYY-MM-DD | 2026-09-29 |
| `jumlah spend` | RM, 2 titik perpuluhan | 412.30 |
| `jumlah hasil` | nombor bulat | 19 |
| `kos per hasil purata` | RM, 2 titik perpuluhan | 21.70 |
| `sasaran kos` | RM, dari brain, untuk rujukan pantas dalam sheet | 15.00 |
| `bil. iklan aktif` | nombor bulat | 6 |
| `bil. Stop` | nombor bulat | 1 |
| `bil. Tambah bajet` | nombor bulat | 2 |
| `bil. Test angle sama` | nombor bulat | 1 |
| `bil. Angle baru` | nombor bulat | 1 |
| `bil. Tunggu` | nombor bulat | 1 |
| `catatan` | luar biasa hari ini (spend melonjak, delivery berhenti, dll.), `-` kalau tiada | Ad "Video Testimoni" frekuensi 4.1 |

## Fallback CSV (tab `Harian`)

Kalau connector Sheets tak boleh menulis, keluarkan blok ini dalam chat, lajur sama seperti tab `Harian`, dipisah koma, baris pertama header:

```csv
tarikh,campaign,ad set,ad,spend,hasil,kos per hasil,CTR,frekuensi,keputusan,sebab
```

## Ringkasan chat (setiap run)

Format pendek, boleh dibaca dalam 30 saat atas telefon. Guna struktur ini (bukan jadual penuh):

```
Laporan iklan <tarikh> — <nama bisnes>

Spend: RM<jumlah> | Hasil: <jumlah> | Kos per hasil: RM<purata> (sasaran RM<sasaran>)

Tindakan hari ini:
1. <ad/angle> — <keputusan>: <sebab ringkas>
2. <ad/angle> — <keputusan>: <sebab ringkas>
3. <ad/angle> — <keputusan>: <sebab ringkas>

Luar biasa: <senarai pendek, atau "Tiada">
```

Hadkan "Tindakan hari ini" kepada tiga yang paling penting (Stop dan Angle baru diutamakan berbanding Tunggu). Kalau lebih daripada tiga iklan perlukan tindakan, sebut baki dalam satu baris ringkas ("+2 lagi dalam sheet").

Pada hari Jumaat, tambah satu baris di hujung:

```
Cadangan brain minggu ini: <satu ayat pengajaran> — masukkan via skill marketing-brain.
```
