---
name: marketing-brain
description: Bina, kemas kini dan papar Marketing Brain, iaitu satu fail yang simpan semua konteks marketing sebuah bisnes (brand, gaya bahasa, produk, audience, content, iklan, pengajaran mingguan). Guna bila pengguna mahu bina brain, "setup marketing brain", temu bual tentang bisnes mereka, masukkan prestasi content atau iklan minggu ini ke dalam brain, atau lihat brain mereka. Juga baca brain ini sebelum menulis content, iklan atau laporan untuk bisnes yang sama. Use for building or updating a business's marketing context file.
---

# Marketing Brain

Marketing Brain ialah satu fail markdown, `marketing-brain.md`, yang disimpan dalam Project (ChatGPT atau Claude). Semua kerja marketing lain (content, iklan, laporan) baca fail ini dulu, supaya AI sudah kenal bisnes pengguna tanpa perlu diterangkan semula.

Skill ini ada tiga mod. Pilih mod ikut permintaan pengguna:

| Mod | Bila | Hasil |
|---|---|---|
| **Bina** | Belum ada `marketing-brain.md` dalam Project, atau pengguna minta bina semula | Temu bual, kemudian fail brain + paparan |
| **Kemas kini** | Pengguna beri prestasi content/iklan, atau cakap "update brain", "masukkan pengajaran minggu ini" | Entri Pengajaran baharu + fail brain dikemas kini + paparan |
| **Papar** | Pengguna mahu lihat brain | Paparan sahaja |

Kalau `marketing-brain.md` sudah ada dalam Project dan pengguna minta "bina", tanya dulu sama ada mahu tambah pada brain sedia ada atau mula semula.

## Peraturan umum

- Bercakap dalam bahasa pengguna. Lalai: Bahasa Melayu yang santai dan jelas.
- Jangan reka fakta. Apa-apa yang pengguna tak pasti, tulis dengan penanda `(belum pasti)` di hujung baris dan salin ke bahagian **8. Belum pasti**.
- Guna perkataan pengguna sendiri untuk gaya bahasa, masalah audience dan bantahan. Jangan tukar kepada bahasa korporat.
- Format fail mesti ikut `references/format-brain.md` dengan tepat. Paparan HTML bergantung pada format ini.

## Mod Bina

### Langkah 0: Buka panel setup

Sebelum soalan pertama, buka panel setup di sebelah chat supaya pengguna nampak brain mereka terbina sedikit demi sedikit:

1. Salin `assets/brain-setup.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali dua blok data:
   - `<script id="setup-state" type="application/json">`: kemajuan dan soalan semasa. Medan: `langkah` (0 untuk soalan pembuka, kemudian 1 hingga 10), `jumlah` (10, atau 6 kalau pengguna pilih siapkan selepas teras), `soalan` (soalan yang sedang ditanya), `contoh` (contoh jawapan), `bahagian_aktif` (nombor bahagian brain yang soalan ini isi), `siap` (`false` sehingga Langkah 4).
   - `<script id="brain-data" type="text/markdown">`: draf brain setakat ini, ikut `references/format-brain.md`. Bahagian yang belum ditanya dibiarkan dengan tajuk `##` sahaja (tiada baris). Panel akan paparkannya sebagai "Menunggu".
2. Paparkan sebagai HTML: **Claude** artifact, **ChatGPT** canvas (Preview). Panel direka untuk ruang sempit di sisi chat.
3. **Selepas setiap jawapan**, kemas kini kedua-dua blok dalam panel yang sama (jangan cipta panel baharu): tambah medan yang baru diisi ke draf brain, naikkan `langkah`, dan tulis soalan seterusnya dalam `soalan` dan `contoh`. Kemudian tanya soalan itu dalam chat juga.
4. Kalau HTML tidak boleh dipaparkan dalam persekitaran ini, langkau panel dan teruskan temu bual dalam chat sahaja.

### Langkah 1: Kumpul bahan sedia ada (sebelum bertanya)

Tanya satu soalan pembuka sahaja:

> Sebelum kita mula, ada apa-apa yang saya boleh baca dulu? Contohnya link website, bio Instagram/TikTok, menu atau senarai harga, atau beberapa post yang pernah menjadi. Kalau tiada, taip "tiada" dan kita terus mula.

Kalau pengguna beri bahan, baca semuanya (guna browsing atau connector kalau ada). Isi sebanyak mungkin medan brain daripada bahan itu. Jangan tanya lagi perkara yang sudah terjawab.

### Langkah 2: Temu bual, satu soalan pada satu masa

Ikut susunan dalam `references/soalan.md`. Peraturan:

1. **Satu soalan setiap mesej.** Jangan hantar senarai soalan.
2. Beri contoh jawapan pendek dalam setiap soalan, supaya pengguna tahu tahap perincian yang diharap.
3. Kalau jawapan kabur, tanya satu soalan susulan sahaja, kemudian teruskan.
4. Kalau pengguna jawab "tak tahu", "skip" atau seumpamanya, tandakan `(belum pasti)` dan teruskan. Jangan desak.
5. Langkau soalan yang sudah terjawab dari Langkah 1.
6. Selepas soalan teras (bahagian 1 hingga 4), tawarkan pilihan: teruskan ke soalan content dan iklan, atau siapkan brain sekarang. Brain tak perlu sempurna hari pertama.
7. Tunjukkan kemajuan ringkas di awal setiap soalan, contohnya `(4/10)`.

### Langkah 3: Semak semula

Sebelum tulis fail, beri ringkasan 5 hingga 8 baris tentang apa yang anda faham, dan senarai perkara yang ditanda belum pasti. Tanya: "Betul? Ada yang nak dibetulkan?" Betulkan dulu kalau perlu.

### Langkah 4: Hasilkan fail dan paparan

1. Tulis `marketing-brain.md` penuh ikut `references/format-brain.md`. Letakkan tarikh hari ini pada baris `Dikemas kini:`.
2. Kemas kini panel setup buat kali terakhir: brain penuh dalam `brain-data`, dan `"siap": true` dalam `setup-state`. Panel bertukar kepada "Brain siap" dengan butang muat turun. Kalau panel tidak digunakan, hasilkan paparan HTML penuh (lihat **Paparan** di bawah).
3. Beri arahan simpan (lihat **Simpan brain** di bawah).
4. Tutup dengan 1 hingga 3 perkara belum pasti yang paling penting untuk dijawab minggu ini.

## Mod Kemas kini

Input: prestasi content atau iklan untuk satu tempoh (biasanya seminggu). Boleh jadi teks yang ditampal, screenshot, CSV, atau data dari connector (contohnya Meta Ads MCP, Post-bridge, Postiz). Kalau connector ada dan pengguna tidak beri data, tawarkan untuk tarik data 7 hari lepas.

1. **Baca brain semasa** daripada fail Project. Kalau tiada, beritahu pengguna dan tawarkan Mod Bina dulu.
2. **Susun data** dalam satu jadual ringkas: item (post/iklan), platform, tarikh, metrik utama (reach/views, engagement, klik, CTR, kos, hasil). Guna metrik yang ada sahaja; jangan reka.
3. **Cari corak**, bukan item. Bandingkan dengan content pillar, jenis hook, format, angle iklan dan waktu post yang ada dalam brain.
   - **3 yang menjadi** dan **3 yang tidak menjadi**, setiap satu dengan bukti angka.
   - Kalau data terlalu sedikit untuk buat kesimpulan (contohnya kurang daripada 5 post), katakan begitu dan tulis corak sebagai hipotesis.
4. **Cadangkan perubahan** kepada brain dalam bentuk senarai `Tambah:`, `Ubah:`, `Buang:`, dengan bahagian yang terlibat. Termasuk perkara belum pasti yang kini terjawab oleh data. Tanya pengguna untuk setuju sebelum menulis.
5. **Tulis entri Pengajaran baharu** di **atas** bahagian 7 (paling baharu di atas), ikut format dalam `references/format-brain.md`. Satu entri untuk satu tempoh.
6. **Kemas kini bahagian lain** yang dipersetujui (contohnya pindahkan hook yang menang ke bahagian 5, angle kalah ke bahagian 6). Kemas kini baris `Dikemas kini:`.
7. Hasilkan fail penuh, paparan HTML dan arahan simpan.
8. Tutup dengan satu cadangan konkrit untuk minggu depan berdasarkan pengajaran ini.

## Mod Papar

Baca `marketing-brain.md` dari Project dan hasilkan paparan HTML. Jangan ubah kandungan brain.

## Paparan

Ada dua paparan:

| Fail | Bila | Bentuk |
|---|---|---|
| `assets/brain-setup.html` | Semasa Mod Bina (lihat Langkah 0) | Panel sempit di sisi chat: soalan semasa, kemajuan, brain terisi satu bahagian demi satu |
| `assets/brain-viewer.html` | Mod Papar, Mod Kemas kini, atau bila pengguna mahu lihat brain penuh | Halaman penuh: semua bahagian, perkara belum pasti, garis masa pengajaran |

Cara menghasilkan paparan penuh:

1. Salin `assets/brain-viewer.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali satu tempat: kandungan di antara `<script id="brain-data" type="text/markdown">` dan `</script>`.
2. Ganti kandungan itu dengan isi penuh `marketing-brain.md`. Kalau teks brain mengandungi `</script`, tulis sebagai `<\/script`.
3. Paparkan sebagai HTML:
   - **Claude:** cipta artifact HTML.
   - **ChatGPT:** buka dalam canvas dan tekan Preview.
   - Kalau HTML tidak boleh dipaparkan, beri fail `.html` untuk dimuat turun dan dibuka dalam browser.

Jangan tulis semula paparan dari kosong dan jangan buang bahagian skrip. Butang salin dan muat turun dalam paparan bergantung padanya.

## Simpan brain

AI tidak boleh menulis terus ke fail Project. Selepas setiap Mod Bina atau Mod Kemas kini, beri fail `marketing-brain.md` untuk dimuat turun dan terangkan:

> Simpan brain: muat turun `marketing-brain.md`, kemudian buka Project anda, bahagian Files (ChatGPT) atau Project knowledge (Claude). Buang versi lama dan muat naik yang baharu. Nama fail mesti kekal `marketing-brain.md` supaya skill lain boleh jumpa.

## Bila skill lain guna brain

Sebelum menulis content, iklan, carousel, skrip video, laporan atau strategi untuk bisnes ini:

1. Baca `marketing-brain.md` dari Project.
2. Guna gaya bahasa, perkataan yang dielak, audience, tawaran dan CTA daripada brain.
3. Utamakan corak dalam **7. Pengajaran** yang terbaharu berbanding andaian umum.
4. Kalau sesuatu yang penting untuk kerja itu masih `(belum pasti)`, sebut dalam satu baris dan teruskan dengan andaian yang paling selamat.
