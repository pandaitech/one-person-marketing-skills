---
name: content-interviewer
description: Temu bual pengguna satu soalan pada satu masa untuk keluarkan cerita, angka, kesilapan, pendapat kuat dan kata-kata pelanggan sebenar, kemudian susun jawapan itu jadi bahan content asli (S-tier) dan 5 angle content dalam suara brand. Guna bila pengguna kata "saya tak tahu nak tulis apa", "temu bual saya", "AI tanya saya jawab", atau nak tukar pengalaman/cerita jadi content. Sesuai dengan voice mode. Interviews the user one question at a time (voice-friendly) to turn their own experience into original content angles.
---

# Content Interviewer

Ramai orang kata "saya tak tahu nak tulis apa". Tapi bila ditanya soalan, semua orang boleh jawab. Skill ini terbalikkan proses: AI tanya, pengguna jawab, jawapan itu jadi bahan content **S-tier** — content original daripada pengalaman sebenar pengguna, bukan idea kosong daripada AI.

Paling sesuai guna dalam **voice mode**: bercakap 5 minit lebih laju daripada menaip 30 minit.

## Peraturan umum

- **Satu soalan setiap mesej.** Jangan hantar senarai soalan.
- **Soalan mesra suara.** Pendek, ayat biasa, tiada senarai dan tiada format markdown dalam soalan (tiada bullet, tiada bold). Pengguna patut boleh jawab terus bercakap tanpa baca skrin.
- **Gali dalam, bukan luas.** Untuk setiap jawapan, cuba dapatkan sekurang-kurangnya satu daripada: angka/statistik, kesilapan yang pernah dibuat, pendapat kuat/kontroversi kecil, atau kata-kata pelanggan sebenar. Kalau jawapan pertama umum, tanya **satu** soalan susulan sahaja untuk gali lebih spesifik, contohnya "Boleh royak satu contoh sebenar?" atau "Berapa lama tu jadinya?"
- **Kekalkan perkataan pengguna.** Jangan haluskan jadi bahasa korporat semasa temu bual. Petik terus untuk bahagian bahan mentah.
- **Jangan reka fakta.** Apa-apa yang pengguna tak pasti atau tak nak jawab, terima dan teruskan ke soalan lain.
- Pengguna boleh kata "cukup" bila-bila masa untuk terus ke output, walaupun belum sampai 6 soalan.

## Langkah 1: Baca Marketing Brain

Baca `marketing-brain.md` daripada Project. Guna bahagian **5. Content** (content pillar, sumber content original) dan **2. Brand & gaya bahasa** untuk pilih topik dan tulis hook nanti.

Kalau fail tiada: beritahu dalam satu baris, cadangkan jalankan skill `marketing-brain` dulu, kemudian teruskan dengan **maksimum 2 soalan pantas** supaya temu bual dan hook masih boleh jalan: (1) "Apa bisnes anda, dan jual kepada siapa?", (2) "Kalau nak describe gaya bercakap anda dengan pelanggan dalam 3 perkataan, apa dia?"

## Langkah 2: Pilih topik

Tanya satu soalan pembuka. Kalau brain ada content pillar, tawarkan sebagai pilihan:

> Nak cerita pasal apa hari ni? Contohnya [pillar 1], [pillar 2] atau [pillar 3] daripada brain anda — atau topik lain yang anda rasa nak kongsi.

**Topik daripada artikel atau berita (A tier).** Kalau pengguna beri link atau tampal artikel, berita, kajian atau pengumuman: baca dulu, ringkaskan 3 fakta utama dengan sumber (tanpa tambah apa-apa yang tiada dalam artikel), kemudian temu bual untuk dapatkan **pandangan pengguna**: setuju atau tidak dan kenapa, apa maksudnya untuk pelanggan mereka, pengalaman sendiri yang berkaitan. Dalam output, kredit sumber, jangan salin ayat artikel, dan pastikan sekurang-kurangnya separuh setiap draf ialah pandangan pengguna.

Kalau brain tiada content pillar atau pengguna tak pasti, cadangkan 3 topik berdasarkan bisnes/produk dalam brain (contohnya satu cerita permulaan, satu kesilapan yang dibuat, satu soalan pelanggan yang selalu ditanya) dan biar pengguna pilih.

## Langkah 3: Temu bual, satu soalan pada satu masa

Guna `references/soalan-bank.md` untuk pilih set soalan ikut jenis topik (cerita, pendapat/hot take, cara buat, di sebalik tabir, atau kes pelanggan). Tak perlu ikut turutan tepat bank soalan — susun ikut aliran jawapan pengguna, macam perbualan sebenar, bukan senarai soalan tetap.

1. Mula dengan soalan pembuka jenis topik itu.
2. Selepas setiap jawapan, putuskan: gali lebih dalam (satu susulan), atau pindah ke soalan seterusnya.
3. Sasaran **6 hingga 10 soalan** kesemuanya. Boleh tamat lebih awal kalau pengguna kata "cukup", atau bahan sudah cukup kaya (ada cerita + angka/kesilapan/pendapat + boleh buat 5 angle).
4. Jangan tanya semula perkara yang sudah terjawab.

## Langkah 4: Bahan mentah

Sebelum tulis angle, susun jawapan pengguna jadi nota **"Bahan Mentah"**:

- Tulis dalam perkataan pengguna sendiri, bukan bahasa korporat.
- Kekalkan petikan terus untuk baris yang kuat (pendapat, angka, kata-kata pelanggan) — guna tanda petik.
- Susun ikut tema (bukan ikut susunan soalan), contohnya: Latar/cerita, Angka & bukti, Kesilapan & pengajaran, Pendapat, Kata pelanggan.
- Ini bahan mentah, bukan draf siap — tak perlu cantik, kena jujur dan spesifik.

## Langkah 5: 5 angle content

Hasilkan **5 angle**, setiap satu format:

- **Hook:** satu baris, dalam suara brand (guna gaya bahasa, perkataan yang selalu/dielak daripada brain bahagian 2). Kalau brain tiada gaya bahasa, guna gaya pengguna dari jawapan temu bual.
- **Sudut/angle:** satu ayat — apa fokus content ni (contohnya kesilapan, angka mengejutkan, pendapat kontroversi, cerita pelanggan).
- **Format yang sesuai:** video pendek, carousel, thread, atau newsletter — dan sebab ringkas kenapa format itu sesuai untuk angle ini.

Cuba variasikan jenis angle (jangan 5-5 sama jenis) — campur cerita, pendapat, angka, dan kes pelanggan kalau bahan membenarkan.

Kemudian tulis terus **satu post Threads dan satu caption Instagram** daripada angle yang paling kuat, supaya pengguna nampak hasil siap serta-merta. Guna petikan pengguna sendiri. Untuk format lain dan lebih banyak draf, guna `content-repurposer` (Langkah 6).

## Langkah 6: Langkah seterusnya

Tutup dengan:

1. Cadangan hantar bahan mentah + angle ni ke skill `content-repurposer` untuk jadi draf penuh (video pendek, carousel, post bertulis).
2. Cadangan apa nak tambah balik ke Marketing Brain: hook/angle yang kuat → bahagian 5 (Sumber content original, Content pillar); petikan kuat → bahagian 2 (Contoh ayat sebenar); kalau ada pendapat/kesilapan tentang produk → bahagian 3.

## Paparan

Tiada paparan HTML untuk skill ini — output chat sahaja (bahan mentah + 5 angle sebagai teks/markdown biasa dalam mesej).
