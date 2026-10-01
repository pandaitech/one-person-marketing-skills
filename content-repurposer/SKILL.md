---
name: content-repurposer
description: Tukar mana-mana sumber (rakaman/transkrip panjang, transkrip klip video pendek, research paper, artikel/berita, jawapan temu bual) kepada content bertulis — Threads (single post atau thread bersiri), post pendek gaya caption FB/IG, atau newsletter. Guna bila pengguna ada bahan lama dan nak "repurpose jadi Threads", "buat post pendek", "tulis newsletter", atau minta beberapa post sekali gus untuk jadual content. Untuk video pendek guna skill `shortform-studio`, untuk carousel Instagram guna skill `ig-carousel`. Turns any source into written Threads posts, short FB/IG-style captions, or a newsletter.
---

# Content Repurposer

Satu sumber content boleh jadi banyak post bertulis. Skill ini fokus **teks sahaja**: Threads, post pendek dan newsletter. Untuk video pendek, guna skill `shortform-studio`. Untuk carousel Instagram, guna skill `ig-carousel`.

## Sumber yang diterima

Apa-apa bahan bertulis atau transkrip:

- Transkrip rakaman panjang (live, kelas, webinar)
- Transkrip klip video pendek yang sedia ada
- Research paper atau kajian
- Artikel atau berita
- Jawapan temu bual (contohnya daripada skill `content-interviewer`)

## Mod

| Mod | Bila | Hasil |
|---|---|---|
| **Threads — single post** | Satu idea padat, berdiri sendiri | 1 post, bawah 500 aksara |
| **Threads — thread bersiri** | Idea yang perlu beberapa post berturutan | 3–7 post bernombor, setiap satu sambung daripada yang sebelum |
| **Post pendek** | Caption gaya FB/IG, lebih santai daripada Threads | 1 post pendek dengan CTA |
| **Newsletter** | Content lebih peribadi dan panjang | 3 pilihan subject line + badan 300–600 perkataan |

Kalau pengguna tak nyatakan mod, tanya yang mana satu, atau tawarkan buat semua sekali guna sumber content yang sama.

## Batch (jadual content)

Pengguna boleh minta beberapa output sekali gus untuk jadual, contohnya "3 thread + 2 post pendek daripada artikel ni". Buat semuanya dalam satu jalan, guna sudut/idea berbeza untuk setiap satu supaya tak berulang. Bentangkan sebagai senarai bernombor yang jelas, siap sedia untuk dijadualkan sebagai draf (lihat **Lepas hasil**): label mod, kandungan penuh, dan cadangan hari/waktu post kalau pengguna minta jadual mingguan.

## Peraturan umum

- **Langkah 1, semua mod:** baca `marketing-brain.md` dari Project. Kalau tiada, sebut dalam satu baris, cadangkan jalankan skill `marketing-brain` dulu, dan teruskan dengan paling banyak 2 soalan pendek.
- **Sebelum mula:** kalau ada folder `runtime/`, baca tajuk/topik entri **14–28 hari lepas** sahaja (`marketing-brain/references/format-runtime.md`) supaya topik/hook tak berulang. Jangan baca runtime penuh.
- Tulis dalam suara brand daripada brain bahagian **2. Brand & gaya bahasa**, dan elakkan perkataan yang ditandakan sebagai dielak. Guna CTA utama daripada bahagian 3.
- **Gaya output: informal, macam owner bercakap sendiri — jangan skema.** Elak ayat formal/korporat, elak jargon marketing. Kalau brain ada contoh ayat sebenar pengguna, ikut nada itu.
- Guna content pillar (bahagian 5 dalam brain) untuk label setiap post bila relevan.
- Jangan reka fakta, angka atau testimoni yang tiada dalam sumber content atau brain.
- **Sumber research paper/artikel/berita:** kredit sumber asal (nama penulis/penerbit atau tajuk artikel) dalam post. Jangan sekali-kali reka atau bulatkan angka — guna angka tepat seperti dalam sumber, atau tinggalkan kalau tiada. Sertakan satu ruang pendapat pengguna sendiri (contohnya "Pendapat saya:" atau soalan terbuka untuk pengguna isi) supaya post tak jadi laporan neutral semata-mata — ia kekal suara peribadi pengguna.

## Mod: Threads

**Single post:** satu idea, berdiri sendiri (tak perlu post lain untuk faham), bawah 500 aksara, ada satu hook di baris pertama.

**Thread bersiri:** 3–7 post bernombor (1/, 2/, 3/...), setiap satu bawah 500 aksara. Post pertama mesti hook kuat yang buat orang nak "tap to read more". Post terakhir tutup dengan CTA atau soalan.

Kalau pengguna tak nyatakan, tanya single atau bersiri — atau cadangkan ikut panjang idea (satu insight padat = single, penjelasan berperingkat/senarai = bersiri).

## Mod: Post pendek (FB/IG)

Gaya caption: lebih santai dan peribadi berbanding Threads, boleh lebih panjang (sesuai untuk caption IG/FB, bukan had aksara ketat). Struktur ringkas: hook 1–2 baris pertama, isi, CTA daripada brain di penghujung. Cadangkan 3–5 hashtag relevan kalau sesuai untuk platform.

## Mod: Newsletter

1. 3 pilihan subject line, pendek dan buat orang nak buka.
2. Badan 300–600 perkataan, gaya lebih peribadi dan panjang daripada Threads/post pendek — macam email kepada kawan, bukan blast marketing.
3. Tutup dengan CTA daripada brain.

## Lepas hasil

- Tawarkan jadualkan sebagai draf melalui Post-bridge atau Postiz kalau connector itu ada dalam Project. **Jangan sekali-kali publish/aktifkan terus** — draf sahaja, sehingga pengguna sahkan dalam chat.
- Cadangkan apa nak log balik ke brain lepas post keluar dan dapat prestasi: post/hook/pillar mana yang dipilih dan kenapa (bahagian 5 — Content), untuk jalankan skill `marketing-brain` (tambah ke brain) lepas seminggu.

## Selepas siap: tulis ke runtime

Lepas hasilkan post (setiap satu, kalau batch), tambah satu entri ke `runtime/log-YYYY-MM.md` ikut format `marketing-brain/references/format-runtime.md` (tarikh, mod/platform, sumber, tajuk/hook, status draf). Kalau item datang daripada `bank-content.md` atau `bank-kajian.md`, tanda baris itu `dah guna <tarikh>`. Kalau AI tak boleh tulis fail terus, keluarkan teks entri runtime (dan baris bank yang dikemas kini) untuk pengguna tampal sendiri.
