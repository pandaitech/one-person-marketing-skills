# Kebenaran visual, ratio teks:seni, dan margin selamat

Rujukan reka bentuk untuk setiap slide — apa jenis "visual" (kalau ada) yang
slide itu perlukan, dan bagaimana `assets/carousel.html` melayankan ruang
teks vs elemen seni pada kanvas 1080×1350.

## Peranan kebenaran visual

Untuk setiap slide, putuskan secara berasingan:

1. **Truth role** — `evidence` (bukti sebenar), `context` (rujukan awam untuk
   konteks sahaja) atau `no_visual` (tipografi sahaja sudah cukup).
2. **Presentation intent** — `proof`, `explanation` atau `teaser`.
3. **Kind** — `real-reference` (screenshot/imej sebenar pengguna bekalkan),
   `generated-explanation` (imej dijana AI untuk terangkan konsep) atau
   `typography-only` (tiada imej, reka bentuk `carousel.html` sahaja).

**Peraturan paling penting: imej yang dijana AI bukan bukti.** Jangan sekali-kali
guna `generated-explanation` sebagai `evidence` untuk dakwaan produk/hasil/angka
sebenar. Kalau pengguna nak tunjuk hasil sebenar (screenshot, before/after,
dashboard), itu mesti `real-reference` daripada aset pengguna sendiri — minta
versi yang sudah dibersihkan (tiada kata laluan, token, data peribadi pelanggan).
Kalau pengguna tiada aset sebenar, turunkan ke `context` atau `no_visual`;
jangan buat imej rekaan nampak macam bukti.

Guna `no_visual`/`typography-only` bila imej hanya akan jadi hiasan generik atau
mengganggu — kata pada pengguna: "Slide ni tak perlu visual, tipografi dah
cukup kuat", bukan paksa setiap slide ada 'gambar'.

## Ratio teks : seni ikut layout

`assets/carousel.html` sendiri IALAH visual (tipografi + warna + hiasan CSS) —
tiada keperluan jana imej luar untuk mod lalai. Setiap `layout` dalam skema
JSON (lihat `format-carousel.md`) sudah bawa nisbah teks:ruang yang sesuai:

| `layout` | Bila guna | Teks : ruang seni |
|---|---|---:|
| `cover` | Hook/cover, satu headline besar | 55 : 45 |
| `big-text` | Satu insight/idea, tiada senarai | 70 : 30 |
| `list` | Senarai langkah/tanda/sebab | 65 : 35 |
| `stat` | Fokus satu angka/statistik | 45 : 55 (nombor besar = elemen visual utama) |
| `quote` | Petikan/testimoni | 60 : 40 |
| `source` | Citation kertas kajian/artikel | 75 : 25 |
| `cta` | Slide penutup ajakan | 60 : 40 |

Kalau mod pilihan **penjanaan imej** digunakan (lihat
`image-generation-chatgpt.md`), imej yang dijana jadi latar/elemen seni bagi
ruang "seni" di atas — teks tetap dilapis oleh `carousel.html` atau disalin
tepat ke dalam prompt imej ikut templat di rujukan itu. Lebih 100 perkataan
pada satu slide ialah masalah ketumpatan copy, bukan sesuatu yang diselesaikan
dengan pilih layout lain — pendekkan atau pecah slide (lihat
`plan-and-gates.md`).

## Margin selamat 1080×1350 (dibina dalam `carousel.html`)

- Margin sisi: sekurang-kurangnya 72px.
- Margin atas: sekurang-kurangnya 64px.
- Zon footer (nama bisnes + nombor slide): 96px.
- Saiz minimum kicker/label: 28px — mesti jelas dibaca pada skrin telefon dalam
  feed, bukan label kecil yang perlu zoom.
- Saiz headline auto-fit ikut panjang teks (headline pendek dapat fon paling
  besar, headline panjang kecil sedikit supaya tak overflow) — `cover` 74–128px,
  layout lain (big-text/list/cta) 64–112px, `quote` 52–88px. Jangan tetapkan
  headline pada satu saiz tetap secara manual; biar auto-fit `carousel.html`
  yang putuskan berdasarkan panjang teks.
- Saiz minimum body/list/source-note: 38px (paparan guna 38–40px) — mesti
  selesa dibaca sepintas lalu dalam feed telefon, bukan ~24px yang perlu zoom.
- Satu fokus visual utama setiap slide (nombor list, stat besar, atau hiasan
  sudut) — jangan tambah lebih daripada itu.
- Jangan letak teks di atas tekstur hiasan yang sibuk; hiasan (`decorative`)
  direka supaya tidak bertindih dengan zon teks. Label "Swipe →" pada slide 1
  (`cover`) diletak di bawah-KIRI, berasingan daripada hiasan sudut-kanan
  (`corner-mark`/`halftone-dot`) dan daripada nombor slide di footer.
- Content block (kicker+headline+body/list) dijajar ATAS di bawah margin atas
  untuk semua layout kecuali `cover` dan `quote` (kekal tengah, headline jadi
  fokus dominan) — supaya slide dengan copy pendek tidak "terapung" di
  tengah-bawah kanvas dengan ruang kosong besar atas dan bawah.

Nilai ini sudah dikodkan dalam `assets/carousel.html`; rujukan ini untuk
semak/jelaskan sebab, bukan untuk ubah CSS secara manual. Band ketumpatan copy
di `plan-and-gates.md` sudah dikira ikut saiz fon ini — jangan anggap boleh
tulis lebih banyak perkataan kerana "boleh kecilkan fon"; layout ini sengaja
tak sokong pengecilan fon manual sebab itu yang buat carousel lama sukar
dibaca dalam feed telefon.

## Pilihan `decorative` (CSS sahaja, tiada fail imej)

| Nilai | Kesan |
|---|---|
| `none` | Tiada hiasan tambahan. |
| `torn-edge` | Tepi bawah kanvas koyak/zigzag (kertas). |
| `halftone-dot` | Corak titik halftone di sudut bawah-kanan, warna accent. |
| `corner-mark` | Segi tiga kecil warna accent-soft di sudut atas-kanan. |
| `underline` | Jalur warna accent-soft di bawah headline. |

`layout_style: "clean"` sentiasa matikan semua hiasan di atas, tak kira nilai
`decorative` — guna bila rujukan gaya pengguna nampak minimalis/tiada hiasan.

## Kesan `layout_style`

| Nilai | Kesan dalam `carousel.html` |
|---|---|
| `listicle` | Nombor list jadi kotak bucu tajam. |
| `how-to` | Nombor list ditukar label "Langkah 1", "Langkah 2"… |
| `data-stats` | Angka stat guna angka bersaiz sekata (tabular numerals). |
| `story` | Headline/kicker lebih lapang, kicker italic. |
| `clean` | Minimalis; semua hiasan `decorative` dimatikan. |

Pilih `layout_style` ikut jenis content (senarai tanda/sebab → `listicle`;
arahan langkah demi langkah → `how-to`; angka/kajian → `data-stats`; cerita
peribadi/pengalaman → `story`; tiada kecenderungan → `clean`), atau ikut apa
yang paling hampir dengan rujukan gaya pengguna.
