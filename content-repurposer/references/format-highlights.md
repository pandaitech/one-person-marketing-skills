# Skema data `highlight-picker.html`

Paparan pemilih highlight (`assets/highlight-picker.html`) membaca JSON dalam `<script id="highlight-data" type="application/json">`. JSON mesti sah (tiada trailing comma, semua string dalam petikan berganda).

## Bentuk

```json
{
  "business": "Nama Bisnes",
  "source": "Nama/tarikh rakaman asal, contohnya \"Live Instagram 12 Mac\"",
  "highlights": [
    {
      "rank": 1,
      "start": "00:12:34",
      "end": "00:13:40",
      "hook": "Baris 3 saat pertama",
      "why": "Sebab ia menarik, satu ayat",
      "on_screen_text": "Teks cadangan di skrin",
      "caption": "Caption penuh dengan CTA",
      "pillar": "Nama content pillar daripada brain"
    }
  ]
}
```

## Peraturan medan

- `rank`: nombor 1 = paling kuat. Guna untuk susunan lalai senarai.
- `start` / `end`: format `HH:MM:SS` atau `MM:SS`, ikut apa yang ada dalam transkrip.
- `hook`, `why`, `on_screen_text`, `caption`: teks bebas, boleh kosong string `""` kalau benar-benar tiada, tapi elak — cuba isi semua medan.
- `pillar`: guna nama pillar yang sama seperti dalam brain bahagian 5, supaya penapis pillar dalam paparan berguna. Kalau tiada dalam brain, tulis label ringkas sendiri.
- Susunan array `highlights` tidak penting; paparan susun ikut `rank`.
- Minimum satu highlight. Tiada had maksimum, tapi lalai skill ialah lebih kurang 10.

## Ciri paparan

- Senarai kad, satu kad satu highlight, tunjuk timestamp, hook, why, on-screen text, caption, pillar.
- Checkbox pilih setiap kad, butang "salin dipilih" hasilkan senarai teks bersih (timestamp + hook) untuk dihantar kepada editor.
- Penapis ikut pillar (chip di atas senarai).
- JSON tak sah: paparan tunjuk mesej ralat, bukan skrin kosong.
