# Peraturan minimum data dan keputusan

## Mod Belajar dari data — peraturan "menang"/"kalah"

Jangan panggil satu corak "menang" atau "kalah" melainkan ia capai **kedua-dua**:

- Sekurang-kurangnya **RM `[SPEND_MIN]`** (lalai: 3× sasaran kos daripada brain, atau RM150 kalau sasaran kos tiada) dibelanjakan merentasi iklan dalam corak itu, DAN
- Sekurang-kurangnya **5 result** (purchase/lead/message) merentasi iklan dalam corak itu.

Kalau tak cukup, sebut ini dalam laporan dan tulis corak itu sebagai **hipotesis**, bukan kesimpulan — contohnya "Berdasarkan 2 iklan sahaja (belum cukup data), angle X nampak lebih murah..." Jangan cadang tulis ke brain sebagai fakta sehingga cukup data.

# Peraturan keputusan (Mod Keputusan harian/mingguan)

> **Status:** Nombor RM tetap daripada pengajar belum muktamad. Semua nilai di sini dinyatakan sebagai **gandaan sasaran kos** (daripada brain, bahagian 6 "Sasaran kos"), supaya peraturan sama berfungsi untuk apa-apa bajet. Sunting jadual "Config" di bawah bila pengajar beri nombor tetap.

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

## Metrik yang digunakan

Guna metrik hasil bisnes (purchases/leads/messages ikut objective iklan), cost per result, dan ROAS kalau ada. **Jangan** guna metrik vanity (reach, likes, views) sebagai asas keputusan — metrik ini boleh disebut sebagai konteks tambahan sahaja.
