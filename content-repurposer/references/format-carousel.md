# Skema data `carousel-preview.html`

Paparan carousel (`assets/carousel-preview.html`) membaca JSON dalam `<script id="carousel-data" type="application/json">`. JSON mesti sah (tiada trailing comma, semua string dalam petikan berganda).

## Bentuk

```json
{
  "business": "Nama Bisnes",
  "accent": "#7A3E7A",
  "slides": [
    { "number": 1, "type": "hook", "text": "Baris hook slide 1" },
    { "number": 2, "type": "value", "text": "Idea slide 2" },
    { "number": 7, "type": "cta", "text": "Ajakan bertindak" }
  ],
  "caption": "Caption penuh untuk post Instagram, termasuk CTA"
}
```

## Peraturan medan

- `accent`: kod warna hex pilihan, daripada brain kalau ada. Kosongkan (`""`) atau buang medan ini untuk guna warna neutral lalai paparan.
- `slides`: susun ikut `number` menaik, mula dari 1. Lalai 7 slide, tapi boleh kurang/lebih ikut permintaan pengguna.
- `type`: satu daripada `"hook"`, `"value"`, `"cta"`. Guna untuk label kecil pada kad (contohnya slide hook ditanda berbeza daripada slide value).
- `text`: teks slide sahaja (bukan caption). Pendek — ini yang tersiar di atas gambar/reka bentuk sebenar.
- `caption`: caption penuh post, berasingan daripada teks slide.

## Ciri paparan

- Slide dipaparkan sebagai kad nisbah 4:5 dalam baris boleh scroll/swipe, nombor slide jelas pada setiap kad.
- Reka bentuk neutral-brand; guna `accent` untuk aksen warna (nombor slide, sempadan) kalau diberi.
- Butang "salin semua teks" hasilkan teks bersih semua slide + caption, untuk tampal ke tool design (Canva/Figma) atau untuk rekod.
- JSON tak sah: paparan tunjuk mesej ralat, bukan skrin kosong.
