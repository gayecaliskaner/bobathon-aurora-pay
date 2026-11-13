## Açıklama
<!-- Değişiklikleri kısaca anlatın: Ne değişti ve neden? -->

## Değişiklik Türü
- [ ] Yeni özellik (feature)
- [ ] Hata düzeltme (bugfix)
- [x] Yeniden yapılandırma (refactor / clean architecture)
- [ ] Dokümantasyon / Test / Altyapı

## Kontrol Listesi
- [x] `pytest` yeşil ve tüm testler başarılı
- [x] Test kapsamı (coverage) >= %85
- [x] Güvenlik taraması (`./scripts/scan.sh`) 0 bulgu
- [x] Para işlemleri `Decimal` ile yapıldı, `float` kullanılmadı
- [x] Hatalar standart hata zarfı (`{"error": {"code": "...", "message": "..."}}`) ile dönüyor
- [x] Log'larda kişisel veri (PII) yok
- [x] Kodda veya repoda gizli bilgi (secret) yok
- [x] Clean architecture ve katmanlı mimari standartlarına uyuldu

## İlgili Issue'lar
<!-- İlgili issue numaraları veya ticket'lar: INCIDENT-2041, SEC-317, PRD-limits -->
