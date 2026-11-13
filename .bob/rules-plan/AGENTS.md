# Project Architecture Rules (Non-Obvious Only)
- Depolama bellek içidir (`services/core/store.py` sözlükleri + `reports.py` içinde sqlite `:memory:`); kalıcı veritabanı kapsam dışıdır. v1 tek para birimi (TRY).
- Transfer akışı (`service.execute_transfer`) atomik olmalı: tüm doğrulamalar (hesaplar, bakiye, tutar > 0, gönderen != alıcı) yazmadan önce yapılır.
- Idempotency durumu `store.idempotency` içinde tutulur; `store.reset()` üçünü de temizler.
- M1 servisi `services/limits/` altında `services/core`'dan bağımsız olmalı, yeni bağımlılık eklememeli.
- Limit kuralları: dahil sınırlar; reddedilen işlem kullanıma/statement'a yazılmaz; iki ihlalde öncelik `PER_TRANSFER_LIMIT_EXCEEDED`; kullanım günler arası bağımsız.
- Tüm servisler tek hata zarfı kullanır (`ENGINEERING-HANDBOOK` §2); plana bu zarfı dahil edin.
- M4 (test görevi), M3'te oluşturulan custom mode ve skill'i kullanır; M8, önceki işlerin commit'lenmesini bekler.
