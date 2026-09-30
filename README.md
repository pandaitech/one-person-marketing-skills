# One-Person Marketing Skills

Enam skill Bahasa Melayu untuk pelajar kursus **One-Person Marketing Team** oleh PandaiTech. Skill ini jadikan ChatGPT atau Claude sebagai pasukan marketing anda: bina Marketing Brain, hasilkan content daripada satu sumber, dan urus Meta Ads dengan data.

## Skill

| Skill | Lesson | Apa yang ia buat |
|---|---|---|
| `marketing-brain` | Setup 2, 01.11 | Temu bual anda, bina `marketing-brain.md` (brand, produk, audience, content, iklan), dan kemas kini pengajaran setiap minggu. Ada panel setup dan paparan brain. |
| `content-interviewer` | 01.5 | Temu bual anda tentang pengalaman dan pendapat anda, jadikan bahan content original. |
| `content-repurposer` | 01.6, 01.7, 01.8 | Satu rakaman atau content jadi 10 video pendek, carousel Instagram, post Threads dan newsletter. |
| `meta-ads-strategist` | 02.2 | Belum ada data iklan? Rancang campaign pertama: objective, 3 angle, struktur test dan bajet. |
| `meta-ads-analyst` | 02.1, 02.7 | Belajar daripada data 90 hari, dan tentukan setiap iklan: stop, tambah bajet, test angle sama, atau angle baru. |
| `meta-ads-daily-report` | 02.8 | Laporan iklan setiap pagi ke Google Sheets, dengan cadangan tindakan. |

Mula dengan `marketing-brain`. Semua skill lain membaca `marketing-brain.md` dalam Project anda.

## Pasang dengan chat (paling mudah)

Buka ChatGPT atau Claude dan taip:

> install skill https://github.com/pandaitech/one-person-marketing-skills

AI akan baca arahan di bawah dan pasang semua skill. Kalau AI anda tidak boleh memasang skill sendiri, ia akan beri link `.zip`, dan anda ikut langkah **Pasang dengan fail .zip**.

### Arahan untuk AI agent

Pengguna mahu memasang **semua** skill dalam repo ini ke direktori skill peribadi mereka.

1. Setiap folder di akar repo yang mengandungi `SKILL.md` ialah satu skill. Senarai semasa: `marketing-brain`, `content-interviewer`, `content-repurposer`, `meta-ads-strategist`, `meta-ads-analyst`, `meta-ads-daily-report`. Semak repo untuk folder skill lain yang ditambah kemudian.
2. Salin setiap folder skill **sepenuhnya dan tanpa ubah suai**, termasuk `references/`, `assets/` dan `examples/`. Nama folder mesti kekal sama dengan medan `name` dalam `SKILL.md`. Jangan salin `README.md`, `scripts/` atau fail di akar repo.
3. Cara pasang, ikut apa yang anda boleh buat:
   - **Ada direktori skill peribadi yang anda boleh tulis** (contohnya ChatGPT Work, Codex, Claude Code `~/.claude/skills/`): muat turun setiap folder dari `https://github.com/pandaitech/one-person-marketing-skills/tree/main/<nama-skill>` dan simpan di sana.
   - **Boleh jalankan terminal:** `npx skills add pandaitech/one-person-marketing-skills`, atau `git clone` repo ini dan salin folder skill ke direktori skill.
   - **Tidak boleh memasang skill sendiri** (contohnya claude.ai dan app Claude): beritahu pengguna dengan jujur, beri enam link `.zip` dalam jadual di bawah, dan terangkan langkah muat naik untuk app mereka.
4. Selepas pasang, sahkan setiap skill ada `SKILL.md` dengan `name` dan `description`, kemudian beri pengguna senarai skill yang berjaya dipasang dan yang gagal (dengan sebab).
5. Akhir sekali, beritahu pengguna: mulakan dengan `@marketing-brain` (atau "Bantu saya bina Marketing Brain") dalam Project baharu.

## Pasang dengan fail .zip

Muat turun fail `.zip` untuk setiap skill dari [Releases terkini](https://github.com/pandaitech/one-person-marketing-skills/releases/latest):

| Skill | Muat turun |
|---|---|
| `marketing-brain` | [marketing-brain.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/marketing-brain.zip) |
| `content-interviewer` | [content-interviewer.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/content-interviewer.zip) |
| `content-repurposer` | [content-repurposer.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/content-repurposer.zip) |
| `meta-ads-strategist` | [meta-ads-strategist.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/meta-ads-strategist.zip) |
| `meta-ads-analyst` | [meta-ads-analyst.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/meta-ads-analyst.zip) |
| `meta-ads-daily-report` | [meta-ads-daily-report.zip](https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/meta-ads-daily-report.zip) |

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
