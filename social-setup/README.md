# social-setup

Skill untuk sambung app developer anda sendiri ke **Facebook, Instagram, Threads** (satu app Meta), **TikTok** dan **YouTube**, tanpa perlu tampal token dalam chat AI.

## Macam mana ia jalan

1. Anda minta AI (contohnya "sambung TikTok saya") dalam AI app yang boleh jalankan command di komputer anda -- app desktop Claude (Cowork/Code), Claude Code, Codex, atau ChatGPT dengan Codex.
2. AI jalankan satu skrip tempatan: `python3 scripts/setup.py tiktok` (Windows: `py scripts/setup.py tiktok`).
3. Skrip buka **satu tab browser di komputer anda** -- satu wizard step-by-step dalam Bahasa Melayu, dengan butang "Buka page ini" untuk setiap page console yang perlu.
4. **Anda** tampal App ID / Client Key / Secret / token terus dalam wizard tu. Nilai ni **tak pernah** masuk chat AI atau dihantar ke mana-mana selain server platform berkenaan (Meta / TikTok / Google).
5. Wizard sahkan setiap nilai dengan satu panggilan API ringkas (baca sahaja, tak ubah apa-apa) dan tunjuk hijau/merah dengan sebab kalau gagal.
6. Bila semua hijau, klik **Sahkan & Simpan**. Wizard simpan ke `~/.pandaitech/social/credentials.json` di komputer anda sahaja, dan wizard tamat.
7. AI baca ringkasan (tiada token/secret) dan beritahu anda 2-3 ayat: apa yang berjaya, dan bila token akan luput.

## Kalau AI anda tak boleh jalankan command

Kalau anda guna claude.ai web atau chat biasa yang tak boleh jalankan command di komputer anda, skill ni tak boleh digunakan. Ikut panduan manual di halaman kursus untuk setiap platform:

- Facebook / Instagram / Threads: `guides/02-meta-app-fb-ig-threads.md`
- TikTok: `guides/03-tiktok.md`
- YouTube: `guides/04-youtube.md`

## Semak status

Untuk lihat platform mana yang masih sambung (tanpa buka wizard):

```
python3 scripts/setup.py check
```

## Keselamatan

- Token dan secret ditaip terus dalam wizard di browser anda, tak pernah lalui chat AI.
- Fail `credentials.json` disimpan di komputer anda sahaja (`~/.pandaitech/social/`), permission 600 (owner sahaja) di macOS/Linux.
- Semua panggilan verifikasi adalah baca sahaja -- wizard tak post, publish atau ubah apa-apa di akaun anda.
- Token luput? Jalankan `python3 scripts/setup.py <platform>` semula untuk refresh.

## Struktur folder

```
social-setup/
  SKILL.md              -- arahan untuk AI agent
  README.md             -- fail ini
  scripts/
    setup.py            -- entry point CLI (meta | tiktok | youtube | check)
    lib/
      store.py           -- baca/simpan credentials.json, redaksi ringkasan, kiraan luput
      verify.py           -- panggilan API baca-sahaja untuk sahkan setiap credential
      oauth.py            -- bina URL log masuk TikTok/Google
      platforms.py         -- kandungan wizard setiap platform (langkah, medan, URL)
      server.py            -- HTTP server tempatan + wizard + endpoint OAuth callback
  assets/
    wizard.html / .css / .js  -- halaman wizard
  tests/
    test_store.py        -- ujian unit bahagian tulen (merge, redaksi, luput)
```
