---
name: social-setup
description: Bantu pelajar sambung app developer Meta mereka sendiri (Facebook, Instagram, Threads) di komputer mereka sendiri, dengan pilihan mod manual (AI pandu, pengguna klik) atau auto (AI guna computer use), dan wizard tempatan untuk tampal token. Guna bila pengguna mahu "sambung", "setup" atau "connect" Facebook, Instagram atau Threads. Requires an AI app that can run shell commands on the user's own computer.
---

# Social Setup

Skill ini sambungkan app developer pengguna sendiri (bukan app PandaiTech) ke **Meta** (Facebook + Instagram + Threads). Token dan secret dimasukkan dalam **wizard tempatan** yang jalan di komputer pengguna sendiri, bukan dalam chat ini.

TikTok dan YouTube **tidak dilindungi** oleh skill ini. Pelajar yang perlukan TikTok atau YouTube guna scheduler connector (Post-bridge atau Postiz) ikut kursus.

AI tanya dulu mod **manual** (pengguna klik sendiri, AI pandu dalam chat) atau **auto** (AI buat guna computer use). Dua-dua mod berakhir dengan wizard tempatan untuk tampal token, supaya token tak pernah lalui chat.

## Keperluan

Skill ini perlukan AI app yang boleh jalankan command di komputer pengguna (contoh: app desktop Claude dengan Cowork/Code, Claude Code, Codex, ChatGPT dengan Codex). Kalau anda sedang jalan dalam **claude.ai web** atau chat biasa yang tak boleh jalankan command, **jangan cuba** jalankan skrip ini (mod manual untuk langkah console masih boleh dipandu, tapi token perlu disimpan ikut panduan manual). Beritahu pengguna dengan jujur dan arahkan mereka ke panduan manual di halaman kursus (guide yang sepadan: `02-meta-app-fb-ig-threads.md`).

## Cara guna

### Langkah 1: tanya mod

Sebelum buat apa-apa, tanya pengguna **satu soalan** dengan dua pilihan:

> Nak setup macam mana?
> 1. **Manual**: anda klik sendiri, saya pandu langkah demi langkah. Jimat token.
> 2. **Auto**: saya buat sendiri guna computer use, anda cuma login dan tampal token di akhir. Guna lebih banyak token.

Tunggu jawapan. Jangan mula sebelum pengguna pilih.

- **Manual:** ikut `references/meta-manual.md`. Pandu satu langkah pada satu masa dalam chat, tunggu "siap" sebelum langkah seterusnya. Pada langkah akhir, jalankan wizard (di bawah) untuk pengguna tampal token.
- **Auto:** ikut `references/meta-auto.md`. Kalau AI app ini tiada computer use, beritahu pengguna dan tawarkan mod manual.

### Langkah akhir: wizard untuk masukkan token

1. Jalankan (dalam background kalau tool anda sokong long-running command, kalau tidak jalankan foreground):
   ```
   python3 scripts/setup.py meta
   ```
   Windows: `py scripts/setup.py meta`
2. Beritahu pengguna: **"Wizard dah dibuka dalam browser anda. Tampal nilai dalam kotak di bawah dan klik Sahkan & Simpan."** (Pengguna dah siap langkah console, jadi boleh terus ke kotak.)
3. Tunggu skrip selesai. Ia akan tamat sendiri bila pengguna klik selesai, batal, atau selepas 30 minit tanpa tindakan.
4. Skrip cetak **satu baris JSON** ke stdout (platform, status, apa yang disahkan, tarikh luput -- tiada secret). Relay dalam **2 hingga 3 ayat Bahasa Melayu**, contohnya:
   > Facebook + Instagram + Threads berjaya disambung. Semua token disahkan aktif. Token Threads luput 29 November -- jalankan wizard ni semula sebelum tarikh tu untuk refresh.

Untuk semak status semua platform yang sudah disambung (tanpa buka wizard):
```
python3 scripts/setup.py check
```
Ini jalan automatik (tiada wizard/browser), sahkan setiap credential tersimpan, dan cetak satu baris JSON per platform. Guna bila pengguna tanya "adakah Meta saya masih sambung?" dan seumpamanya.

## Peraturan keras

- **Jangan** baca atau buka `~/.pandaitech/social/credentials.json`. Fail itu untuk skrip sahaja.
- **Jangan** minta App ID, Client Key, Client Secret atau token dalam chat. Semua nilai ditaip terus oleh pengguna ke dalam wizard tempatan (browser), tak pernah lalui chat AI.
- **Jangan** cetak atau ulang apa-apa yang kelihatan seperti token/secret walaupun pengguna tampal dalam chat secara tak sengaja -- kalau ini berlaku, beritahu pengguna untuk tampal dalam wizard sahaja, bukan chat.
- **Jangan reka langkah tambahan.** Ikut je output skrip. Kalau skrip error (contohnya port sedang digunakan, atau pengguna tanya "kenapa gagal"), tunjukkan mesej error tu terus dan sebut bahagian guide yang sepadan (`02-meta-app-fb-ig-threads.md`) supaya pengguna boleh semak langkah console secara manual kalau perlu.
- Skrip ini **tak buat** apa-apa panggilan API yang mengubah/menerbitkan apa-apa -- semua panggilan verifikasi adalah read-only (contohnya `/me`).

## Apa yang wizard buat (untuk rujukan, bukan untuk anda buat semula)

| Platform | Nilai yang ditampal pengguna | Luput |
|---|---|---|
| `meta` | Token Facebook+Instagram, Page ID, Instagram Business ID, Token Threads | Token FB+IG tak luput; Token Threads 60 hari |

Wizard sahkan setiap credential dengan satu panggilan API read-only (Graph API `/me`) dan papar hijau/merah dengan sebab ringkas dalam Bahasa Melayu bila gagal. Simpan ke `~/.pandaitech/social/credentials.json` (gabung ikut platform, tak timpa platform lain), fail permission 600 di macOS/Linux.

## README

Lihat `README.md` dalam folder ini untuk penerangan ringkas kepada pengguna (Bahasa Melayu).
