---
name: shortform-studio
description: Tukar satu rakaman panjang (kelas, webinar, live, podcast, temu bual) kepada beberapa video pendek 9:16 untuk TikTok/Reels/Shorts — cari klip terbaik, cadangkan hook & caption, render dengan Studio (app tempatan untuk semak & luluskan setiap klip), sampai final check. Guna bila pengguna ada rakaman/transkrip dan nak "jadikan video pendek", "clip kan video ni", "buat shortform daripada webinar/kelas ni". Perlukan Claude Code, Claude desktop (tab Code), atau app lain yang boleh jalankan command di terminal — bukan untuk chat biasa tanpa akses fail/terminal (lihat **Mod chat sahaja** di bawah untuk had itu). Turns one long recording into several 9:16 short-form clips end to end, with a local review app for approving each cut.
---

# Shortform Studio

Satu rakaman panjang → beberapa video pendek 9:16 siap render, caption dan
selesai semak. Skill ini jalankan pipeline penuh: cari klip, cadang hook,
render, dan satu app tempatan (**Studio**) untuk anda tengok setiap klip dan
bagi nota sebelum ia lulus.

Ini bukan skill "chat sahaja" — ia perlukan terminal (ffmpeg, python,
whisper.cpp). Guna dalam **Claude Code**, tab **Code** dalam Claude desktop,
atau **Codex app**. Kalau anda dalam ChatGPT/Claude web biasa tanpa akses
fail dan command, lihat **Mod chat sahaja** di hujung.

## Struktur skill

```
shortform-studio/
  SKILL.md                        <- anda di sini
  references/                     <- peraturan editorial, caption, layout, manifest
  scripts/                        <- transcribe, tighten, render (standard), screen motion, check
  studio/                         <- app Studio (server + web UI)
```

Semua data kerja (rakaman, klip, taste book, render) disimpan **di luar**
skill ni, dalam `$STUDIO_DATA_DIR` (lalai: `./shortform-studio-data`,
relatif kepada folder tempat anda jalankan `studio.py`). Skill sendiri tetap
bersih — boleh copy ke mana-mana projek, data tak bercampur dengan kod.

## Langkah 1: Semak tools

Jalankan semak ni dulu, sekali sahaja setiap mesin:

```bash
which ffmpeg ffprobe python3 uv whisper-cli
```

Kalau ada yang hilang:

| Tool | Pasang (macOS, Homebrew) | Lain-lain |
|---|---|---|
| `ffmpeg` / `ffprobe` | `brew install ffmpeg` | apt: `sudo apt install ffmpeg` |
| `python3` (>=3.9) | biasanya dah ada | `brew install python3` |
| `uv` (untuk renderer house-style — pillow/numpy tanpa install global) | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `whisper-cli` (whisper.cpp, untuk transcript word-level tempatan) | `brew install whisper-cpp` | build dari [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) |

Model whisper.cpp (bukan sebahagian `pip`/`brew`, muat turun sekali):

```bash
mkdir -p ~/.cache/shortform-studio/whisper/models
curl -L -o ~/.cache/shortform-studio/whisper/models/ggml-medium.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
```

`ggml-medium.bin` cukup untuk kebanyakan kerja; guna `ggml-large-v3.bin` (URL
sama, tukar nama fail) kalau perlukan ketepatan lebih tinggi pada rakaman
bising/aksen berat. Kalau binari dipasang bernama lain (`whisper-main`,
`main`), guna nama tu dalam command `scripts/transcribe.py --whisper-cli`.

Tak perlu ulang semakan ni setiap kali — sekali cukup untuk satu mesin.

## Langkah 2: Dapatkan rakaman + transkrip

1. Minta path fail rakaman (mp4/mov/mkv, dsb.) daripada pengguna.
2. Tanya sama ada mereka **sudah ada transkrip**: SRT/VTT, transkrip Zoom,
   auto-caption YouTube, atau hasil ASR lain. Kalau ada, tukar ke format JSON
   `{"segments": [...]}` (tambah `word_segments` kalau sumber bagi timing
   per-perkataan).
3. Kalau **tiada** transkrip, atau transkrip sedia ada terlalu kasar untuk
   cut yang tepat (perenggan sahaja, bukan per-perkataan), jana word
   timeline tempatan:

   ```bash
   python3 scripts/transcribe.py /absolute/path/rakaman.mp4 \
     --model ~/.cache/shortform-studio/whisper/models/ggml-medium.bin \
     --output /absolute/path/rakaman-words.json \
     --language ms
   ```

   Tukar `--language` ikut bahasa rakaman (`ms` untuk Melayu, `en` untuk
   English, boleh campur — model whisper multilingual boleh handle
   code-switch Melayu/English dalam satu rakaman).
4. Untuk rakaman panjang (>30 minit), jalankan sekali untuk seluruh rakaman
   dan simpan hasilnya — jangan transcribe berulang. Untuk satu klip sahaja,
   window fokus (`--start`/`--duration`) cukup.

Baca [references/editorial-rules.md](references/editorial-rules.md) dan
[references/final-polish.md](references/final-polish.md) untuk cara guna
transkrip ni dengan betul (timing ASR biasanya leret 0.3-0.7 saat).

## Langkah 3: Cari klip, cadang ke Studio, buka Studio sendiri

Pengguna biasanya mula macam ni:

> ni rakaman webinar aku, webinar.mp4. cari klip paling padu untuk Reels dan
> TikTok. bagi aku pilih dulu sebelum potong.

1. Buat/pastikan ada transkrip (**Langkah 2**).
2. Baca transkrip penuh (bukan cari kata kunci sahaja). Cari 15-30 calon
   klip yang berdiri sendiri — ikut
   [references/editorial-rules.md](references/editorial-rules.md) untuk
   ujian cold-viewer, panjang, hook dan tajuk.
3. Daftarkan rakaman dan setiap cadangan ke Studio (tak perlu server
   berjalan untuk CLI ni):

   ```bash
   python3 studio/studio.py add-recording --title "..." --file /absolute/path/rakaman.mp4 \
     --transcript /absolute/path/rakaman-words.json

   python3 studio/studio.py propose <recording-id> \
     --title "..." --ranges "674.14-693.64,693.98-731.36" \
     --hook "..." --summary "..." --score 8.5
   ```

   (atau `--json-file proposals.json` untuk daftar beberapa sekali gus.)
4. **Buka Studio sendiri, tanpa tunggu pengguna minta** — ini bahagian
   "bagi aku pilih dulu":

   ```bash
   python3 studio/studio.py serve --open
   ```

   Ini buka app web tempatan (default port 5055, tukar dengan `--port`) di
   browser pengguna, terus ke senarai cadangan.

Beritahu pengguna secara ringkas: berapa calon dicadang, Studio dah terbuka,
dan apa nak buat di situ (lihat **Langkah 4**). Jangan potong video lagi —
tunggu pengguna luluskan di Studio, kecuali mereka dah nyatakan nak proses
semua terus tanpa semak satu-satu.

## Langkah 4: Pengguna pilih & laras dalam Studio (bukan kerja AI)

Ini bahagian director buat sendiri dalam browser — AI tidak terlibat sehingga
pengguna kembali ke chat. Dalam **Recordings/Ideas**, setiap cadangan ada
tajuk, hook dan skor:

- **P** — preview klip;
- tarik hujung klip untuk ubah julat masa;
- **A** — approve; **R** — reject calon yang lemah;
- laraskan tema (warna/font) dalam **Settings** kalau brand tersendiri
  diperlukan (lihat nota tema di bawah).

Approve dalam Studio automatik bina recipe rough-cut **dan** render v1
(guna renderer house-style, `studio_core/house_render.py`) — pengguna tak
perlu tunggu AI untuk tu.

### Tema (warna/font)

Renderer house-style guna tema neutral secara lalai. Kalau projek ni ada
`marketing-brain.md` (daripada skill `marketing-brain`) dengan bahagian
brand/warna, isikan tema Studio daripada situ dulu sebelum render pertama:

```bash
curl -sX PATCH http://127.0.0.1:5055/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"theme": {"background": "#...", "text": "#...", "accent": "#...", "font": "..."}}'
```

(atau isikan terus dalam tab **Settings** di UI Studio). Lihat
[references/recipe-and-motion-design.md](references/recipe-and-motion-design.md)
untuk medan tema penuh. Kalau tiada brand dinyatakan, teruskan dengan tema
lalai — jangan tanya dulu.

## Langkah 5: "render" — pastikan v1 sedia

Pengguna kembali ke chat dengan sesuatu macam:

> aku dah approve 3 klip dalam Studio. render.

Approve dalam Studio (Langkah 4) **sudah** automatik bina recipe dan render
v1 untuk setiap klip yang diluluskan — jadi kerja AI di sini biasanya cuma
mengesahkan, bukan merender dari kosong:

1. `python3 studio/studio.py list` — semak setiap klip yang baru diluluskan
   ada sekurang-kurangnya satu versi (`v=1` ke atas, bukan `v=-`).
2. Kalau ada klip approved yang **belum** ada versi (jarang berlaku — recipe
   gagal dibina, atau auto-render dimatikan dalam Settings), render terus
   dengan `python3 studio/studio.py render <clip-id>`, tunggu siap, verify
   (**Langkah 7**).
3. Lapor ringkas: berapa klip dah ada v1, sedia ditonton dalam **Review**.
4. Jalankan **Langkah 8** (log runtime + Bank Content) untuk klip yang baru
   render.

Pengguna tonton v1 dalam Review, tekan **N** untuk tulis nota bertitik-masa,
⌘⏎ untuk hantar — ini juga kerja director dalam browser, bukan AI.

## Langkah 6: "proses queue studio" — balas nota, render versi baharu

> proses queue studio

Ini bermaksud: jalankan `studio.py pending`, kemudian selesaikan setiap item
(satu subagent setiap klip/rakaman, selari, kalau banyak) ikut
`brief`/`brief-rec` item tu.

```bash
python3 studio/studio.py pending
```

Untuk **setiap** klip queued (nota sudah dihantar oleh director):

1. `python3 studio/studio.py claim <clip-id>`
2. Ikut brief klip tu — ia akan beritahu sama ada ini **klip recipe** (route
   Studio house-style — lalai untuk klip yang dilahirkan dari Studio, edit
   JSON recipe terus,
   [references/recipe-and-motion-design.md](references/recipe-and-motion-design.md))
   atau perlu manifest untuk `scripts/render.py` (route standard, hanya
   untuk klip di luar Studio,
   [references/manifest-schema.md](references/manifest-schema.md) +
   [references/layout-profiles.md](references/layout-profiles.md)).
3. Untuk klip recipe: edit recipe JSON supaya setiap nota diikut (contoh:
   nota "hook lambat, mula terus dari ayat X" → ubah `cut.segments[0].a` ke
   saat sumber ayat X, laraskan `title.until`), validate
   (`studio.py recipe <clip-id>`), render versi baharu yang alamatkan setiap
   nota:
   `python3 studio/studio.py render <clip-id> --note "apa yang berubah" --addresses c1,c2`.
   Ini daftar versi baharu automatik — jangan tulis ganti fail lama.
4. Untuk klip route standard: render manual, kemudian
   `python3 studio/studio.py add-version <clip-id> /abs/path/v2.mp4 --notes "..." --addresses c1,c2`.
5. Verify: full decode + contact sheet sempadan setiap cut yang berubah —
   `scripts/check.py` (lihat **Langkah 7**).
6. Untuk nota yang sengaja tak diikut, balas kenapa:
   `studio.py reply <clip-id> <comment-id> "sebab tak buat"`.
7. Kalau nampak corak baru dalam citarasa pengguna (contoh: dia selalu minta
   buang sesuatu jenis moment), cadangkan:
   `studio.py taste --propose "..."`.

Ulang sehingga queue kosong (`studio.py pending` tak tunjuk apa-apa). Lapor
versi baharu sedia untuk pengguna banding (**G**) dan approve (**⇧A**) dalam
Review — itu juga kerja director dalam browser.

## Langkah 7: Final check

Untuk setiap output video, sahkan:

- decode penuh tanpa ralat ffmpeg, resolusi 1080x1920, video H.264, audio
  AAC (`scripts/check.py`);
- title 5 saat pertama, caption 2 baris seimbang lepas tu, sentence case
  (bukan title case), tiada karaoke per-perkataan;
- layout/tema konsisten sepanjang batch (kecuali sengaja diminta lain);
- tiada apa-apa penting dalam 250px paling bawah (kawasan selamat UI
  platform);
- tajuk klip masih tepat untuk cut penuh, bukan hook sahaja;
- fail, ID klip dan julat masa sepadan dengan manifest/recipe yang diluluskan.

Bagi laluan mutlak (absolute path) yang boleh diklik untuk setiap video
akhir dan (kalau relevan) manifest/recipe-nya.

## Langkah 8: Lepas approve — log ke runtime + Bank Content

Setiap klip yang **diluluskan sepenuhnya** (⇧A di Review, `approved_version`
terisi) masuk sistem 1 (`Klip video pendek → post teks`,
lihat lesson 01.10) — supaya task harian pengguna (skill `content-repurposer`)
boleh terus ambil klip ni tanpa dia cari manual. Buat langkah ni lepas
**Langkah 5** atau **6** apabila ada klip baru berstatus `approved`:

1. Cari folder kerja marketing pengguna (folder yang ada `marketing-brain.md`
   / `bank-content.md` — biasanya folder kerja semasa, atau folder yang
   sama dengan `webinar.mp4`; tanya sekali kalau tak jumpa langsung).
2. Ikut format tepat dalam
   `../marketing-brain/references/format-runtime.md` kalau fail itu wujud.
   Kalau tiada, guna format minimum di bawah dan beritahu pengguna dalam
   satu baris yang anda guna format ringkas.
3. Tambah **satu baris** ke `bank-content.md` (append, jangan sunting baris
   lain), status `belum guna`:

   ```markdown
   | Tarikh rekod | Sumber | Idea/topik | Kenapa S-tier | Status |
   |---|---|---|---|---|
   | 2026-09-30 | Klip Studio `guna-voice-sahaja-untuk-explain-kat-ai` (rakaman "Meta Ads dengan AI Agent") | Guna Voice Sahaja Untuk Explain Kat AI — "kita kena scratch atas kertas dulu ke atau terus bincang dengan AI" | Klip video siap render (v2), hook kuat, sedia untuk repurpose jadi post teks | belum guna |
   ```

4. Tambah **satu entri** (append, jangan sunting entri lama) ke
   `runtime/log-YYYY-MM.md` (bulan kalendar semasa; cipta fail/folder kalau
   belum wujud):

   ```markdown
   ### 2026-09-30 09:52 — shortform-studio
   - **Jenis:** klip video
   - **Klip:** Guna Voice Sahaja Untuk Explain Kat AI (`guna-voice-sahaja-untuk-explain-kat-ai`)
   - **Sumber:** rakaman "Meta Ads dengan AI Agent", julat sumber 101:35.4-101:40.8
   - **Hook:** "kita kena scratch atas kertas dulu ke atau terus bincang dengan AI"
   - **Fail:** /absolute/path/ke/renders/.../guna-voice-sahaja-untuk-explain-kat-ai-v2.mp4
   - **Status:** siap, belum post
   ```

5. Kalau AI tak boleh tulis fail terus (contohnya `bank-content.md` bukan
   fail tempatan sebenar), beri baris/entri di atas untuk pengguna tampal
   sendiri, sama macam skill `marketing-brain`.

Satu klip = satu baris Bank Content + satu entri runtime, walaupun ada
beberapa versi (v1, v2, ...) — jangan log setiap versi berasingan, log
sekali sahaja apabila status jadi `approved`.

## Mod chat sahaja

Kalau pengguna berada dalam chat biasa (ChatGPT/Claude web) **tanpa** akses
fail dan terminal — tiada cara jalankan ffmpeg/whisper.cpp/Studio — beritahu
mereka dengan jelas dalam satu baris bahawa render video sebenar perlukan
app yang boleh jalankan command (Claude Code, tab Code dalam Claude
desktop, atau Codex app), dan tawarkan alternatif ini sahaja:

**Senarai highlight sahaja** — daripada transkrip/nota yang pengguna
tampal dalam chat, hasilkan senarai calon klip (tajuk, hook verbatim, julat
masa anggaran jika transkrip ada timestamp, dan sebab ia kuat) ikut
[references/editorial-rules.md](references/editorial-rules.md). Ini adalah
**senarai untuk panduan editing manual sahaja** — bukan video, bukan render.
Bentangkan sebagai jadual, dan cadangkan pengguna bawa senarai ni (atau
transkrip + rakaman) ke Claude Code/Codex untuk hasilkan video sebenar.

## Peraturan umum

- Jangan reka fakta, kata, atau nombor yang tiada dalam rakaman/transkrip.
  Semua yang tersiar di skrin mesti disebut atau ditunjuk dalam rakaman itu
  sendiri.
- Bahasa caption/tajuk ikut bahasa rakaman — Melayu untuk rakaman Melayu
  adalah biasa, bukan pengecualian.
- Jangan tulis ganti fail render sedia ada. Versi baharu = fail baharu.
- Simpan keputusan editorial (klip mana, hook mana, kenapa) berasingan
  daripada keputusan tema/visual — permintaan "ubah gaya sahaja" tak patut
  ubah cut atau audio yang sudah diluluskan.
- Untuk kerja berbilang klip, selarikan (parallelize) di peringkat klip bila
  boleh — setiap klip di Studio queue boleh diproses oleh subagent berasingan.
- Rujuk skill lain dalam koleksi ni bila relevan: guna `marketing-brain`
  untuk konteks brand, `content-repurposer` untuk versi teks daripada
  rakaman yang sama.
- Setiap klip yang diluluskan sepenuhnya log sekali ke `bank-content.md` +
  `runtime/log-YYYY-MM.md` (**Langkah 8**) — jangan lupa langkah ni walaupun
  pengguna tak sebut secara eksplisit; ini yang bagi sistem 1 (`klip → post
  teks`) sesuatu untuk diambil.

## Rujukan penuh

- [references/editorial-rules.md](references/editorial-rules.md) — bank
  klip, ujian cold-viewer, hook, tajuk, panjang, tightening, teaching arc.
- [references/captions-and-onscreen-text.md](references/captions-and-onscreen-text.md)
  — caption, teks di skrin, kawasan selamat platform.
- [references/layout-profiles.md](references/layout-profiles.md) — 3 profil
  layout renderer standard.
- [references/manifest-schema.md](references/manifest-schema.md) — skema
  manifest untuk `scripts/render.py`.
- [references/screen-motion.md](references/screen-motion.md) — zoom skrin
  semantik.
- [references/final-polish.md](references/final-polish.md) — proses
  polish klip sedia ada, word timing tepat.
- [references/recipe-and-motion-design.md](references/recipe-and-motion-design.md)
  — route Studio recipe / house-style, tema, sound.
- [studio/README.md](studio/README.md) dan
  [studio/docs/STUDIO-V2.md](studio/docs/STUDIO-V2.md) — app Studio penuh
  (API, skema recipe).
- `../marketing-brain/references/format-runtime.md` — format tepat
  `bank-content.md` dan `runtime/log-YYYY-MM.md` (**Langkah 8**).
