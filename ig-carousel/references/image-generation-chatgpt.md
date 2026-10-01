# Mod pilihan: slide berilustrasi (penjanaan imej)

Mod lalai `ig-carousel` ialah `assets/carousel.html` — tipografi + warna, tiada
imej dijana. Mod ini **pilihan**, untuk pengguna yang secara eksplisit nak
slide berilustrasi (gambar/ilustrasi sebagai latar, bukan sekadar teks di atas
warna rata). Paling berguna dalam ChatGPT (image generation terus dalam chat);
dalam Claude, cadangkan pengguna guna alat imej pilihan mereka sendiri dengan
prompt yang sama.

Jangan masuk mod ini secara automatik — tanya dulu: *"Nak slide dengan
ilustrasi/gambar dijana AI, atau cukup dengan reka bentuk teks (carousel.html)
macam biasa?"*

## Peraturan asas (sama macam visual-and-layout.md)

- Imej yang dijana **bukan bukti**. Jangan sekali-kali jana imej untuk gantikan
  screenshot/hasil sebenar yang patut jadi `real-reference`.
- Copy pada slide (headline/body/citation) mesti **sama tepat** dengan yang
  sudah dikunci dalam rancangan slide (`plan-and-gates.md`) — jangan biar model
  imej reka semula ayat.
- Kalau ada rujukan gaya (screenshot pengguna, lihat `style-reference.md`),
  lampirkan imej rujukan itu sekali dalam permintaan penjanaan supaya gaya
  visual (warna, mood, jenis ilustrasi) konsisten merentasi semua slide.
- Kekal pada nisbah 4:5 (1080×1350) dan margin selamat di `visual-and-layout.md`
  — teks utama tak boleh terlindung tekstur ilustrasi.
- Elak: 3D berkilat, glassmorphism, neon, wajah/tangan direka yang boleh nampak
  pelik, UI/dashboard palsu yang nampak macam bukti sebenar, logo/jenama pihak
  ketiga.

## Templat prompt setiap slide

Guna templat ini untuk setiap slide, isi placeholder daripada rancangan slide
yang sudah dikunci:

```text
Hasilkan satu imej ilustrasi carousel Instagram, nisbah 4:5 (1080×1350 px).

Gaya visual: [terangkan gaya — cth. "flat illustration warna hangat, kertas
tekstur ringan" ATAU rujuk imej rujukan yang dilampirkan untuk gaya tepat].

Susun atur: [layout slide, cth. "headline besar di atas, ilustrasi mengisi
2/3 bawah" — ikut nisbah teks:seni untuk layout ini dalam visual-and-layout.md].

Teks yang MESTI ada pada imej, tepat seperti berikut (jangan ubah ejaan/ayat):
- Kicker: "[kicker slide ini, jika ada]"
- Headline: "[headline slide ini, tepat]"
- Body/label lain: "[body/stat/citation slide ini, jika ada, tepat]"

Subjek ilustrasi: [apa yang perlu dilukis — satu subjek/aksi utama sahaja,
cth. "sepasang tangan menabur baja organik ke tanah durian, close-up"].

Warna: latar [background hex/nama], teks utama [ink hex/nama], aksen [accent
hex/nama] untuk elemen kecil (garis, ikon, label).

JANGAN: reka UI/dashboard/screenshot palsu, reka angka/statistik yang tiada
dalam ayat di atas, tambah logo jenama lain, ubah ejaan teks yang diberi.
```

Untuk slide `source` (citation kajian), jangan jana ilustrasi dekoratif yang
mengalih perhatian daripada citation — cadangkan pengguna kekalkan slide itu
sebagai tipografi sahaja (`typography-only`) walaupun slide lain dalam deck
berilustrasi.

## Selepas jana

1. Semak setiap imej: teks tepat (tiada salah eja/hilang perkataan daripada
   model imej), subjek sepadan dengan ayat (bukan generik/mengelirukan), boleh
   dibaca pada lebar telefon (~320–600px).
2. Kalau teks pada imej meleset/kabur, jana semula atau tawarkan pengguna guna
   `carousel.html` untuk slide itu sahaja (boleh campur: sesetengah slide
   berilustrasi, sesetengah tipografi).
3. Simpan imej yang diterima mengikut cara biasa platform (muat turun daripada
   chat) — skill ini tak simpan/proses fail imej.
