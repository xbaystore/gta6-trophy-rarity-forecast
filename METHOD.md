# Metode Forecast

## Masalahnya

Rate sebuah trophy adalah persentase pemain terlacak yang sudah meraihnya. Angka ini tidak bergerak mulus: ia naik karena pemain makin jauh progresnya, bisa turun karena penyebutnya (jumlah pemain terlacak) bertambah, dan di Exophase ia berubah dalam lompatan diskret setiap kali data di-refresh. Tugas program adalah memberi lima kuantil untuk rate di waktu target — bukan satu angka tebakan — dan skornya dihitung dengan pinball loss di skala logit.

## Kenapa skala logit

Rate hidup di rentang 0–100, dan gerakan 0,1% → 0,2% jauh lebih berarti daripada 50,0% → 50,1%. Di skala logit, `logit(p) = ln(p / (1 - p))` dengan `p = rate / 100`, kedua gerakan itu diperlakukan setara secara relatif, dan ekstrapolasi tidak pernah menembus batas 0 atau 100 setelah diubah kembali dengan inverse logit. Karena pinball loss final juga dihitung di skala logit, memodelkan dan memberi kuantil langsung di skala ini membuat median dan sebarannya selaras dengan fungsi skornya: kuantil yang simetris di logit adalah kuantil yang jujur untuk loss tersebut.

Sebelum masuk logit, rate selalu di-clamp ke [0,01; 99,99] supaya logit-nya selalu terdefinisi.

## Membersihkan riwayat menjadi state

Membaca riwayat mentah apa adanya akan menghitung refresh yang sama berkali-kali. Program menelusuri history berurutan dan hanya menyimpan read bila pasangan `(players_tracked, seluruh rates)` berbeda dari state tersimpan terakhir. Tiap state mencatat jam sejak rilis (19 November 2026 00:00 UTC), rate trophy itu (state dilewati bila rate-nya null), jumlah pemain terlacak, dan jumlah peraih tersirat `e = rate/100 × N`.

## Tren per trophy

Untuk tiap trophy, dipasang garis `y = a + b·x` dengan `x = ln(1 + t_jam)` dan `y = logit(rate)`. Bentuk log-waktu dipilih karena pertumbuhan trophy melambat: lonjakan awal sesudah rilis besar, lalu makin landai. Regresinya terbobot waktu — bobot tiap state adalah selisih jam ke state berikutnya, dan state terakhir berbobot selisihnya ke checkpoint (minimal 0,5 jam) — supaya state yang mewakili rentang lama lebih berpengaruh daripada state sesaat. Dari fit ini didapat slope `b_i` dan simpangan residual `resid_i`. Bila datanya terlalu tipis (kurang dari 3 state, atau semua rate sama), slope dianggap 0; bila kurang dari 4 state, residual memakai nilai bawaan 0,25.

## Shrinkage ke slope gabungan

Slope trophy langka sangat berisik: dua-tiga peraih baru bisa membuat garisnya curam secara semu. Karena itu dihitung slope gabungan berupa median slope semua trophy yang sudah punya minimal 20 peraih, lalu slope tiap trophy dicampur menurut reliabilitas `rel = e_last / (e_last + 25)`:

```
b = rel × b_i + (1 − rel) × b_gabungan
```

Trophy dengan ratusan peraih hampir sepenuhnya mengikuti datanya sendiri; trophy dengan segelintir peraih menumpang tren umum.

## Median di waktu target

Median logit digeser dari posisi terakhir:

```
m = logit(max(r_last, floor_i)) + Δ
Δ = 0,8 × b × (ln(1 + t_target) − ln(1 + t_last)), dibatasi ke [−2,2; +2,2]
```

Faktor 0,8 dan pembatasan Δ adalah peredam yang disengaja: ekstrapolasi lurus selama 4,5 hari dari data 2 hari mudah berlebihan, dan skor pinball menghukum kuantil yang terlalu percaya diri lebih berat daripada yang sedikit konservatif. Bila sebuah trophy nyaris belum punya peraih (`e_last < 3`), rate terakhir diganti lantai kecil menurut tier-nya (platinum 0,02%, gold 0,05%, silver 0,10%, bronze 0,15%) supaya median tidak terkunci persis di nol. Trophy yang sudah jenuh (`r_last ≥ 99,99`) diberi kuantil tetap dekat langit-langit.

## Lebar sebaran yang jujur

Kuantil dibentuk sebagai `inv_logit(m + z·sd)` dengan `z = [−1,645; −0,674; 0; 0,674; 1,645]`. Simpangan `sd` menggabungkan tiga sumber ketidakpastian:

```
sd = sqrt( (0,34 × sqrt(horizon_hari))² + resid_i² + 1 / max(e_last, 1) )
```

- Suku horizon tumbuh dengan akar waktu: makin jauh targetnya, makin lebar.
- Suku residual membawa kegoyahan fit historis trophy itu sendiri.
- Suku `1/e_last` membuat trophy langka otomatis lebar, karena rate-nya bisa berlipat hanya oleh beberapa peraih baru.

Hasilnya dibatasi ke [0,42; 1,5] di skala logit. Ada satu pelebaran khusus: bila jumlah pemain terlacak tidak pernah berubah di seluruh riwayat — artinya refresh Exophase belum pernah terlihat — maka `sd` dinaikkan ke minimal 0,95, karena lompatan refresh pertama yang belum terjadi adalah sumber ketidakpastian terbesar yang belum terwakili di data.

Kombinasi ini yang membuat sebarannya jujur untuk pinball loss logit: interval tidak sekadar lebar tetap, melainkan melebar persis pada trophy dan horizon yang memang paling tidak pasti, dan menyempit hanya bila data historisnya stabil dan peraihnya banyak.

## Sifat program

- Deterministik: tidak ada keacakan, tidak ada jam dinding; urutan output mengikuti id trophy menaik.
- Kokoh terhadap kasus tepi: riwayat satu read, rate null, dan rate 0 di semua read semuanya ditangani tanpa crash.
- Offline dan hanya pustaka standar Python.
