# Meta: mod auto (AI buat guna computer use)

AI kawal browser pengguna dan buat langkah 1 hingga 13 dalam `meta-manual.md` sendiri. Mod ini guna lebih banyak token, sebab setiap klik perlukan screenshot.

## Syarat

- AI app mesti ada **computer use** (kawal skrin dan browser), contohnya Claude desktop dengan computer use dihidupkan, atau ChatGPT agent. Kalau tiada, beritahu pengguna dengan jujur dan tawarkan mod manual.
- Pengguna dah login Facebook dalam browser tu, atau akan login sendiri bila diminta.

## Apa yang AI buat

Ikut langkah 1 hingga 13 dalam `meta-manual.md`, satu per satu: buka page, isi borang, pilih use case, tambah permission, cipta system user, assign assets, tanda permission token. Selepas setiap bahagian (A, B, C), beritahu pengguna dalam satu ayat apa yang dah siap.

## Apa yang pengguna mesti buat sendiri (AI berhenti dan minta)

- **Login dan 2FA.** AI tak taip kata laluan atau kod 2FA. Berhenti, minta pengguna login, kemudian sambung.
- **Terima terma Meta** (contohnya Meta Platform Terms semasa create app). Berhenti, tunjuk butang, minta pengguna klik sendiri.
- **Terima jemputan Threads di telefon** (langkah 12). AI tak boleh buat ini.
- **Token.** Bila token keluar (langkah 9 dan 13), AI **jangan** baca, salin, taip atau ulang token. Berhenti dan terus ke langkah akhir: jalankan wizard dan minta pengguna klik **Copy** pada token dan tampal sendiri dalam wizard.
- **Page ID & Instagram ID** (langkah 10) perlukan token dalam Graph API Explorer. Minta pengguna tampal token dalam Explorer sendiri; AI boleh taip query dan klik **Submit**, kemudian beritahu pengguna ID mana yang perlu disalin ke wizard. ID bukan secret, jadi boleh disebut dalam chat.

## Kalau sesuatu tak sama

UI Meta berubah dari masa ke masa. Kalau butang tak dijumpai selepas dua cubaan, berhenti dan tanya pengguna, atau tukar ke mod manual untuk langkah tu sahaja. Jangan klik sesuatu yang memadam app, system user atau token.
