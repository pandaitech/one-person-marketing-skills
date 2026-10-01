---
name: meta-ads-audit
description: Audit akaun Meta Ads dan hasilkan satu page visual yang senang di-scan — duit, struktur, iklan terbaik dan terburuk, corak menang, titik perubahan, pembaziran, dan apa nak buat seterusnya. Guna bila pengguna kata "audit akaun ads aku", "audit Meta Ads", "semak prestasi iklan aku selama ni", atau mahu faham sejarah iklan sebelum buat iklan baru. Audits a Meta Ads account's history and produces one skimmable visual report page.
---

# Meta Ads Audit

Tujuan: dalam satu page, pengguna faham apa yang dah jadi dalam akaun iklan mereka, kenapa, dan apa nak buat seterusnya. Page tu untuk di-scan dalam beberapa minit, bukan dibaca macam esei.

## 1. Kumpul input

Baca `marketing-brain.md` dalam folder kalau ada. Ambil apa yang dah ada (produk, harga, untung, sasaran kos). Tanya hanya yang masih kurang, sekali gus dalam satu mesej:

- **Produk / skop**: produk mana, dan cara tapis kalau akaun ada banyak produk (nama campaign, link landing page, market).
- **Tempoh**: lalai 12 bulan lepas.
- **Harga** dan **untung kasar setiap jualan**: untuk kira untung lepas iklan dan kos maksimum yang masih untung.

## 2. Tarik data

Guna connector Meta Ads (contohnya `https://mcp.facebook.com/ads`). Tarik apa yang perlu untuk soalan di bawah: tahap campaign, ad set dan iklan; pecahan bulanan; spend, result (purchase, lead atau mesej ikut objective), kos setiap result, ROAS kalau ada, frequency, CTR; teks dan thumbnail creative. Simpan data mentah dalam folder supaya soalan susulan tak perlu tarik semula.

Kalau tiada connector, minta eksport CSV dari Ads Manager (Reports → Export, tahap Ad, tempoh yang sama).

## 3. Analisis: soalan yang mesti dijawab

1. **Gambaran**: berapa spend, berapa result, kos setiap result, ROAS, dan untung lepas iklan. Macam mana trendnya ikut bulan?
2. **Struktur**: berapa campaign, objective apa, ABO atau CBO, berapa ad set dan iklan, dan macam mana struktur berubah dari masa ke masa.
3. **Terbaik vs terburuk**: iklan mana paling murah dan paling mahal ikut kos setiap result. Abaikan iklan yang spend terlalu kecil untuk dinilai (lalai: bawah RM50).
4. **Corak menang**: apa persamaan iklan terbaik — hook, angle, format, tawaran, market, audience, placement.
5. **Titik perubahan**: bila prestasi berubah, dan sebab paling mungkin (creative letih, harga, musim, audience, perubahan struktur). Sokong dengan frequency, CTR dan kos.
6. **Pembaziran**: berapa duit habis tanpa result, di mana, dan bila sepatutnya stop.
7. **Seterusnya**: 3 pengajaran utama, sasaran kos setiap result yang masih untung, dan 3 idea iklan baru berdasarkan corak menang.

Ini senarai soalan, bukan susun atur. Kalau data tunjuk sesuatu yang lebih penting (contohnya satu market jauh lebih murah, atau satu angle bawa separuh jualan), tonjolkan.

## 4. Page audit

Hasilkan satu page HTML, `audit-iklan.html`. Reka bentuk ikut apa yang data tunjuk; pilih sendiri carta, susunan dan penekanan. Prinsip:

- **Visual dulu.** Nombor besar untuk angka utama, carta untuk trend dan perbandingan, tag atau ikon untuk corak. Teks ringkas: lebih kurang 3 ayat setiap bahagian, cukup untuk terangkan apa yang carta tunjuk dan kenapa ia penting.
- **Teks panjang disembunyikan.** Butiran, kaedah dan nota letak dalam bahagian "lihat butiran" yang boleh dibuka.
- **Yang paling penting di atas.** Pembaca yang cuma scan 10 saat pertama patut dah tahu: untung ke tak, apa yang menang, apa yang membazir.
- **Tanda dengan jelas** titik perubahan pada carta, dan iklan menang/kalah dengan warna.
- Muat skrin desktop dan telefon, tiada scroll ke tepi.
- Nota skop, kaedah dan batasan data letak dalam bahagian Kaedah di hujung page, bukan di atas.

Paparkan page tu (ChatGPT: canvas, Preview; Claude: artifact). Kalau tak boleh dipaparkan, beri fail untuk dibuka dalam browser.

## 5. Simpan ke brain

Tambah ringkasan pendek dalam `marketing-brain.md` bahagian Iklan: sasaran kos, angle menang, angle kalah, dan satu entri Pengajaran bertarikh yang merujuk `audit-iklan.html`. Senaraikan dalam chat apa yang ditambah atau diubah.

## Lepas audit

Cadangkan langkah seterusnya dalam satu baris: rancang test dengan 3 idea baru, atau semak iklan aktif setiap hari dengan sasaran kos dari audit ni.
