# Skema data `assets/carousel.html`

Paparan carousel (`assets/carousel.html`) membaca JSON dalam
`<script id="carousel-data" type="application/json">`. JSON mesti sah (tiada
trailing comma, semua string dalam petikan berganda, `\n` untuk baris baharu
dalam teks panjang).

Setiap slide dalam paparan ini ialah **kanvas 1080×1350 sebenar** (bukan kad
teks ringkas) — apa yang nampak dalam preview ialah apa yang keluar dalam PNG.

## Bentuk penuh

```json
{
  "business": "Nama Bisnes",
  "topic": "Tajuk carousel untuk tab/preview",
  "theme": {
    "background": "#F7F4EC",
    "surface": "#FFFFFF",
    "ink": "#1B1B18",
    "body_color": "#3A3A34",
    "muted": "#8A8578",
    "accent": "#C1502E",
    "heading_font": "Fraunces",
    "body_font": "Inter",
    "layout_style": "listicle",
    "align": "left",
    "decorative": "corner-mark"
  },
  "slides": [
    {
      "number": 1,
      "layout": "cover",
      "role": "hook",
      "kicker": "UNTUK PEKEBUN DURIAN",
      "headline": "Tanah anda 'lapar'. Ini tanda dia.",
      "body": "5 tanda tanah kurang nutrien — dan apa nak buat.",
      "credit": null
    }
  ],
  "caption": "Caption penuh untuk post Instagram, termasuk CTA."
}
```

## Medan tahap-atas

| Medan | Wajib | Nota |
|---|---|---|
| `business` | ya | Nama bisnes/akaun; keluar di footer setiap slide dan nama fail ZIP. |
| `topic` | tidak | Tajuk carousel, untuk title tab preview sahaja. |
| `theme` | ya | Lihat **Theme** di bawah. Kosongkan medan individu untuk guna lalai neutral. |
| `slides` | ya | Array slide, susun ikut `number` menaik mula dari 1. Biasanya 6–9 slide. |
| `caption` | tidak | Caption penuh post, berasingan daripada teks slide. |

## `theme`

| Medan | Nilai | Nota |
|---|---|---|
| `background` | hex | Warna latar setiap slide. |
| `surface` | hex | Warna permukaan sekunder (kad dalam slide, cth. kotak `source_note`). |
| `ink` | hex | Warna teks utama (headline). |
| `body_color` | hex | Warna teks body/paragraf. |
| `muted` | hex | Warna teks kecil (footer, credit, label). |
| `accent` | hex | Warna aksen (kicker, nombor list, stat, CTA pill, hiasan). |
| `heading_font` | satu daripada senarai di bawah | Font headline/kicker/nombor. |
| `body_font` | satu daripada senarai di bawah | Font body/footer/credit. |
| `layout_style` | `listicle` \| `story` \| `data-stats` \| `how-to` \| `clean` | Lihat kesan di `references/style-reference.md`. `clean` matikan semua hiasan. |
| `align` | `left` \| `center` | Penjajaran teks utama. |
| `decorative` | `none` \| `torn-edge` \| `halftone-dot` \| `corner-mark` \| `underline` | Elemen hiasan CSS sahaja (tiada imej binari). |

Font yang disokong (dimuat terus dari Google Fonts dalam fail, tiada muat turun
lain diperlukan): **heading** — `Fraunces`, `Playfair Display`,
`DM Serif Display`, `Lora`, `Space Grotesk`, `Poppins`, `Archivo`, `Inter`,
`Work Sans`, `Nunito Sans`. **body** — sama senarai (biasanya pilih yang lebih
neutral seperti `Inter`, `Work Sans`, `Nunito Sans`, `Lora`). Nama mesti tepat
seperti senarai; nama lain jatuh balik ke `Fraunces`/`Inter`.

Kalau pengguna beri rujukan gaya (screenshot carousel), isi `theme` daripada
token yang diekstrak — lihat `references/style-reference.md`. Kalau tiada
rujukan, guna warna brand dari `marketing-brain.md` bahagian 2; kalau brain pun
tiada warna, biarkan lalai neutral di atas.

## `slides[]`

Setiap slide kongsi medan asas ini, dan medan khusus ikut `layout`:

| Medan | Guna dalam layout | Nota |
|---|---|---|
| `number` | semua | Nombor slide, mula 1, menaik tanpa lompat. |
| `layout` | semua | Satu: `cover`, `big-text`, `list`, `stat`, `quote`, `source`, `cta`. |
| `role` | semua (metadata) | `hook`, `orientation`, `mechanism`, `evidence`, `tradeoff`, `resolution`, `cta`, dsb. Tak dipaparkan; untuk rekod/edit sahaja. |
| `kicker` | semua (opsyenal) | Label kecil atas headline, cth. nama pillar atau "SUMBER". |
| `headline` | cover, big-text, list, cta, source | Teks utama besar. Sokong `\n` untuk baris baharu. |
| `body` | cover, big-text, stat, cta | Perenggan sokongan pendek. |
| `items` | list | Array string, satu per baris list. |
| `stat_value` | stat | Angka/teks besar (cth. `"73%"`, `"2×"`). |
| `stat_label` | stat | Label di bawah nombor. |
| `quote` | quote | Teks quote (fallback ke `headline` jika kosong). |
| `attribution` | quote | Nama/sumber quote. |
| `source_note` | source | Teks citation penuh (pengarang, tahun, tajuk kajian/artikel, atau link). |
| `cta_label` | cta | Teks pil CTA pendek (cth. "DM 'TANAH' sekarang"). |
| `credit` | semua (opsyenal) | Citation kecil di bawah content, cth. `"Rujukan: Zhang et al. 2023 (contoh)"`. |

### Layout → medan yang dipakai

| `layout` | Guna untuk | Medan utama |
|---|---|---|
| `cover` | Slide 1, hook | `kicker`, `headline`, `body` (headline besar 96px; ada hint "Swipe →" jika slide pertama) |
| `big-text` | Satu idea/insight per slide | `kicker`, `headline`, `body` |
| `list` | Senarai langkah/tanda/sebab | `kicker`, `headline`, `items[]` (auto-nombor; jika `layout_style: "how-to"`, label jadi "Langkah N") |
| `stat` | Angka/statistik fokus | `kicker`, `stat_value`, `stat_label`, `body` |
| `quote` | Petikan/testimoni/kutipan sumber | `quote`, `attribution` |
| `source` | Slide citation kajian/artikel | `kicker` (lalai "Sumber"), `headline`, `source_note` |
| `cta` | Slide penutup ajakan bertindak | `kicker`, `headline`, `body`, `cta_label` |

## Peraturan

- `slides`: susun ikut `number` menaik, mula dari 1. Biasanya 6–9, ikut permintaan pengguna atau hasil semakan kualiti.
- Elakkan aksara `</script` mentah dalam nilai teks.
- Untuk sumber kajian/penyelidikan: mesti ada satu slide `layout: "source"` dengan citation penuh dalam `source_note`, dan `caption` turut sebut citation ringkas. Jangan reka angka/penemuan yang tiada dalam kajian.
- Teks pada slide mesti pendek — ikut band ketumpatan di `references/plan-and-gates.md` (short/medium/long); `overfull` mesti dipendekkan atau dipecah sebelum render.

## Ciri paparan

- Setiap kad ialah kanvas 1080×1350 sebenar, dikecilkan untuk preview (scroll/swipe rail).
- Butang **PNG** bawah setiap kad — eksport slide itu sahaja pada resolusi penuh.
- Butang **Muat turun semua (ZIP)** atas — eksport semua slide sebagai satu fail `.zip`.
- Butang **Salin caption** — salin `caption` (atau ringkasan slide jika `caption` kosong).
- Guna `html-to-image` dan `JSZip` dari cdnjs.cloudflare.com; jika sekatan persekitaran (cth. sandbox canvas ChatGPT/Claude) menghalang eksport, paparan tunjuk banner amaran dan cadangkan screenshot manual — ia tidak gagal senyap.
- JSON tak sah: paparan tunjuk mesej ralat, bukan skrin kosong.

## Cara hasilkan paparan

1. Salin `assets/carousel.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali kandungan dalam blok `<script id="carousel-data" type="application/json"> ... </script>`.
2. Ganti dengan JSON sah ikut skema di atas.
3. Paparkan sebagai HTML:
   - **Claude:** cipta artifact HTML.
   - **ChatGPT:** buka dalam canvas dan tekan Preview.
   - Kalau HTML tidak boleh dipaparkan, beri fail `.html` untuk dimuat turun dan dibuka dalam browser.

Jangan tulis semula paparan dari kosong dan jangan buang bahagian skrip —
butang eksport/salin dalam paparan bergantung padanya.
