# Skema data `campaign-plan.html`

Paparan `assets/campaign-plan.html` baca satu objek JSON di dalam `<script id="meta-ads-strategist-data" type="application/json">`. Ikut skema ini dengan tepat — nama medan (key) mesti sama, kerana skrip paparan baca key tersebut secara literal.

## Peraturan

- JSON sah sahaja (double quote untuk semua string dan key, tiada koma berlebihan).
- `bajet.mata_wang` selalunya `"RM"`.
- Setiap teks yang boleh disalin (hook, teks_utama, headline) mesti string biasa, bukan array bersarang, supaya butang salin berfungsi.
- `struktur.kempen` mesti ada **satu entri untuk setiap angle** dalam array `angles` (susunan sama), sebab paparan pautkan campaign ke angle ikut index.
- Medan yang berasal daripada anggaran (bukan brain atau jawapan pengguna terus) disenaraikan juga dalam `andaian`, ditulis dalam ayat penuh supaya pengguna faham konteksnya tanpa perlu buka semula bahagian lain.
- Kalau sesuatu benar-benar tiada (contohnya brief video belum siap), tulis string kosong `""`, jangan buang key tersebut — paparan jangkakan semua key wujud.

## Templat

```json
{
  "bisnes": "<nama bisnes>",
  "tarikh": "YYYY-MM-DD",
  "objective": {
    "pilihan": "<Messages / Leads / Sales / Traffic>",
    "sebab": "<1-2 ayat>"
  },
  "bajet": {
    "bulanan": 900,
    "test_harian_setiap_kempen": 10,
    "mata_wang": "RM"
  },
  "tempoh_test": {
    "minimum_hari": 4,
    "minimum_belanja_setiap_iklan": 40,
    "andaian": true
  },
  "struktur": {
    "label": "3 x kempen 1-1-1 (setiap angle kempen berasingan, bajet sama rata)",
    "konsep": "Konsep A — agih bajet sama rata semasa test",
    "kempen": [
      {
        "nama": "<nama kempen, contoh: Test - Jimat masa pagi>",
        "angle_rujukan": "<nama angle yang sepadan>",
        "objective": "<sama seperti objective.pilihan>",
        "bajet_jenis": "CBO",
        "bajet_harian": 10,
        "ad_set": {
          "nama": "<nama ad set>",
          "sasaran": "<ringkasan targeting daripada audience brain>",
          "iklan": {
            "nama": "<nama iklan>",
            "angle": "<nama angle yang sepadan>"
          }
        }
      }
    ]
  },
  "angles": [
    {
      "nama": "<nama angle>",
      "kepercayaan_disasar": "<apa pelanggan percaya sekarang yang angle ni cuba ubah>",
      "hooks": ["<hook 1>", "<hook 2>", "<hook 3>"],
      "teks_utama": "<primary text, 2-4 ayat>",
      "headline": "<headline pendek>",
      "brief_kreatif": {
        "imej": "<apa nak ditunjuk dalam imej>",
        "video": "<apa nak ditunjuk dalam video>"
      }
    }
  ],
  "ukuran": {
    "apa_dipantau": ["CTR", "Kos per hasil", "Frequency"],
    "bila_nilai": "<ayat ringkas gabung minimum_hari dan minimum_belanja_setiap_iklan>",
    "langkah_seterusnya": "Guna skill meta-ads-analyst untuk keputusan stop, tambah bajet, angle sama atau angle baharu."
  },
  "checklist": [
    "<item checklist 1>",
    "<item checklist 2>"
  ],
  "andaian": [
    "<ayat penuh tentang satu andaian, contoh: Sasaran kos RM12 per mesej ialah anggaran daripada margin produk, sahkan lepas dapat data sebenar>"
  ],
  "cadangan_brain": [
    "<ayat tentang apa nak tambah/ubah dalam bahagian 6 Iklan pada marketing-brain.md>"
  ]
}
```

## Nota

- `struktur.kempen[i]` dan `angles[i]` mesti pada index yang sama — paparan tidak padankan ikut nama, tapi ikut kedudukan dalam array.
- Kalau bilangan angle bukan 3 (contohnya pengguna minta 2 sahaja), skema tetap sah selagi panjang `angles` dan `struktur.kempen` sama.
- `bajet.test_harian_setiap_kempen` ialah bajet **untuk satu kempen**, bukan jumlah semua kempen. Jumlah harian keseluruhan = `test_harian_setiap_kempen` × bilangan kempen.
