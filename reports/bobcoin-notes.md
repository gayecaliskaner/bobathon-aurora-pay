# Bob Coin Kullanım Notu — 13 Kasım 2026

Proje: `gayecaliskaner/bobathon-aurora-pay`
Tarih: 2026-11-13

---

## Bobalytics (Son 24 Saat)

| Metrik | Değer |
|---|---|
| **Toplam harcanan Bob Coin** | **20.35** |
| Değişim (önceki döneme göre) | +188% |
| Toplam satır (Bob lines) | 471 |
| Kullanıcı satırı (User lines) | 0 |
| Bob commit oranı | %100,0 |
| Bob commit sayısı | 1 |

> Kaynak: Bobalytics > Metrics > Bobcoin spend ekran görüntüsü (13 Kasım 2026)

---

## Oturum Bazlı Harcamalar

| Oturum | Task ID | Zaman | Harcama | Araç Çağrısı | Süre | Durum |
|---|---|---|---|---|---|---|
| bob-run.json | `9b64432256a1…` | 08:32 UTC | **0.2616** | 5 | 33 sn | ✅ success |
| bob-run-2.json | `1ab64cbb1ac9…` | 08:36 UTC | **0.1458** | 4 | 10 sn | ✅ success |
| **Toplam (oturumlar)** | — | — | **0.4074** | 9 | 43 sn | — |

---

## Özet

- Bugün toplam **20.35 Bob Coin** harcandı (Bobalytics verisi, son 24 saat).
- Yerel oturum kayıtlarına yansıyan tutar **0.41 Bob Coin** (iki task).
- Fark, diğer oturumlar veya önceki çalışmalardan kaynaklanıyor olabilir.
- Tüm commit'ler Bob tarafından yapılmış (%100 Bob commit oranı).

---

## Task Başına `--max-cost` / `--max-turns` Önerisi

Gözlemlenen oturum verileri ve görev türlerine göre aşağıdaki sınırlar önerilmektedir:

| Görev Türü | Örnek | `--max-cost` | `--max-turns` | Gerekçe |
|---|---|---|---|---|
| **Bilgi / Açıklama** | Modül HTML açıklaması, soru yanıtlama | `0.30` | `5` | Düşük araç çağrısı (ortalama 5), kısa döngü |
| **Küçük Kod Değişikliği** | Tek fonksiyon düzeltme, yeni endpoint | `0.50` | `10` | Okuma + yazma + doğrulama üçlüsü |
| **Orta Ölçekli Özellik** | Yeni servis/modül, refactor | `1.00` | `20` | Birden fazla dosya, test çalıştırma |
| **Büyük / Çok Adımlı Görev** | Güvenlik taraması + düzeltme, migration | `2.00` | `40` | Subagent, CI döngüsü, iteratif düzeltme |
| **Araştırma / Raporlama** | Bobalytics özeti, doküman üretimi | `0.40` | `8` | Çoğunlukla okuma ağırlıklı |

### Kullanım

Bob CLI'dan task çalıştırırken:

```bash
bob run --max-cost 0.50 --max-turns 10 "küçük bir endpoint ekle"
```

`.bob/config.yaml` ile proje geneli varsayılan belirleme:

```yaml
defaults:
  max_cost: 1.00
  max_turns: 20
```

### Gözlemlerden Çıkan Kurallar

- **bob-run.json:** 5 araç çağrısı, 33 sn, 0.26 coin → açıklama görevi `--max-cost 0.30` ile güvenle çalışır.
- **bob-run-2.json:** 4 araç çağrısı, 10 sn, 0.15 coin → araştırma görevi `--max-cost 0.20` yeterli olurdu; ancak `0.30` güvenli tampon sağlar.
- Günlük toplam (20.35 coin) göz önüne alındığında, **task başına ortalama ~1 coin** hedeflenmesi bütçeyi dengeler.
- `--max-turns` aşımında görev yarıda kesilir (bkz. bob-run-2.json `max 3 turns` hatası); kritik görevlerde `--max-turns` değeri cömert tutulmalı, `--max-cost` ile sınırlandırılmalıdır.
