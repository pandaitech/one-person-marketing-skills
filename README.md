# One-Person Marketing Skills

Sepuluh skill Bahasa Melayu untuk pelajar kursus **One-Person Marketing Team** oleh PandaiTech. Skill ini jadikan ChatGPT atau Claude sebagai pasukan marketing anda: bina Marketing Brain, hasilkan content daripada satu sumber, dan urus Meta Ads dengan data.

## Skill

| Skill | Lesson | Apa yang ia buat |
|---|---|---|
| `marketing-brain` | Setup 2, 01.13 | Terus buka panel: isi apa yang anda tahu, AI bina `marketing-brain.md` (brand, produk, audience, content, iklan) dalam satu jalan. Brain terus berkembang: tambah prestasi dan maklumat baru bila-bila masa. |
| `content-interviewer` | 01.6 | Temu bual anda tentang pengalaman dan pendapat anda, jadikan bahan content original. |
| `shortform-studio` | 01.7 | Rakaman panjang jadi video pendek, dengan Studio untuk pilih klip dan semak versi; perlukan app yang boleh jalankan command (tab Code dalam Claude desktop, Claude Code, Codex). |
| `ig-carousel` | 01.8 | Apa-apa sumber (transkrip, research paper, artikel) jadi carousel IG, gaya boleh tiru dari carousel rujukan, muat turun PNG. |
| `content-repurposer` | 01.9, 01.11 | Apa-apa sumber (transkrip, research paper, artikel, jawapan temu bual) jadi post Threads (single atau thread bersiri), post pendek FB/IG, atau newsletter — siap dijadualkan sebagai draf. |
| `meta-ads-strategist` | 02.2 | Belum ada data iklan? Rancang campaign pertama: objective, 3 angle, struktur test dan bajet. |
| `meta-ads-audit` | 02.1 | Audit akaun Meta Ads: satu page visual tentang duit, iklan terbaik dan terburuk, corak menang, titik perubahan, pembaziran dan 3 idea iklan baru. |
| `meta-ads-analyst` | 02.7 | Belajar daripada data 90 hari, dan tentukan setiap iklan: stop, tambah bajet, test angle sama, atau angle baru. |
| `meta-ads-daily-report` | 02.8 | Laporan iklan setiap pagi ke Google Sheets, dengan cadangan tindakan. |
| `social-setup` | Setup 3 | Sambung app developer Meta anda sendiri (Facebook, Instagram, Threads) melalui wizard di komputer anda. Untuk TikTok dan YouTube, guna Post-bridge atau Postiz. Token tak pernah masuk chat. Perlukan AI app yang boleh jalankan command (contohnya Claude Code, Codex, app desktop Claude). |

Mula dengan `marketing-brain`. Semua skill lain membaca `marketing-brain.md` dalam Project anda.

## Pasang dengan chat (paling mudah)

Buka ChatGPT atau Claude dan taip:

> install skill https://github.com/pandaitech/one-person-marketing-skills

AI akan baca arahan di bawah dan pasang semua skill. Kalau AI anda tidak boleh memasang skill sendiri, ia akan beri link `.zip`, dan anda ikut langkah **Pasang dengan fail .zip**.

### Arahan untuk AI agent

Pengguna mahu memasang **semua** skill dalam repo ini ke direktori skill peribadi mereka.

1. Setiap folder di akar repo yang mengandungi `SKILL.md` ialah satu skill. Senarai semasa: `marketing-brain`, `content-interviewer`, `shortform-studio`, `ig-carousel`, `content-repurposer`, `meta-ads-strategist`, `meta-ads-audit`, `meta-ads-analyst`, `meta-ads-daily-report`, `social-setup`. Semak repo untuk folder skill lain yang ditambah kemudian.
2. Salin setiap folder skill **sepenuhnya dan tanpa ubah suai**, termasuk `references/`, `assets/` dan `examples/`. Nama folder mesti kekal sama dengan medan `name` dalam `SKILL.md`. Jangan salin `README.md`, `scripts/` atau fail lain di akar repo (folder `scripts/` dan `README.md` di dalam folder skill mesti disalin).
3. Cara pasang, ikut apa yang anda boleh buat:
   - **Ada direktori skill peribadi yang anda boleh tulis** (contohnya ChatGPT Work, Codex, Claude Code `~/.claude/skills/`): muat turun setiap folder dari `https://github.com/pandaitech/one-person-marketing-skills/tree/main/<nama-skill>` dan simpan di sana.
   - **Boleh jalankan terminal:** `npx skills add pandaitech/one-person-marketing-skills`, atau `git clone` repo ini dan salin folder skill ke direktori skill.
   - **Tidak boleh memasang skill sendiri** (contohnya claude.ai dan app Claude): beritahu pengguna dengan jujur, beri link `.zip` dalam jadual di bawah, dan terangkan langkah muat naik untuk app mereka.
4. Selepas pasang, sahkan setiap skill ada `SKILL.md` dengan `name` dan `description`, kemudian beri pengguna senarai skill yang berjaya dipasang dan yang gagal (dengan sebab).
5. Akhir sekali, beritahu pengguna: mulakan dengan `@marketing-brain` (atau "Bantu saya bina Marketing Brain") dalam Project baharu.

## Pasang dengan fail .zip

Muat turun fail `.zip` untuk setiap skill dari [Releases terkini](https://github.com/pandaitech/one-person-marketing-skills/releases/latest):

| Skill | Muat turun |
|---|---|
| `marketing-brain` | [marketing-brain.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/marketing-brain.zip) |
| `content-interviewer` | [content-interviewer.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/content-interviewer.zip) |
| `shortform-studio` | [shortform-studio.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/shortform-studio.zip) |
| `ig-carousel` | [ig-carousel.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/ig-carousel.zip) |
| `content-repurposer` | [content-repurposer.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/content-repurposer.zip) |
| `meta-ads-strategist` | [meta-ads-strategist.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/meta-ads-strategist.zip) |
| `meta-ads-audit` | [meta-ads-audit.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/meta-ads-audit.zip) |
| `meta-ads-analyst` | [meta-ads-analyst.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/meta-ads-analyst.zip) |
| `meta-ads-daily-report` | [meta-ads-daily-report.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/meta-ads-daily-report.zip) |
| `social-setup` | [social-setup.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/social-setup.zip) |

Jangan unzip. Muat naik fail `.zip` terus.

### Claude (app desktop atau claude.ai)

1. Settings → Capabilities. Pastikan **Code execution and file creation** dihidupkan.
2. Bahagian **Skills** → **Upload skill** → pilih fail `.zip`.
3. Ulang untuk setiap skill. Pastikan togol setiap skill hidup.

### ChatGPT (app desktop)

1. Buka **Skills** di sidebar.
2. **Create** → **Upload from your computer** → pilih fail `.zip`.
3. Ulang untuk setiap skill. ChatGPT mungkin mengimbas skill sebelum ia boleh digunakan.

Guna skill dengan menaip `@` dan pilih skill, atau minta terus, contohnya: "Bantu saya bina Marketing Brain."

### Claude Code, Codex dan agent lain

```bash
npx skills add pandaitech/one-person-marketing-skills
```

## Kemas kini

Bila skill dikemas kini, muat turun `.zip` terbaharu dari Releases, buang skill lama dalam ChatGPT atau Claude, dan muat naik yang baharu. Marketing Brain anda tidak terjejas kerana ia disimpan dalam Project anda, bukan dalam skill.

## Prinsip keselamatan

- Skill Meta Ads membaca data sahaja secara lalai. AI tidak akan pause, aktifkan, ubah atau naikkan bajet iklan tanpa pengesahan jelas daripada anda dalam chat.
- Skill content menyediakan draf. Tiada post diterbitkan tanpa pengesahan anda.
- Jangan tampal token atau password dalam chat. Sambung akaun melalui connector rasmi (contohnya Meta Ads MCP) ikut guidebook kursus.
