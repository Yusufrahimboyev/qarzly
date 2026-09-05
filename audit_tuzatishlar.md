# Qarzly — Audit topilmalari bo'yicha bajarilgan tuzatishlar

**Sana:** 2026-08-31
**Manba:** [audit_hisoboti.md](audit_hisoboti.md)
**Verifikatsiya:** 86 test o'tdi (8 integration test skip — DB yo'q),
`ruff check .` toza, `mypy bot tests` xatosiz.

## 1. Critical

### ✅ C-01 — Authorization fail-open → fail-closed

- `bot/core/config.py` — `ADMIN_IDS` bo'sh bo'lsa `Settings` validatsiyasi
  ilovani ishga tushirmaydi. Ochiq rejim faqat yangi `ALLOW_OPEN_ACCESS=true`
  flagi bilan ongli yoqiladi.
- `bot/presentation/middlewares/admin_middleware.py` — bo'sh ro'yxat endi
  "hammaga ruxsat" emas, "kirish yo'q" degani.
- `bot/infrastructure/web/telegram_auth.py` — API ham xuddi shu qoidada;
  ro'yxatsiz kirish 403 bilan rad etiladi.
- `database_url` endi `SecretStr` — log va traceback'da DSN ochilmaydi.
- Destruktiv amallarda (`trash/move`, `trash/restore`, `trash/purge`) actor
  Telegram ID si audit logga va `trash.deleted_by` ustuniga yoziladi.
- Testlar: `tests/test_config.py`.

### ✅ C-02 — Moliyaviy operatsiyalar endi atomik

- Yangi `UnitOfWork` abstraktsiyasi (`bot/domain/repositories/unit_of_work.py`)
  va uning PostgreSQL implementatsiyasi
  (`bot/infrastructure/database/unit_of_work.py`): bitta connection, bitta
  tranzaksiya, unga bog'langan repository'lar.
- `DebtService.create_debt`, `create_debts`, `pay_full_debt`,
  `pay_partial_debt` — har biri bitta tranzaksiyada. Xatoda hammasi rollback
  bo'ladi (qarz kamayib, to'lov yozilmay qolmaydi).
- To'lanadigan qatorlar `SELECT ... FOR UPDATE` bilan qulflanadi
  (`get_active_by_client_id(for_update=True)`) — lost update va ikki karra
  to'lov yo'q.
- Global `asyncio.Lock` olib tashlandi: u rollback bermas, replica'lar
  orasida ishlamas va barcha yozuvlarni bitta processda navbatga qo'yardi.
- Testlar: `tests/integration/test_pg_repositories.py`
  (`test_failed_use_case_rolls_back_everything`,
  `test_concurrent_partial_payments_do_not_overdraw`).

### ✅ C-03 — Sana `TEXT` → `DATE`

- Domain: `Debt.debt_date` va `Payment.payment_date` endi `datetime.date`.
- Baza: `debts.debt_date`, `payments.payment_date`, `trash.debt_date` — `DATE`.
- Migratsiya `002_date_columns` avval barcha qiymatlar `DD.MM.YYYY`
  formatida ekanini tekshiradi va mos kelmasa deploy'ni to'xtatadi
  (jimgina noto'g'ri konvertatsiya qilmaydi).
- Formatlash faqat presentation chegarasida: `format_date()` (bot xabarlari,
  API javoblari `DD.MM.YYYY` ko'rinishida qoladi — frontend o'zgarmadi).
- FIFO uchun `idx_debts_client_fifo (client_id, status, debt_date, id)`.
- Testlar: `test_fifo_across_month_and_year_boundary`,
  `test_date_sorting_is_chronological`, `test_debt_date_is_stored_as_date_object`.

### ✅ C-04 — Nested pool acquisition yo'qotildi

- Barcha repository'lar endi `Executor` (pool **yoki** tranzaksiya
  connection'i) ustida ishlaydi va o'zi hech qachon `pool.acquire()`
  chaqirmaydi (`repositories/executor.py`).
- `add()` metodlari `INSERT ... RETURNING <barcha ustunlar>` bilan bitta
  so'rovda entity qaytaradi (ilgari ikkinchi connection so'rardi).
- Test: `test_concurrent_inserts_do_not_exhaust_pool` (pool 5, 20 parallel
  insert, timeout bilan).

## 2. Major / Moderate

| ID | Holat | Nima qilindi |
|---|---|---|
| M-01 Idempotency | ✅ | `idempotency_keys` jadvali + `IdempotencyStore`; `POST /api/debts` va `POST /api/payments` `Idempotency-Key` header'ini qo'llab-quvvatlaydi (takror so'rov birinchi javobni qaytaradi, 409 — hali bajarilayotgan so'rov uchun). Mini App kalitni avtomatik yuboradi. |
| M-02 Client identity | ✅ | Telefon — asosiy identity: `ON CONFLICT` bilan atomik get-or-create + `uq_clients_phone` partial unique index. Telefonli mijoz endi faqat ism bo'yicha birlashtirilmaydi; telefonsizlar faqat telefonsizlar bilan solishtiriladi. |
| M-03 Input validatsiya | ✅ | Qat'iy `parse_money` (`-100`, `abc123`, `1.5` → `None`); `strip_whitespace` li DTO stringlari; `extra="forbid"`; miqdor/narx/summa uchun yuqori chegaralar; maksimal 50 tovar; domain `DebtProduct.validate()` va DB `CHECK` constraintlar. |
| M-04 Single-product USD | ✅ | `create_debt()` single-product yo'lida tovarga qarz valyutasi beriladi; `DebtProduct.currency` endi `Currency` tipida. Test: `test_single_product_usd_keeps_currency_inside_product`. |
| M-05 Multi-currency create | ✅ | Barcha guruhlar avval hisoblanadi va tekshiriladi (`_DebtPlan`), keyin bitta tranzaksiyada yoziladi. Mos valyutadagi tovarsiz exchange/berilgan pul endi jimgina yo'qolmaydi — xato qaytadi. |
| M-06 Pagination | 🟡 qisman | `get_all_paid`/`get_all_trashed` DB darajasida `LIMIT/OFFSET`; API'da `?limit=&offset=` (default 200, maks 1000); `get_all_summaries` endi barcha yopilgan qarzlarni emas, engil agregat (`get_client_ids_with_paid_debts`) oladi; FIFO composite indeks qo'shildi. Keyset (cursor) pagination va bitta JOIN/CTE summary query hali qilinmadi. |
| M-07 Horizontal scaling / FSM | ⬜ qilinmadi | Redis FSM storage, webhook va queue — infratuzilma qarori. Kod bir instansiya uchun to'g'ri ishlaydi; concurrency endi DB tranzaksiya va row lock bilan himoyalangan (global lock emas). |
| M-08 Trash / audit trail | ✅ | Hisobot korzinadagi qarzlarning to'lovlarini jamiga qo'shmaydi; `purge_trash()` to'lovlarni o'chirishdan oldin `trash_payments` arxiviga ko'chiradi; `deleted_by` (actor) saqlanadi; mijoz faqat qarzi ham, to'lovi ham qolmaganda o'chiriladi. |
| M-09 Startup migration | ✅ | `schema_migrations` bilan versiyalangan migratsiyalar; bitta tranzaksiya + `pg_advisory_xact_lock` (transaction-mode pooler uchun to'g'ri); har qadam savepoint'da; majburiy qadam xatosida fail-fast; `APPLY_MIGRATIONS=false` bilan deploy job'ga chiqarish mumkin. |
| M-10 API abuse / replay | ✅ | Foydalanuvchi va IP bo'yicha sliding-window rate limit (429 + `Retry-After`), autentifikatsiya xatolari ham hisobga olinadi; `auth_date` oralig'i `-clock_skew <= age <= max_age`; PII javoblarida `Cache-Control: no-store` va `Vary: X-Telegram-Init-Data`; Telegram/Google Fonts allowlist qilingan CSP. |
| M-11 Telegram flood / uzun xabar | ✅ | `RetryAfterMiddleware` — `TelegramRetryAfter` qiymatini hurmat qiladi, tarmoq/server xatolarida eksponensial backoff; mijoz hisoboti 4096 belgidan oshsa `split_message()` bilan bo'laklarga bo'lib yuboriladi. |
| M-12 Observability | 🟡 qisman | `LOG_JSON=true` bilan structured JSON loglar; AUDIT yozuvlarida actor ID; API xatolarida actor ID. Prometheus metrikalari va Sentry ulanmadi (yangi dependency va tashqi xizmat talab qiladi). |
| M-13 Integration testlar | 🟡 qisman | `tests/integration/` yozildi: sxema turlari, SQL FIFO, rollback, parallel to'lov, pool saturation, dublikat telefon, purge arxivi. `TEST_DATABASE_URL` berilmasa skip bo'ladi — lokal muhitda PostgreSQL/Docker yo'qligi sababli ishga tushirilmadi. |
| M-14 Startup/shutdown | ✅ | `AsyncExitStack` — resurslar ochilgan tartibda teskari yopiladi, bitta cleanup xatosi qolganlarini to'xtatmaydi (`_closing` helper). |

## 3. Minor / Style

1. ✅ `DebtProduct.currency` — `Currency` tipida (matn kelsa avtomatik keltiriladi).
2. ✅ JSON serializatsiya domaindan `infrastructure/database/mappers/products.py` ga ko'chirildi.
3. 🟡 Fayllarni feature modullariga bo'lish (`debt_creation.py`, `routes.py`, `app.js`) — qilinmadi; routes ichida yordamchilar ajratildi.
4. ✅ README PostgreSQL arxitekturasiga moslashtirildi (SQLite/`DATABASE_PATH` yo'q), yangi env o'zgaruvchilar va test buyruqlari qo'shildi.
5. ✅ Dependencylar `~=` (compatible release) bilan cheklandi.
6. ✅ `database_url` — `SecretStr`.
7. ✅ Ruff `E501` xatolari tuzatildi.
8. ✅ Typed `web.AppKey` / `web.RequestKey` — 29 ta `NotAppKeyWarning` yo'q.
9. ✅ Ishlatilmagan `DebtService.debts` property olib tashlandi.
10. ✅ `supabase/.temp/` git'dan chiqarildi va `.gitignore` ga qo'shildi.

## 4. Deploy oldidan bajarilishi kerak

1. **`ADMIN_IDS` ni sozlang.** Aks holda ilova ishga tushmaydi (ataylab).
2. **Baza backup/snapshot oling.** `002_date_columns` migratsiyasi
   `debt_date`/`payment_date` ustunlarini `DATE` ga o'zgartiradi.
3. Migratsiyani ishga tushiring (startupda avtomatik yoki
   `APPLY_MIGRATIONS=false` bilan alohida job'da). Sana ustunlari ikki
   bosqichda tekshiriladi: (a) format `DD.MM.YYYY` mi, (b) `to_date` →
   `to_char` round-trip aynan bir xil qiymat qaytaradimi (mavjud bo'lmagan
   `31.02.2026` kabi sana jimgina surilib ketmasligi uchun). Muammo topilsa
   migratsiya to'xtaydi, nechta yozuv muammoli ekanini aytadi va **hech narsa
   o'zgarmaydi** — avval o'sha yozuvlarni tuzating.
4. `005_clients_phone_unique` ixtiyoriy: bazada dublikat telefonlar bo'lsa
   index qo'yilmaydi va ERROR log yoziladi. Dublikatlarni birlashtirgach,
   keyingi startupda avtomatik qo'yiladi.
5. Integration testlarni CI da haqiqiy PostgreSQL bilan ishga tushiring
   (`TEST_DATABASE_URL`) — ular aynan C-02/C-03/C-04 regressiyalarini ushlaydi.
   ⚠️ Bu testlar jadvallarni TRUNCATE qiladi, shuning uchun faqat alohida test
   bazasini ko'rsating: DSN nomida "test" bo'lmasa testlar ishlamaydi.

## 5. Ma'lumot xavfsizligi — nima o'chadi, nima o'chmaydi

| Amal | Mavjud ma'lumotga ta'siri |
|---|---|
| Sxema init (`CREATE TABLE IF NOT EXISTS`) | Hech narsa (mavjud jadvallar tegilmaydi) |
| `001_bigint_columns` | Ustun turi kengayadi, qiymatlar o'zgarmaydi |
| `002_date_columns` | Sana matndan `DATE` ga aylantiriladi — **qatorlar o'chmaydi**. Xato topilsa butun tranzaksiya rollback bo'ladi |
| `003_money_check_constraints` | `NOT VALID` — eski qatorlar tekshirilmaydi va o'chirilmaydi |
| `004_trash_actor_columns` | Yangi bo'sh ustun qo'shiladi |
| `005_clients_phone_unique` | Faqat index. Dublikat telefon bo'lsa index qo'yilmaydi (ilova ishlayveradi), yozuvlar o'chirilmaydi |
| Mijoz identity qoidasi (M-02) | Faqat **yangi** qarz qo'shishga ta'sir qiladi; mavjud mijozlar birlashtirilmaydi ham, o'chirilmaydi ham |
| `purge_trash()` | Yagona o'chiruvchi amal — **ilgari ham bor edi**. Endi to'lovlar avval `trash_payments` arxiviga ko'chiriladi va to'lovi bor mijoz o'chirilmaydi (ya'ni eski koddan xavfsizroq) |

**Rollback (agar kodni orqaga qaytarish kerak bo'lsa):** eski kod sanani matn
deb kutadi, shuning uchun ustunlarni ham qaytarish kerak — ma'lumot yo'qolmaydi:

```sql
ALTER TABLE debts    ALTER COLUMN debt_date    TYPE TEXT USING to_char(debt_date, 'DD.MM.YYYY');
ALTER TABLE payments ALTER COLUMN payment_date TYPE TEXT USING to_char(payment_date, 'DD.MM.YYYY');
ALTER TABLE trash    ALTER COLUMN debt_date    TYPE TEXT USING to_char(debt_date, 'DD.MM.YYYY');
DELETE FROM schema_migrations WHERE version = '002_date_columns';
```
