# Format data untuk `assets/decision-table.html`

Paparan membaca satu blok JSON dalam `<script id="meta-ads-analyst-data" type="application/json">`. Satu fail paparan sama digunakan untuk dua mod; medan `"mode"` tentukan susun atur. Jangan tambah medan yang tidak disebut di sini tanpa kemas kini `assets/decision-table.html`.

Semua medan RM ialah nombor (tanpa simbol `RM`, tanpa koma). Medan yang tiada data: tinggalkan keluar sepenuhnya (jangan tulis `null` atau reka angka).

## Mod "belajar" (Mod 1: Belajar dari data)

```json
{
  "mode": "belajar",
  "business": "Nama bisnes",
  "period": { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD", "days": 90 },
  "result_metric": "Purchase | Lead | Message",
  "min_data_rule": "Ayat pendek peraturan minimum spend/result yang digunakan",
  "summary": {
    "ads_reviewed": 0,
    "winning_patterns": 0,
    "losing_patterns": 0,
    "hypotheses": 0
  },
  "winning_patterns": [
    {
      "title": "Ringkasan corak dalam satu ayat",
      "dimension": "angle | format | tawaran | audience | placement",
      "evidence": "Ayat bukti dengan angka: spend, result, cost per result",
      "is_hypothesis": false,
      "sample_ads": ["Nama iklan 1", "Nama iklan 2"]
    }
  ],
  "losing_patterns": [
    { "title": "...", "dimension": "...", "evidence": "...", "is_hypothesis": false, "sample_ads": ["..."] }
  ],
  "brain_suggestions": {
    "add": ["Baris untuk ditambah pada brain, dengan bahagian yang terlibat"],
    "change": ["..."],
    "remove": ["..."]
  }
}
```

## Mod "keputusan" (Mod 2: Keputusan harian/mingguan)

```json
{
  "mode": "keputusan",
  "business": "Nama bisnes",
  "currency": "RM",
  "target_cost_per_result": 12,
  "period": { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD", "days": 7 },
  "summary": { "stop": 0, "tambah_bajet": 0, "test_angle_sama": 0, "angle_baru": 0, "tunggu": 0 },
  "items": [
    {
      "name": "Nama iklan atau ad set",
      "level": "ad | ad set",
      "angle": "Nama angle/hook (untuk kumpulkan test_angle_sama vs angle_baru)",
      "days_running": 5,
      "spend": 45,
      "results": 3,
      "cost_per_result": 15,
      "frequency": 1.8,
      "ctr": 1.4,
      "decision": "stop | tambah_bajet | test_angle_sama | angle_baru | tunggu",
      "signal": "Metrik/nombor yang mencetus keputusan, contohnya 'CPR RM30, 2.5x sasaran, stabil 3 hari'",
      "reason": "Ayat pendek sebab, rujuk peraturan dalam references/thresholds.md"
    }
  ],
  "action_list": [
    "Nama iklan — Keputusan: sebab ringkas"
  ]
}
```

`action_list` ialah versi teks pendek `items` untuk butang salin (satu baris setiap iklan). Jana ia daripada `items`, tapi tulis eksplisit supaya paparan tak perlu format semula ayat.
