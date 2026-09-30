# social-setup

Skill untuk sambung app developer Meta anda sendiri -- **Facebook, Instagram, Threads** (satu app Meta) -- tanpa perlu tampal token dalam chat AI.

TikTok dan YouTube **tidak dilindungi** oleh skill ini. Kalau anda perlukan TikTok atau YouTube, guna scheduler connector (Post-bridge atau Postiz) ikut kursus.

## Macam mana ia jalan

1. Anda minta AI (contohnya "sambung Facebook saya") dalam AI app yang boleh jalankan command di komputer anda -- app desktop Claude (Cowork/Code), Claude Code, Codex, atau ChatGPT dengan Codex.
2. AI tanya dulu: **manual** (anda klik sendiri, AI pandu langkah demi langkah, jimat token) atau **auto** (AI buat sendiri guna computer use, lebih banyak token). Dua-dua mod berakhir di wizard untuk anda tampal token.
3. AI jalankan satu skrip tempatan: `python3 scripts/setup.py meta` (Windows: `py scripts/setup.py meta`).
4. Skrip buka **satu tab browser di komputer anda** -- satu wizard step-by-step dalam Bahasa Melayu, dengan butang "Buka page ini" untuk setiap page console yang perlu.
5. **Anda** tampal token / Page ID / Instagram Business ID terus dalam wizard tu. Nilai ni **tak pernah** masuk chat AI atau dihantar ke mana-mana selain server Meta.
6. Wizard sahkan setiap nilai dengan satu panggilan API ringkas (baca sahaja, tak ubah apa-apa) dan tunjuk hijau/merah dengan sebab kalau gagal.
7. Bila semua hijau, klik **Sahkan & Simpan**. Wizard simpan ke `~/.pandaitech/social/credentials.json` di komputer anda sahaja, dan wizard tamat.
8. AI baca ringkasan (tiada token/secret) dan beritahu anda 2-3 ayat: apa yang berjaya, dan bila token akan luput.

## Kalau AI anda tak boleh jalankan command

Kalau anda guna claude.ai web atau chat biasa yang tak boleh jalankan command di komputer anda, skill ni tak boleh digunakan. Ikut panduan manual di halaman kursus:

- Facebook / Instagram / Threads: `guides/02-meta-app-fb-ig-threads.md`

## Semak status

Untuk lihat sama ada Meta masih sambung (tanpa buka wizard):

```
python3 scripts/setup.py check
```

## Keselamatan

- Token dan secret ditaip terus dalam wizard di browser anda, tak pernah lalui chat AI.
- Fail `credentials.json` disimpan di komputer anda sahaja (`~/.pandaitech/social/`), permission 600 (owner sahaja) di macOS/Linux.
- Semua panggilan verifikasi adalah baca sahaja -- wizard tak post, publish atau ubah apa-apa di akaun anda.
- Token luput? Jalankan `python3 scripts/setup.py meta` semula untuk refresh.

## Struktur folder

```
social-setup/
  SKILL.md              -- arahan untuk AI agent
  README.md             -- fail ini
  scripts/
    setup.py            -- entry point CLI (meta | check)
    lib/
      store.py           -- baca/simpan credentials.json, redaksi ringkasan, kiraan luput
      verify.py           -- panggilan API baca-sahaja untuk sahkan setiap credential
      platforms.py         -- kandungan wizard Meta (langkah, medan)
      server.py            -- HTTP server tempatan + wizard
  assets/
    wizard.html / .css / .js  -- halaman wizard
  tests/
    test_store.py        -- ujian unit bahagian tulen (merge, redaksi, luput)
```
