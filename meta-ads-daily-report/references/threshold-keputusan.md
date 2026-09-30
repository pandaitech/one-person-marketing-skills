# Ambang keputusan

Peraturan ini **sama persis** dengan `references/thresholds.md` dalam skill `meta-ads-analyst`, supaya laporan pagi dan analisis dalam chat sentiasa beri keputusan yang sama. Kalau pengguna ubah satu nilai, ubah di kedua-dua skill dan sebut dalam balasan.

Semua nilai ialah **gandaan sasaran kos** (brain bahagian **6. Iklan → Sasaran kos**), supaya ia masuk akal untuk apa-apa bajet. Nombor RM tetap daripada pengajar belum muktamad; sunting jadual Config bila sudah ada.

## Config (sunting di sini)

| Pemboleh ubah | Nilai lalai | Makna |
|---|---|---|
| `MIN_DAYS` | 3 hari | Hari minimum iklan/ad set berjalan sebelum boleh dinilai |
| `MIN_SPEND_MULTIPLE` | 2× sasaran kos | Belanja minimum sebelum boleh dinilai |
| `STOP_SPEND_MULTIPLE` | 3× sasaran kos | Belanja minimum sebelum "Stop" boleh dicadang atas sebab tiada result |
| `STOP_COST_MULTIPLE` | 2× sasaran kos | Cost per result yang mencetus "Stop" (stabil, bukan satu hari sahaja) |
| `SCALE_COST_MULTIPLE` | 0.8× sasaran kos | Cost per result yang mencetus "Tambah bajet" |
| `SCALE_STABLE_DAYS` | 3 hari berturut-turut | Tempoh cost per result perlu kekal di bawah `SCALE_COST_MULTIPLE` sebelum tambah bajet |
| `SCALE_INCREASE_PCT` | 20% | Kenaikan bajet setiap kali, tak lebih kerap daripada sekali setiap `SCALE_STABLE_DAYS` |
| `FATIGUE_FREQUENCY` | 2.5 | Frequency yang menandakan creative letih |
| `FATIGUE_CTR_DROP_PCT` | 20% | Penurunan CTR daripada purata 3 hari pertama iklan tu sendiri, yang menandakan creative letih |
| `WEAK_HOOK_CTR` | 1% | CTR di bawah nilai ini sejak awal (bukan penurunan) menandakan hook lemah, bukan creative letih |

Semua "sasaran kos" diambil daripada brain bahagian 6. Kalau brain tiada nilai ini, tanya pengguna satu soalan sebelum meneruskan Mod Keputusan: *"Apa sasaran cost per result (RM) yang masih untung untuk anda?"*

## Susunan semakan (periksa ikut urutan ini untuk setiap iklan/ad set)

1. **Tunggu** — `hari_berjalan < MIN_DAYS` ATAU `spend < MIN_SPEND_MULTIPLE × sasaran_kos`. Terlalu awal untuk nilai. Jangan buat keputusan lain.
2. **Stop** — `spend ≥ STOP_SPEND_MULTIPLE × sasaran_kos` DAN (tiada result langsung ATAU `cost_per_result ≥ STOP_COST_MULTIPLE × sasaran_kos` secara stabil, bukan turun naik satu hari).
3. **Tambah bajet** — `cost_per_result ≤ SCALE_COST_MULTIPLE × sasaran_kos` selama `SCALE_STABLE_DAYS` hari berturut-turut. Naikkan bajet `SCALE_INCREASE_PCT` sahaja setiap kali; jangan naik mendadak.
4. **Test angle sama** — angle ini (kumpulan ikut hook/idea yang sama, bukan satu creative) pernah/sedang mencapai `cost_per_result ≤ 1× sasaran_kos`, TETAPI creative semasa tunjuk tanda letih: `frequency ≥ FATIGUE_FREQUENCY` ATAU CTR turun `≥ FATIGUE_CTR_DROP_PCT` daripada purata 3 hari pertama creative itu sendiri. Angle masih menang — buat creative baru dengan idea yang sama.
5. **Angle baru** — bukan salah satu di atas, dan CTR rendah (`< WEAK_HOOK_CTR`) sejak awal atau tak pernah convert walaupun sudah cukup spend/hari. Masalah pada idea/hook, bukan creative sudah letih.

Nota: bezakan langkah 4 dan 5 dengan teliti — ini titik yang paling ramai tersilap (rujuk lesson 02.7 dalam skrip kelas). Kalau angle tu **pernah** menang dan baru sekarang jatuh, itu creative letih (langkah 4). Kalau angle tu **tak pernah** menang, itu hook bermasalah (langkah 5).

## Tanda luar biasa (untuk "Luar biasa" dalam ringkasan)

Ini bukan salah satu daripada 5 keputusan — ia bendera tambahan yang disertakan dalam ringkasan chat walaupun keputusan iklan itu sendiri okay:

- **Spend melonjak**: spend semalam ≥ **2 × purata harian 7 hari** iklan itu [LALAI].
- **Delivery berhenti**: status masih Aktif tapi spend semalam = RM0.
- **Frekuensi tinggi**: frekuensi ≥ **3.0** [LALAI], walaupun keputusan belum jatuh ke Stop/Test angle sama.
