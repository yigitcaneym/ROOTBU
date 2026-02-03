# ROOT Tek-Tuş Kurulum Aracı

Bu küçük uygulama, ROOT yazılımını tek tuşla kurmak ve aynı arayüz üzerinden tekrar açmak için hazırlanmıştır.

## Özellikler

- **Windows 10 (19041+)**: PowerShell üzerinden WSL kurulumu.
- **Linux (Ubuntu)**: Miniconda + ROOT kurulumu ve ROOT'u başlatma.

## Çalıştırma

```bash
python3 root_installer.py
```

## Notlar

- Linux kurulumundan sonra terminali kapatıp yeniden açmanız gerekir.
- ROOT'u her açışınızda terminalde şu komutları çalıştırın:

```bash
conda activate root_env
root
```

Arayüzdeki butonlar, yukarıdaki komutları sizin yerinize otomatik olarak çalıştırır.
