# Ekstrak gaya daripada screenshot rujukan

Kalau pengguna tampal/muat naik screenshot carousel yang mereka suka (daripada
perpustakaan rujukan mereka sendiri atau contoh yang mereka jumpa), tugas AI
ialah **tukar imej itu jadi token `theme`** dalam JSON paparan
(`format-carousel.md`) — bukan salin reka bentuk terus, sebab paparan guna
sistem layout sendiri (7 jenis `layout`, fon Google Fonts terhad).

## Langkah

1. Lihat imej rujukan (multimodal — baca terus, jangan minta pengguna terangkan
   dalam teks kalau imej sudah cukup jelas).
2. Ekstrak token berikut, secara anggaran (tak perlu pixel-perfect):

   | Token | Cara anggar |
   |---|---|
   | `background` | Warna latar dominan slide. Ambil kod hex terdekat. |
   | `ink` / `body_color` | Warna teks headline vs teks body (selalunya dua warna berbeza — gelap untuk headline, kelabu/muted untuk body). |
   | `accent` | Warna yang digunakan untuk nombor, garis, kotak sorotan atau CTA — biasanya warna paling menonjol selain hitam/putih. |
   | `heading_font` / `body_font` | Jangan cuba padan fon tepat. Padan **rasa** fon ke senarai disokong dalam `format-carousel.md`: serif elegan → `Fraunces`/`Playfair Display`/`DM Serif Display`/`Lora`; sans besar/moden → `Space Grotesk`/`Poppins`/`Archivo`; sans neutral/bersih → `Inter`/`Work Sans`/`Nunito Sans`. |
   | `layout_style` | Padan kepada kategori terdekat: senarai bernombor/bullet → `listicle`; naratif/cerita peribadi, banyak ruang kosong → `story`; angka/carta/kajian → `data-stats`; arahan berjujukan → `how-to`; sangat minimalis tanpa hiasan → `clean`. |
   | `align` | `left` kalau teks dijajar kiri (paling biasa), `center` kalau semua slide dijajar tengah. |
   | `decorative` | Padan elemen hiasan yang nampak paling ketara ke satu daripada: `torn-edge`, `halftone-dot`, `corner-mark`, `underline`, atau `none` kalau bersih tanpa hiasan. Kalau rujukan ada hiasan yang tak dapat dipadan (cth. bentuk organik, foto tekstur), pilih yang paling hampir dan beritahu pengguna dalam satu ayat yang ia anggaran, bukan replika. |

3. Isi objek `theme` penuh dengan token ini dan teruskan render seperti biasa.
4. Beritahu pengguna dalam satu ayat ringkas: gaya apa yang diekstrak (cth.
   *"Saya ambil gaya serif elegan, latar krim, aksen oren daripada rujukan
   awak — susun atur guna sistem carousel ni, jadi tak 100% sama tapi rasa
   dia serupa."*). Jangan janji replika pixel-perfect.

## Tiada rujukan gaya

Kalau pengguna tak beri screenshot rujukan:

1. Baca `marketing-brain.md` bahagian 2 (Brand & gaya bahasa) untuk warna
   brand kalau dinyatakan. Kalau brain ada warna brand eksplisit, guna sebagai
   `accent` (dan `ink`/`background` jika sesuai).
2. Kalau brain tiada warna brand, atau brain tiada langsung, guna lalai neutral
   `carousel.html` (krim/putih, aksen terakota `#C1502E`, `Fraunces` +
   `Inter`, `layout_style: "clean"`, `align: "left"`, `decorative: "none"`) —
   jangan reka warna brand yang tiada asas.
3. Sebut dalam satu baris yang gaya ini lalai neutral, dan pengguna boleh minta
   tukar warna/gaya bila-bila (edit ikut chat, lihat SKILL.md).

## Simpan gaya untuk carousel akan datang

Kalau pengguna suka hasil gaya ini dan nak guna lagi untuk carousel akan
datang, cadangkan simpan token `theme` itu (warna + fon + `layout_style` +
`decorative`) sebagai nota dalam `marketing-brain.md` bahagian 2, supaya carousel
seterusnya untuk bisnes yang sama boleh terus guna gaya konsisten tanpa perlu
screenshot rujukan setiap kali.
