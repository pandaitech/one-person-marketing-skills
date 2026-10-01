# Format data untuk `assets/audit-report.html`

Paparan membaca satu blok JSON dalam `<script id="meta-ads-audit-data" type="application/json">`. 7 seksyen, setiap satu objek top-level opsyenal — kalau satu seksyen tiada dalam JSON (atau array dalamnya kosong), paparan tunjuk chip "tiada data" untuk bahagian itu sahaja, bukan error.

Semua medan RM ialah nombor (tanpa simbol `RM`, tanpa koma). Medan yang tiada data: tinggalkan keluar sepenuhnya (jangan tulis `null` atau reka angka). Setiap seksyen boleh ada `"insight"` (satu ayat, dipaparkan terus) dan `"detail"` (teks lebih panjang, disembunyikan di belakang "Lihat butiran").

```json
{
  "mode": "audit",
  "business": "Nama bisnes",
  "produk": "Nama produk/kempen yang diaudit",
  "filter": "Ayat pendek filter yang digunakan (nama kempen atau landing link)",
  "currency": "RM",
  "period": { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD", "days": 0 },
  "price": 149,
  "gross_profit_per_sale": 149,
  "assumptions": ["Ayat pendek setiap andaian yang digunakan untuk kira sasaran kos"],

  "gambaran": {
    "spend": 0,
    "result": 0,
    "cost_per_result": 0,
    "roas": 0,
    "monthly": [
      { "label": "Mac 2025", "spend": 0, "cost_per_result": 0 }
    ],
    "insight": "Satu ayat insight",
    "detail": "Teks lebih panjang untuk toggle"
  },

  "struktur": {
    "campaigns": 0,
    "adsets": 0,
    "ads": 0,
    "objectives": [ { "label": "Jualan", "count": 0 } ],
    "budget_type": [ { "label": "ABO", "count": 0 }, { "label": "CBO", "count": 0 } ],
    "insight": "...",
    "detail": "..."
  },

  "iklan_terbaik_terburuk": {
    "ignore_spend_below": 50,
    "best": [
      { "name": "Nama iklan", "cost_per_result": 0, "spend": 0, "result": 0, "thumbnail": "https://..." }
    ],
    "worst": [
      { "name": "Nama iklan", "cost_per_result": 0, "spend": 0, "result": 0, "thumbnail": "https://..." }
    ],
    "insight": "...",
    "detail": "..."
  },

  "corak_menang": {
    "rows": [
      { "hook": "Demo perbandingan", "format": "Video demo", "tawaran": "Sekali bayar", "market": "Indonesia", "audience": "Broad 18-55" }
    ],
    "insight": "...",
    "detail": "..."
  },

  "titik_perubahan": {
    "monthly": [
      { "label": "Mac 2025", "cost_per_result": 0, "frequency": 0, "ctr": 0 }
    ],
    "markers": [
      { "label": "Sep 2025", "reason": "creative_letih", "note": "Ayat pendek sebab" }
    ],
    "insight": "...",
    "detail": "..."
  },

  "pembaziran": {
    "total_wasted": 0,
    "items": [ { "name": "Nama iklan", "spend": 0 } ],
    "insight": "...",
    "detail": "..."
  },

  "kesimpulan": {
    "lessons": ["Ayat pendek 1", "Ayat pendek 2", "Ayat pendek 3"],
    "target_cost_per_result": { "value": 0, "basis": "Ayat pendek macam mana nombor ni dikira" },
    "ideas": [ { "title": "Tajuk idea", "desc": "Ayat pendek" } ]
  }
}
```

## Nota setiap seksyen

- **gambaran**: 4 kad nombor besar (`spend`, `result`, `cost_per_result`, `roas`). `roas` opsyenal — tinggalkan keluar kalau ia mengelirukan (contohnya anomali satu kempen). `monthly` jana carta garis+bar (belanja sebagai bar, kos/result sebagai garis).
- **struktur**: `objectives` dan `budget_type` (ABO vs CBO) jadi bar berlapis mengikut nisbah; `campaigns`/`adsets`/`ads` jadi chip nombor.
- **iklan_terbaik_terburuk**: hantar maksimum 5 setiap senarai (`best` disusun termurah dahulu, `worst` termahal dahulu). `ignore_spend_below` ialah ambang spend (RM) yang sudah ditapis sebelum pilih senarai ini — letak nombor sebenar yang digunakan supaya paparan boleh nyatakan ia. `thumbnail` opsyenal; kalau URL gagal dimuat, paparan tunjuk kotak kosong automatik.
- **corak_menang**: setiap baris dalam `rows` ialah tag/ikon ringkas sahaja (satu atau dua perkataan setiap medan) — jangan tulis ayat dalam medan `hook`/`format`/dll.
- **titik_perubahan**: `markers.label` mesti sama ejaan dengan satu `monthly[].label` supaya garis penanda sejajar pada bulan yang betul. `reason` salah satu: `creative_letih | harga | musim | audience`; `note` ialah label pendek (bukan ayat penuh) yang dipaparkan dalam chip.
- **pembaziran**: `total_wasted` = jumlah RM dibelanja pada iklan/ad set tanpa result langsung. `items` ialah iklan paling membazir, disusun tertinggi dahulu.
- **kesimpulan**: `lessons` tepat 3 ayat pendek. `target_cost_per_result.basis` terangkan sumber nombor (contohnya peratus daripada `gross_profit_per_sale`) — ini medan yang paling kerap jadi andaian, jadi nyatakan dengan jelas. `ideas` tepat 3 kad idea iklan baru.

Jangan tambah medan yang tidak disebut di sini tanpa kemas kini `assets/audit-report.html` sekali.
