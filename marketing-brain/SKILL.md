---
name: marketing-brain
description: Bina, kemas kini dan papar Marketing Brain, iaitu satu fail yang simpan semua konteks marketing sebuah bisnes (brand, gaya bahasa, produk, audience, content, iklan, pengajaran mingguan) dan terus berkembang dari masa ke masa. Guna bila pengguna mahu bina brain, "setup marketing brain", tambah maklumat atau prestasi content/iklan ke dalam brain, "update brain", "kemas kini brain dari runtime", atau lihat brain mereka. Juga baca brain ini sebelum menulis content, iklan atau laporan untuk bisnes yang sama. Use for building, growing or viewing a business's marketing context file, including refreshing it from the runtime log.
---

# Marketing Brain

Marketing Brain ialah satu fail markdown, `marketing-brain.md`, dalam folder kerja marketing pengguna (ChatGPT Work, Codex, Claude Code), atau dalam Project kalau AI tak boleh tulis fail. Semua kerja marketing lain (content, iklan, laporan) baca fail ini dulu, supaya AI sudah kenal bisnes pengguna.

**Brain tak pernah siap.** Ia bermula separa kosong dan makin bijak setiap kali pengguna tambah maklumat atau prestasi. Jangan sebut brain "siap" atau "lengkap"; sebut versi dan tarikh kemas kini.

## Langkah pertama, setiap kali skill dipanggil: tunjuk panel

Sebelum menulis apa-apa lagi, paparkan panel `assets/brain.html`:

1. Semak sama ada `marketing-brain.md` ada dalam folder kerja (atau Project).
2. Salin `assets/brain.html` **sepenuhnya, tanpa mengubah apa-apa** kecuali dua blok data:
   - `<script id="setup-state" type="application/json">`: `{"mode": "borang"}` kalau brain belum ada, `{"mode": "brain"}` kalau brain sudah ada. Bila `mode` ialah `"brain"`, tambah juga `"skor_sebelum"` dan `"baru"` supaya panel tunjuk brain semakin kukuh — lihat nilai tepat dalam **Bina brain** dan **Tambah ke brain** di bawah.
   - `<script id="brain-data" type="text/markdown">`: isi penuh `marketing-brain.md` kalau ada. Kalau belum ada, biarkan templat asal. Tulis `</script` dalam teks brain sebagai `<\/script`.
3. Paparkan sebagai HTML: **Claude** artifact, **ChatGPT** canvas (Preview). Kalau HTML tidak boleh dipaparkan, teruskan dalam chat sahaja.
4. Hantar **satu mesej pendek** sahaja bersama panel:
   - Brain belum ada: "Isi apa yang anda tahu dalam panel, kemudian tekan **Salin jawapan** dan tampal di sini. Atau terus taip atau tampal apa sahaja dalam chat: link website, bio, menu, caption lama. Tak perlu lengkap."
   - Brain sudah ada: "Ini brain anda sekarang. Nak tambah apa? Prestasi minggu ini, produk baru, atau jawapan kepada perkara belum pasti."

Jangan tanya soalan satu demi satu. Jangan hantar senarai soalan dalam chat; soalan ada dalam panel.

## Bina brain (sekali jalan)

Bila pengguna hantar jawapan (dari panel, taip sendiri, link, fail atau gabungan):

1. Baca semua bahan. Buka link yang diberi (browsing atau connector) dan ambil apa yang berguna. Kalau sumber hanya website, jangan baca satu laman sahaja: buka beberapa halaman (laman utama, about/tentang kami, produk atau harga, contact) sebelum menulis brain.
2. Tulis `marketing-brain.md` **penuh dalam satu jalan** ikut `references/format-brain.md`. Isi setiap medan yang boleh disimpulkan daripada bahan. Guna perkataan pengguna sendiri untuk gaya bahasa, masalah audience dan bantahan.
3. Medan yang tiada maklumat: tulis `(belum pasti)` dan senaraikan dalam bahagian 8. Jangan reka fakta. Jangan tanya susulan dulu; brain separa lebih baik daripada tiada brain.
4. Kemas kini panel yang sama: `{"mode": "brain"}`, brain penuh dalam `brain-data`, `"skor_sebelum": 0` (brain baru bermula dari kosong) dan `"baru"`: senarai nombor bahagian 1 hingga 6 yang ada kandungan sekarang (contoh: `["1","2","3"]`).
5. Dalam chat, tulis ringkas (maksimum 5 baris): apa yang sudah diisi, 1 hingga 3 perkara belum pasti yang paling penting, dan arahan simpan (lihat **Simpan brain**). Tambah: "Ada yang salah? Beritahu saya, saya betulkan terus."

## Tambah ke brain (bila-bila masa)

Input boleh jadi apa sahaja: prestasi content/iklan (teks, screenshot, CSV, atau data dari connector seperti Meta Ads MCP, Post-bridge, Postiz), produk baru, perubahan harga, jawapan kepada perkara belum pasti, atau pembetulan.

Buat semuanya dalam satu jalan, tanpa minta pengesahan dulu:

1. Baca brain semasa daripada Project (atau panel).
2. **Maklumat biasa** (produk, harga, audience, pembetulan): ubah bahagian berkaitan terus. Buang dari bahagian 8 apa yang sudah terjawab.
3. **Prestasi**: susun data dalam jadual ringkas (item, platform, tarikh, metrik utama; guna metrik yang ada sahaja). Cari **corak**, bukan item: bandingkan dengan content pillar, hook, format, angle iklan dan waktu post dalam brain. Pilih 3 yang menjadi dan 3 yang tidak menjadi, setiap satu dengan bukti angka. Kalau data sedikit (kurang daripada 5 post), tulis sebagai hipotesis.
4. Tulis entri baharu di **atas** bahagian 7 Pengajaran, ikut format dalam `references/format-brain.md`. Pindahkan corak yang kukuh ke bahagian 5 (Content) atau 6 (Iklan).
5. Kemas kini baris `Dikemas kini:` dan panel: `{"mode": "brain"}`, `"skor_sebelum"` (skor brain **sebelum** perubahan pass ini — kira purata status bahagian 1–6, Terisi=1 / Separa=0.5 / Kosong=0, darab 100, bulat ke integer terdekat; formula sama seperti dalam `assets/brain.html`) dan `"baru"`: senarai nombor bahagian 1 hingga 6 yang berubah dalam pass ini (contoh: `["3","4"]`).
6. Dalam chat: senarai pendek perubahan (`Tambah:`, `Ubah:`, `Buang:`), satu cadangan konkrit untuk minggu depan, dan arahan simpan. Kalau pengguna tak setuju dengan mana-mana perubahan, betulkan terus.

## Kemas kini brain dari runtime (mingguan, atau bila ~10+ entri baharu)

Trigger: "update brain", "kemas kini brain", "masukkan runtime dalam brain", atau pengguna minta brain "belajar" daripada apa yang berlaku baru-baru ini.

**Jangan jalankan mod ini lepas setiap satu post atau iklan** — ia baca banyak entri sekali gus dan buang token kalau jalan terlalu kerap. Cadangkan pengguna jalankan seminggu sekali, atau bila dah ada lebih kurang 10 entri baharu dalam `runtime/`.

1. Baca checkpoint `Runtime diproses sehingga:` pada header brain semasa.
2. Baca **hanya** entri `runtime/log-YYYY-MM.md` selepas tarikh checkpoint itu (merentasi lebih daripada satu fail bulan kalau perlu — lihat `references/format-runtime.md`). Jangan baca entri sebelum checkpoint; ia sudah diproses.
3. **Kelaskan setiap dapatan:**
   - **Sahkan** — entri runtime sepadan/menyokong apa yang brain dah kata. Tiada perubahan pada brain.
   - **Baru** — maklumat yang brain belum ada langsung. Tambah terus ke bahagian berkaitan.
   - **Bercanggah** — entri runtime lawan apa yang brain kata sekarang. Ikut peraturan konflik di bawah.
4. **Peraturan konflik:**
   - **Fakta yang pengguna sendiri nyatakan** (harga, produk, tawaran, perkataan nak dielak): **tarikh terbaharu menang**. Log sebagai `Ubah: <nilai lama> → <nilai baharu> (sumber: runtime YYYY-MM-DD)` dan kemas kini bahagian brain berkaitan terus.
   - **Corak prestasi** (waktu post terbaik, angle menang/kalah, dsb.): **jangan ubah brain melainkan sekurang-kurangnya 3 entri prestasi runtime tunjuk arah yang sama**. Kurang daripada itu, tulis sebagai hipotesis dalam bahagian 7 (Pengajaran), bukan fakta tetap dalam bahagian 5/6.
   - Konflik yang tak cukup bukti untuk mana-mana pihak: letak dalam bahagian **8. Belum pasti** sebagai soalan, dan tanya pengguna terus dalam chat — jangan andaikan sendiri.
   - **Maklum balas pengguna yang berulang (≥2 kali)** dalam runtime (contohnya "jangan guna perkataan X" disebut dua kali dalam entri berasingan): jadi peraturan tetap dalam brain (bahagian 2 kalau pasal gaya bahasa, bahagian berkaitan kalau lain).
5. Tulis entri baharu di bahagian 7 (Pengajaran) untuk corak yang disahkan, ikut format dalam `references/format-brain.md`.
6. Kemas kini baris `Dikemas kini:` dan `Runtime diproses sehingga:` (tarikh entri runtime terakhir yang diproses pass ini).
7. Mampatkan/gabung ayat berulang kalau perlu supaya brain kekal bawah had lebih kurang 1,500 perkataan (lihat `references/format-brain.md`).
8. Kemas kini panel: `{"mode": "brain"}`, `"skor_sebelum"` (skor brain sebelum pass ini, formula sama macam mod **Tambah ke brain**) dan `"baru"` (bahagian 1–6 yang berubah).
9. Dalam chat: senaraikan dapatan ikut kelas (Sahkan / Baru / Bercanggah dan cara ia diselesaikan), soalan dalam bahagian 8 yang perlu jawapan pengguna, dan arahan simpan (**Simpan brain**).

## Simpan brain

- **Kalau AI ini boleh baca/tulis fail terus dalam folder kerja pengguna** (contohnya ChatGPT Work, Codex, Claude Code): tulis `marketing-brain.md` terus ke folder kerja, dan sebut dalam **satu baris sahaja**, contohnya "Disimpan terus ke `marketing-brain.md` dalam folder kerja anda."
- **Kalau tidak** (contohnya claude.ai atau app ChatGPT tanpa akses fail): beri fail `marketing-brain.md` untuk dimuat turun (panel juga ada butang **Muat turun .md**) dan ingatkan dalam satu baris:

> Simpan: muat turun `marketing-brain.md`, buka Project anda (Files di ChatGPT, Project knowledge di Claude), ganti versi lama. Nama fail mesti kekal `marketing-brain.md`.

## Peraturan umum

- Bercakap dalam bahasa pengguna. Lalai: Bahasa Melayu yang santai dan jelas.
- Jangan reka fakta. Yang tak pasti ditanda `(belum pasti)`.
- Format fail mesti ikut `references/format-brain.md` dengan tepat. Panel bergantung pada format ini.
- Brain ada checkpoint `Runtime diproses sehingga:` (header baris 3) dan had saiz lebih kurang 1,500 perkataan — lihat `references/format-brain.md`. Checkpoint hanya dikemas kini oleh mod **Kemas kini brain dari runtime**.
- Jangan tulis semula panel dari kosong dan jangan buang bahagian skrip; butang dalam panel bergantung padanya.

## Bila skill lain guna brain

Sebelum menulis content, iklan, carousel, skrip video, laporan atau strategi untuk bisnes ini:

1. Baca `marketing-brain.md` dari Project atau folder kerja.
2. Guna gaya bahasa, perkataan yang dielak, audience, tawaran dan CTA daripada brain.
3. Utamakan corak dalam **7. Pengajaran** yang terbaharu berbanding andaian umum.
4. Kalau sesuatu yang penting untuk kerja itu masih `(belum pasti)`, sebut dalam satu baris dan teruskan dengan andaian yang paling selamat.
5. **Kalau ada folder `runtime/`:** sebelum mula, baca tajuk/topik daripada entri **14–28 hari lepas sahaja** (`references/format-runtime.md`) supaya topik/hook tak berulang. Jangan baca runtime penuh — itu boros token dan bukan kerja skill content.
6. **Lepas siap hasilkan sesuatu** (post, carousel, laporan, dsb.): skill itu sendiri tambah satu entri ke `runtime/log-YYYY-MM.md` ikut `references/format-runtime.md`. Ini bukan tanggungjawab skill `marketing-brain` — setiap skill content/iklan buat sendiri lepas hasil siap.
