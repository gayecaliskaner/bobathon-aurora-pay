# Bakiye Özeti

Kaynak: `fixtures/data/customers.csv` (yalnızca `balance_try` sütunu toplulaştırıldı). Kişisel veri içermez.

| Metrik | Değer (TRY) |
|---|---|
| Müşteri sayısı | 20 |
| Toplam bakiye | 2,538,460.59 |
| Ortalama bakiye | 126,923.03 |
| En yüksek bakiye | 215,109.88 |
| En düşük bakiye | 26,720.86 |

Hesaplama `decimal.Decimal` ile yapılmıştır; ortalama `ROUND_HALF_UP` ile 2 ondalığa yuvarlanmıştır.
