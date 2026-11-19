# gta6-trophy-rarity-forecast
[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/xbaystore/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/xbaystore/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

## Ringkasan

Program ini memprediksi persentase pemain GTA VI yang akan meraih tiap trophy pada waktu target di masa depan. Untuk setiap berkas kasus `*.in` di direktori input, program membaca riwayat rate trophy dari Exophase, memodelkan pertumbuhannya, lalu menulis berkas `<id>.out` berisi lima kuantil (5%, 25%, 50%, 75%, 95%) untuk setiap trophy dalam kasus tersebut.

Program berjalan sepenuhnya offline, hanya memakai pustaka standar Python, deterministik (dua kali jalan menghasilkan byte yang identik), dan dirancang selesai jauh di bawah batas 8 detik per kasus.

## Menjalankan secara lokal

```bash
export MAKEFUN_INPUT_DIR=/path/ke/input
export MAKEFUN_OUTPUT_DIR=/path/ke/output
python3 main.py
```

Bila variabel lingkungan tidak disetel, program memakai `/input` sebagai direktori input dan `/output` sebagai direktori output. Setiap berkas `*.in` diproses satu per satu; hasilnya ditulis sebagai `<id>.out` di direktori output dengan format JSON `{"trophies": [{"id": ..., "q": [q05, q25, q50, q75, q95]}, ...]}`.

## Ringkasan metode

Forecast dikerjakan di skala logit supaya perubahan dekat 0% dan 100% diperlakukan secara simetris. Riwayat dibaca sebagai rangkaian state yang benar-benar berubah, lalu untuk tiap trophy dipasang garis logit terhadap `ln(1 + jam sejak rilis)` dengan regresi terbobot waktu. Slope tiap trophy dikecilkan (shrinkage) ke arah slope gabungan dari trophy-trophy yang sudah punya cukup banyak peraih, sehingga trophy langka tidak liar hanya karena datanya tipis. Median digeser dari rate terakhir dengan perubahan logit yang teredam dan dibatasi, sementara lebar sebaran kuantil menggabungkan ketidakpastian horizon, residual fit, dan kelangkaan peraih — termasuk pelebaran ekstra bila jumlah pemain terlacak belum pernah berubah sama sekali. Penjelasan lengkap ada di `METHOD.md`.
