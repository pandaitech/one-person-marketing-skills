---
name: marketing-brain
description: Bina, kemas kini dan papar Marketing Brain, iaitu satu fail yang simpan semua konteks marketing sebuah bisnes (brand, gaya bahasa, produk, audience, content, iklan, pengajaran mingguan) dan terus berkembang dari masa ke masa. Guna bila pengguna mahu bina brain, "setup marketing brain", tambah maklumat atau prestasi content/iklan ke dalam brain, atau lihat brain mereka. Juga baca brain ini sebelum menulis content, iklan atau laporan untuk bisnes yang sama. Use for building, growing or viewing a business's marketing context file.
---

# Marketing Brain

Marketing Brain ialah satu fail markdown, `marketing-brain.md`, dalam Project pengguna (ChatGPT atau Claude). Semua kerja marketing lain (content, iklan, laporan) baca fail ini dulu, supaya AI sudah kenal bisnes pengguna.

**Brain tak pernah siap.** Ia bermula separa kosong dan makin bijak setiap kali pengguna tambah maklumat atau prestasi. Jangan sebut brain "siap" atau "lengkap"; sebut versi dan tarikh kemas kini.

## Langkah pertama, setiap kali skill dipanggil: tunjuk panel

Sebelum menulis apa-apa lagi, paparkan panel `assets/brain.html`:

1. Semak sama ada `marketing-brain.md` ada dalam Project.
2. Salin `assets/brain.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali dua blok data:
   - `<script id="setup-state" type="application/json">`: `{"mode": "borang"}` kalau brain belum ada, `{"mode": "brain"}` kalau brain sudah ada.
   - `<script id="brain-data" type="text/markdown">`: isi penuh `marketing-brain.md` kalau ada. Kalau belum ada, biarkan templat asal. Tulis `</script` dalam teks brain sebagai `<\/script`.
3. Paparkan sebagai HTML: **Claude** artifact, **ChatGPT** canvas (Preview). Kalau HTML tidak boleh dipaparkan, teruskan dalam chat sahaja.
4. Hantar **satu mesej pendek** sahaja bersama panel:
   - Brain belum ada: "Isi apa yang anda tahu dalam panel, kemudian tekan **Salin jawapan** dan tampal di sini. Atau terus taip atau tampal apa sahaja dalam chat: link website, bio, menu, caption lama. Tak perlu lengkap."
   - Brain sudah ada: "Ini brain anda sekarang. Nak tambah apa? Prestasi minggu ini, produk baru, atau jawapan kepada perkara belum pasti."

Jangan tanya soalan satu demi satu. Jangan hantar senarai soalan dalam chat; soalan ada dalam panel.

## Bina brain (sekali jalan)

Bila pengguna hantar jawapan (dari panel, taip sendiri, link, fail atau gabungan):

1. Baca semua bahan. Buka link yang diberi (browsing atau connector) dan ambil apa yang berguna.
2. Tulis `marketing-brain.md` **penuh dalam satu jalan** ikut `references/format-brain.md`. Isi setiap medan yang boleh disimpulkan daripada bahan. Guna perkataan pengguna sendiri untuk gaya bahasa, masalah audience dan bantahan.
3. Medan yang tiada maklumat: tulis `(belum pasti)` dan senaraikan dalam bahagian 8. Jangan reka fakta. Jangan tanya susulan dulu; brain separa lebih baik daripada tiada brain.
4. Kemas kini panel yang sama: `{"mode": "brain"}` dan brain penuh dalam `brain-data`.
5. Dalam chat, tulis ringkas (maksimum 5 baris): apa yang sudah diisi, 1 hingga 3 perkara belum pasti yang paling penting, dan arahan simpan (lihat **Simpan brain**). Tambah: "Ada yang salah? Beritahu saya, saya betulkan terus."

## Tambah ke brain (bila-bila masa)

Input boleh jadi apa sahaja: prestasi content/iklan (teks, screenshot, CSV, atau data dari connector seperti Meta Ads MCP, Post-bridge, Postiz), produk baru, perubahan harga, jawapan kepada perkara belum pasti, atau pembetulan.

Buat semuanya dalam satu jalan, tanpa minta pengesahan dulu:

1. Baca brain semasa daripada Project (atau panel).
2. **Maklumat biasa** (produk, harga, audience, pembetulan): ubah bahagian berkaitan terus. Buang dari bahagian 8 apa yang sudah terjawab.
3. **Prestasi**: susun data dalam jadual ringkas (item, platform, tarikh, metrik utama; guna metrik yang ada sahaja). Cari **corak**, bukan item: bandingkan dengan content pillar, hook, format, angle iklan dan waktu post dalam brain. Pilih 3 yang menjadi dan 3 yang tidak menjadi, setiap satu dengan bukti angka. Kalau data sedikit (kurang daripada 5 post), tulis sebagai hipotesis.
4. Tulis entri baharu di **atas** bahagian 7 Pengajaran, ikut format dalam `references/format-brain.md`. Pindahkan corak yang kukuh ke bahagian 5 (Content) atau 6 (Iklan).
5. Kemas kini baris `Dikemas kini:` dan panel (`{"mode": "brain"}`).
6. Dalam chat: senarai pendek perubahan (`Tambah:`, `Ubah:`, `Buang:`), satu cadangan konkrit untuk minggu depan, dan arahan simpan. Kalau pengguna tak setuju dengan mana-mana perubahan, betulkan terus.

## Simpan brain

AI tidak boleh menulis terus ke fail Project. Selepas setiap perubahan, beri fail `marketing-brain.md` untuk dimuat turun (panel juga ada butang **Muat turun .md**) dan ingatkan dalam satu baris:

> Simpan: muat turun `marketing-brain.md`, buka Project anda (Files di ChatGPT, Project knowledge di Claude), ganti versi lama. Nama fail mesti kekal `marketing-brain.md`.

## Peraturan umum

- Bercakap dalam bahasa pengguna. Lalai: Bahasa Melayu yang santai dan jelas.
- Jangan reka fakta. Yang tak pasti ditanda `(belum pasti)`.
- Format fail mesti ikut `references/format-brain.md` dengan tepat. Panel bergantung pada format ini.
- Jangan tulis semula panel dari kosong dan jangan buang bahagian skrip; butang dalam panel bergantung padanya.

## Bila skill lain guna brain

Sebelum menulis content, iklan, carousel, skrip video, laporan atau strategi untuk bisnes ini:

1. Baca `marketing-brain.md` dari Project.
2. Guna gaya bahasa, perkataan yang dielak, audience, tawaran dan CTA daripada brain.
3. Utamakan corak dalam **7. Pengajaran** yang terbaharu berbanding andaian umum.
4. Kalau sesuatu yang penting untuk kerja itu masih `(belum pasti)`, sebut dalam satu baris dan teruskan dengan andaian yang paling selamat.
