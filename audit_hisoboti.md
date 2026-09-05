# Qarzly — Code & Architecture Audit Hisoboti

**Audit sanasi:** 2026-08-31  
**Audit turi:** statik kod tahlili, arxitektura auditi va lokal verifikatsiya  
**Qamrov:** Python/Aiogram bot, aiohttp API, Telegram Mini App, PostgreSQL
repositorylari, konfiguratsiya, testlar va deploy fayllari

## 1. Executive Summary

**Umumiy baho: 5/10.** Kod bazasida qatlamlar ancha yaxshi ajratilgan,
`asyncpg`/aiohttp orqali asinxron I/O ishlatilgan, SQL so'rovlari parametrli,
bot tokeni `SecretStr` bilan saqlangan va Telegram `initData` HMAC tekshiruvi
asosiy algoritm bo'yicha to'g'ri yozilgan. 50 ta mavjud test ham muvaffaqiyatli
o'tdi.

Shunga qaramay, loyiha hozirgi holatda moliyaviy ma'lumotlar bilan productionda
ishlash uchun yetarlicha xavfsiz emas. Eng katta xavflar:

1. `ADMIN_IDS` bo'sh bo'lsa tizim fail-open ishlaydi va har qanday haqiqiy
   Telegram foydalanuvchisi barcha mijozlar ma'lumotlarini o'qishi/o'zgartirishi
   mumkin.
2. Qarz va to'lov amallari yagona PostgreSQL transaction ichida emas. Oraliq
   xatoda qarz yangilanib, payment yozilmay qolishi yoki aralash valyutadagi
   qarzning faqat bir qismi saqlanishi mumkin.
3. Sana `DD.MM.YYYY` ko'rinishidagi `TEXT` sifatida saqlanadi va shu matn bo'yicha
   saralanadi. Bu FIFO to'lovni hamda “eng oxirgi qarz sanasi”ni noto'g'ri qiladi.
4. Uchta repository `pool` connectionini ushlab turib, qayta `pool.acquire()`
   qiladi. Yetarli parallel so'rovda pool to'liq band bo'lib, xizmat deadlock
   holatiga tushishi mumkin.

**Production qarori:** C-01–C-04 bartaraf qilinmaguncha moliyaviy yozuvlar uchun
release tavsiya etilmaydi.

### Kuchli tomonlar

- Composition root va domain/application/infrastructure/presentation ajratilishi
  umumiy yo'nalishda to'g'ri.
- Kodda `requests`, `time.sleep` yoki boshqa aniq bloklovchi I/O topilmadi.
- SQL qiymatlari `$1`, `$2`, ... placeholderlar bilan yuborilgan; aniqlangan SQL
  injection yo'q.
- `.env` git tomonidan ignore qilinadi va repository tarixida tracked `.env`
  topilmadi.
- Telegram `initData` imzosi `hmac.compare_digest` bilan tekshiriladi.
- DB pool, web runner va bot session uchun shutdown chaqiruvlari mavjud.

## 2. Aniqlangan muammolar

## 🔴 Critical

### C-01 — Authorization fail-open

**Dalil:**

- `bot/core/config.py:25-28` — `admin_ids` default qiymati bo'sh ro'yxat.
- `bot/presentation/middlewares/admin_middleware.py:32-34` — bo'sh bo'lsa barcha
  foydalanuvchiga ruxsat beradi.
- `bot/infrastructure/web/telegram_auth.py:73-75,104` — API ham xuddi shu rejimda
  har qanday haqiqiy Telegram foydalanuvchisini qabul qiladi.

**Ta'sir:** deploy paytida bitta environment variable unutilsa, mijozlarning ism,
telefon va qarz tarixi oshkor bo'ladi; foydalanuvchi qarz yaratishi, to'lov qilishi
va korzinani butunlay tozalashi ham mumkin.

**Tavsiya:** productionda bo'sh `ADMIN_IDS` bilan startupni rad etish. Ochiq rejim
faqat `ALLOW_OPEN_ACCESS=true` kabi alohida, ongli development flag bilan yoqilsin.
Destruktiv endpointlar uchun alohida rol va audit actor saqlansin.

### C-02 — Moliyaviy operatsiyalar atomik emas

**Dalil:**

- `bot/application/services/debt_service.py:153-165` — debt va initial payment
  ikkita mustaqil DB amali.
- `bot/application/services/debt_service.py:255-287` — full paymentda har bir debt
  update va payment insert alohida connection/transactionda.
- `bot/application/services/debt_service.py:317-386` — partial payment ham xuddi
  shunday.
- `bot/application/services/debt_service.py:216-236` — aralash valyutadagi qarzlar
  bittadan commit qilinadi.

`asyncio.Lock` (`debt_service.py:51`) faqat bitta Python process ichida amallarni
ketma-ketlashtiradi; rollback bermaydi, replica/deploy overlapini himoya qilmaydi
va PostgreSQL row lock o'rnini bosa olmaydi.

**Ta'sir:** DB yoki tarmoq xatosida qarz kamayadi-yu payment tarixi yozilmaydi;
birinchi valyutadagi qarz saqlanib, ikkinchisi xato bilan qolishi mumkin. Bir
nechta process ishlaganda lost update va ikki marta to'lov ehtimoli mavjud.

**Tavsiya:** har bir use-case bitta acquired connection va
`conn.transaction()` ichida bajarilsin. To'lanadigan debt qatorlari
`SELECT ... FOR UPDATE` bilan qulflansin. Unit of Work yoki transaction-aware
repository contract joriy qilinsin.

### C-03 — `TEXT` sana sabab FIFO va latest date noto'g'ri

**Dalil:**

- `bot/infrastructure/database/schema.py:33,60` — `debt_date` va `payment_date`
  `TEXT`.
- `bot/infrastructure/database/repositories/debt_repository.py:122` — FIFO
  `ORDER BY debt_date ASC` orqali.
- `bot/infrastructure/database/repositories/debt_repository.py:163` — latest date
  `MAX(debt_date)` orqali.
- `bot/application/common/formatters.py:140` — saqlanadigan format
  `DD.MM.YYYY`.

Reproduksiya natijasi:

```text
sorted(['31.01.2026', '01.02.2026', '15.12.2025'])
=> ['01.02.2026', '15.12.2025', '31.01.2026']

max(...)
=> '31.01.2026'
```

**Ta'sir:** qisman to'lov pulni real eng eski qarzga emas, matn bo'yicha “eng
kichik” qarzga ajratadi. Moliyaviy tarix va UI saralashi noto'g'ri bo'ladi.

**Tavsiya:** ustunlarni PostgreSQL `DATE` turiga migratsiya qilish, domainda
`datetime.date` ishlatish va faqat presentation qatlamida `DD.MM.YYYY` formatlash.

### C-04 — Nested pool acquisition pool deadlockiga olib keladi

**Dalil:**

- `bot/infrastructure/database/repositories/client_repository.py:17-30`
- `bot/infrastructure/database/repositories/debt_repository.py:53-93`
- `bot/infrastructure/database/repositories/payment_repository.py:27-51`

Har bir `add()` connectionni ushlab turgan holda `get_by_id()`/`_get_by_id()`ni
chaqiradi; ular esa yana `pool.acquire()` qiladi. Pool `max_size=10`
(`connection.py:35-36`). Masalan, 10 ta parallel client insert birinchi 10 ta
connectionni ushlab, har biri 11-connectionni kutib qolishi mumkin.

**Ta'sir:** yuqori parallel yukda requestlar `command_timeout`gacha osilib qoladi,
bot va APIning DBga bog'liq barcha funksiyalari to'xtaydi.

**Tavsiya:** `INSERT ... RETURNING` orqali barcha kerakli ustunlarni qaytarish va
shu rowni darhol entityga map qilish; yoki mavjud `conn`ni ichki metodga uzatish.

## 🟡 Major / Moderate

### M-01 — Idempotency yo'q

`POST /api/debts`, partial payment va bot tasdiqlash callbacklari request ID yoki
idempotency key saqlamaydi (`routes.py:324-349,426-457`,
`debt_creation.py:876-918`). Network retry, ikki marta bosish yoki qayta yuborilgan
so'rov dublikat qarz/to'lov yaratishi mumkin. `Idempotency-Key` uchun unique DB
yozuvi yoki Telegram update/callback ID asosida deduplication kerak.

### M-02 — Client identifikatsiyasi noto'g'ri birlashtirishi va dublikat yaratishi mumkin

`ClientService.get_or_create()` avval telefon, keyin faqat ism bo'yicha topadi
(`client_service.py:36-52`). Bir xil ismli ikki xil odam bitta clientga birlashadi.
Ayni paytda check-then-insert atomik emas va `clients.phone`/normalizatsiyalangan
identity uchun unique constraint yo'q (`schema.py:19-26,88-90`), shuning uchun
parallel request dublikat client yaratadi.

Telefonni asosiy identity sifatida unique partial index bilan ishlatish; telefonsiz
mijozni avtomatik faqat ism bo'yicha birlashtirmaslik; explicit client ID bilan
“mavjud mijozga qo'shish” oqimini ishlatish kerak.

### M-03 — Input validatsiyasi qatlamlar orasida bir xil emas

- `parse_money()` barcha raqam bo'lmagan belgilarni olib tashlaydi
  (`formatters.py:96-103`). Natija: `-100 -> 100`, `abc123 -> 123`, `1.5 -> 15`.
- Pydantic `min_length` stripdan oldin ishlaydi; `" "` client/product nomi DTOdan
  o'tib, keyin bo'sh stringka aylanadi (`routes.py:39-60,254,296`).
- `products` soni, `quantity`, `price_per_unit` va umumiy summa uchun upper bound
  yo'q. PostgreSQL `BIGINT` chegarasidan oshgan qiymat 500 xatoga olib keladi.
- Domain service `products` yo'li orqali kelgan nom, quantity va price invariantini
  mustaqil tekshirmaydi (`debt_service.py:78-83`).

Strict parser, whitespace-stripping constrained stringlar, maksimal 50 ta product,
BIGINTga mos upper bound va domainda qayta invariant tekshiruvi kerak.

### M-04 — Single-product USD yozuvida ichki valyuta UZS bo'lib qoladi

`DebtService.create_debt()` legacy/single-product yo'lida `DebtProduct` yaratganda
`currency=currency.value` uzatilmagan (`debt_service.py:92-98`). Natijada debt USD,
ammo `products_json` ichidagi product UZS bo'ladi. Hisobot Mini Appda product
narxini noto'g'ri valyutada ko'rsatishi mumkin. Mavjud test faqat debt valyutasini
tekshiradi, nested product valyutasini tekshirmaydi.

### M-05 — Multi-currency create oldindan to'liq validatsiya qilinmaydi

`create_debts()` guruhlarni ketma-ket saqlaydi (`debt_service.py:216-236`). Keyingi
guruhda validation xatosi chiqsa, avvalgi guruh saqlanib qoladi. Bundan tashqari,
exchange/given currencyga mos product guruhi bo'lmasa, deduction jimgina e'tiborsiz
qoladi. Avval barcha guruhlar uchun hisob-kitob va invariantlar tekshirilib, keyin
bitta transactionda yozilishi kerak.

### M-06 — Pagination faqat UI darajasida; DB va API barcha ma'lumotni yuklaydi

- `get_all_summaries()` barcha client, aggregate, latest date va barcha paid debt
  entitylarini xotiraga oladi (`client_service.py:69-73`).
- `/api/summaries`, `/api/debtors`, `/api/paid-debts`, `/api/trash` server-side
  limit/cursor ishlatmaydi (`routes.py:130-169,478-512,547-577`).
- Bot keyboard paginationi ham avval barcha summaryni yuklaydi
  (`debt_table.py:49-61,74-82`).

Ma'lumot ko'payganda latency, DB bandwidth va event-loop xotira bosimi oshadi.
Cursor/keyset pagination, bitta JOIN/CTE summary query va mos composite indekslar
kerak. `idx_debts_status` o'rniga asosiy access pattern uchun, masalan,
`(client_id, status, debt_date, id)` indeksini ko'rib chiqish lozim.

### M-07 — Horizontal scaling va FSM barqaror emas

`MemoryStorage` (`app.py:82`) restartda barcha wizard holatini yo'qotadi va bir
nechta replica orasida state almashmaydi. Long polling (`app.py:108`) bilan bir
bot tokenini bir nechta replica parallel ishlata olmaydi. Global mutation lock esa
barcha client write'larini bir processda ketma-ketlashtiradi.

Bir instansiya uchun bu ishlaydi, ammo high-load uchun Redis FSM storage, webhook,
queue/backpressure va DB transaction/row lock asosidagi concurrency kerak.

### M-08 — Trash oqimi hisobotni buzadi va payment audit tarixini o'chiradi

`get_all_by_client_id()` trashed debtlarni yashiradi (`debt_repository.py:109-110`),
lekin `get_by_client_id()` barcha paymentlarni qaytaradi
(`payment_repository.py:68-79`). `get_client_report()` shu ikkisini birga
agregatsiya qiladi (`debt_service.py:422-440`), shuning uchun trashdan keyin
to'lov jami ko'rsatilgan qarzlarga mos kelmaydi.

`purge_trash()` paymentlarni butunlay o'chiradi (`debt_repository.py:275-283`) va
trash archive payment tafsilotlarini saqlamaydi. Moliyaviy audit trail append-only
bo'lishi, soft-delete actor/time/reasonni saqlashi va payment tarixini yo'qotmasligi
kerak.

### M-09 — Startup migration xavfli va xatolarni yashiradi

Har startupda yettita `ALTER TABLE ... TYPE BIGINT` bajariladi
(`connection.py:50-67`). Bu schema lock olishi mumkin; barcha exceptionlar logsiz
yutiladi. Permission yoki schema xatosida app “muvaffaqiyatli ulandi” deb davom
etadi va keyin runtime yozuvlari yiqiladi.

Alembic yoki oddiy versionlangan SQL migration joriy qilish, migrationni deploy
bosqichida bir marta bajarish va xatoda fail-fast qilish kerak.

### M-10 — API abuse/flood himoyasi va replay hardening yetishmaydi

APIda per-user/IP rate limit, concurrency limit yoki mutation quota yo'q.
`initData` 24 soat davomida qayta ishlatilishi mumkin va kelajakdagi `auth_date`
rad etilmaydi (`telegram_auth.py:24,57-59`). HMAC to'g'ri, ammo age tekshiruvi
`-clock_skew <= age <= max_age` bo'lishi kerak. Mutationlar idempotency bilan
himoyalanishi, auth failurelar ham rate-limit qilinishi kerak.

PII javoblariga `Cache-Control: no-store` va `Vary: X-Telegram-Init-Data`, frontendga
esa Telegram/Google manbalarini aniq allowlist qilgan CSP qo'shish tavsiya etiladi.

### M-11 — Telegram flood control va uzun xabar boshqarilmagan

Outbound Telegram chaqiruvlari uchun `TelegramRetryAfter`/backoff siyosati yo'q.
Client report barcha tarixni bitta xabarga yig'adi (`debt_table.py:151-220`) va
Telegramning xabar uzunligi chegarasidan oshishi mumkin. Reportni sahifalash yoki
fayl sifatida yuborish, retry-after qiymatini hurmat qiladigan middleware kerak.

### M-12 — Observability incident tahlili uchun yetarli emas

Loglar oddiy matn (`core/logging.py:7-10`). “AUDIT” yozuvlarida operatsiyani bajargan
Telegram user ID, request/update ID, correlation ID va natija statusi yo'q
(`debt_service.py:167-178,293-298,405-413`). Prometheus metrikalari, Sentry/error
tracking, DB pool saturation va Telegram retry metrikalari mavjud emas.

Structured JSON log, PII redaction, actor/request ID va quyidagi metrikalar kerak:
request latency/error rate, DB acquire time, active pool connections, Telegram
429, mutation success/failure va scheduler health.

### M-13 — Testlar real PostgreSQL xulqini qamramaydi

50 ta test o'tadi, ammo service/API testlari `Fake*Repository` bilan ishlaydi
(`tests/conftest.py`). `test_migration.py` DBga migration bajarmaydi, faqat DDL
matnida substring tekshiradi. Shuning uchun C-02, C-03 va C-04 testlarda ushlanmaydi.

Testcontainers yoki CI PostgreSQL orqali repository integration, rollback,
concurrent payment, FIFO month/year boundary va pool saturation testlari kerak.

### M-14 — Startup/shutdown cleanup to'liq exception-safe emas

Asosiy `try/finally` faqat web server start bo'lgandan keyin boshlanadi
(`app.py:94-109`). `create_scheduler()` yoki `web_server.start()` xato qilsa, oldin
ochilgan resurslar ilova nazoratida yopilmaydi. Cleanup amallaridan bittasi xato
qilsa, keyingilari bajarilmaydi. `AsyncExitStack` yoki alohida guarded cleanup
bloklari tavsiya etiladi.

## 🟢 Minor / Style

1. `DebtProduct.currency` `str`, `Debt.currency` esa `Currency`; bitta kuchli type
   ishlatilsa mapping va validatsiya soddalashadi (`domain/entities/debt.py:33,126`).
2. JSON serialize/parse persistence tafsiloti domain entity modulida joylashgan
   (`domain/entities/debt.py:57-86`); buni infrastructure mapperga ko'chirish
   qatlam chegarasini tozalaydi.
3. `debt_creation.py` 1 081 qator, `routes.py` 653 qator va frontend JS qariyb
   2 000 qator. Use-case/DTO/serializer/routerlarni feature modullariga ajratish
   test va reviewni yengillashtiradi.
4. README hali ayrim joylarda Async SQLite, `DATABASE_PATH` va ephemeral SQLite
   deployini tasvirlaydi (`README.md:66,94,123,196-206`), kod esa PostgreSQL
   `DATABASE_URL` ishlatadi. Operatsion hujjat yangilanishi kerak.
5. Dependencylar faqat `>=` bilan berilgan va lock/hash yo'q
   (`requirements.txt`, `pyproject.toml:6-13`). Reproducible build uchun lock va
   avtomatik dependency/security update jarayoni kerak.
6. `database_url` ham credential bo'lgani uchun `SecretStr` yoki redacted DSN type
   bilan saqlanishi, production TLS majburiy tekshirilishi kerak
   (`core/config.py:38`).
7. Ruff 3 ta `E501` topdi: `client_service.py:88`,
   `tests/test_client_service.py:91`, `tests/test_web_api.py:599`.
8. Aiohttp testlarda string app/request keylar sabab 29 ta `NotAppKeyWarning`
   chiqdi. Typed `web.AppKey` ishlatish tavsiya etiladi.
9. `DebtService.debts` property ishlatilmaydi va repositoryni tashqariga ochadi
   (`debt_service.py:448-450`). Olib tashlash mumkin.
10. `supabase/.temp/linked-project.json` tracked. Bu secret emas, ammo lokal
    tool metadatasini repositoryda saqlash zarurati qayta ko'rib chiqilsin.

## 3. “Oldin / Keyin” kod namunalari

Quyidagi kodlar yo'nalishni ko'rsatadi; production migratsiya va repository
contractlari bilan moslashtirib joriy qilinishi kerak.

### 3.1 Sana: matndan `DATE`ga

**Oldin:**

```sql
debt_date TEXT NOT NULL
```

```python
ORDER BY debt_date ASC, id ASC
```

**Keyin:**

```sql
ALTER TABLE debts ADD COLUMN debt_date_v2 DATE;

UPDATE debts
SET debt_date_v2 = TO_DATE(debt_date, 'DD.MM.YYYY');

ALTER TABLE debts ALTER COLUMN debt_date_v2 SET NOT NULL;
CREATE INDEX idx_debts_client_fifo
    ON debts (client_id, status, debt_date_v2, id);
```

```python
from datetime import date

@dataclass(frozen=True, slots=True)
class Debt:
    debt_date: date

# SQL
ORDER BY debt_date ASC, id ASC

# Faqat UI uchun
display_date = debt.debt_date.strftime("%d.%m.%Y")
```

Migratsiyadan oldin `TO_DATE(... )` round-trip orqali barcha eski qiymatlar
haqiqiy sana ekanini tekshirish zarur.

### 3.2 Partial payment: bitta transaction va row lock

**Oldin:**

```python
active_debts = await debts.get_active_by_client_id(client_id)
await debts.update_remaining_debt(debt_id, new_remaining, new_status)
await payments.add(payment)
```

**Keyin:**

```python
async def apply_partial_payment(
    pool: asyncpg.Pool,
    *,
    client_id: int,
    amount: int,
    currency: Currency,
    payment_date: date,
) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT id, remaining_debt
                FROM debts
                WHERE client_id = $1
                  AND currency = $2
                  AND status = 'active'
                  AND remaining_debt > 0
                ORDER BY debt_date, id
                FOR UPDATE
                """,
                client_id,
                currency.value,
            )

            available = sum(row["remaining_debt"] for row in rows)
            if amount <= 0 or amount > available:
                raise ValueError("To'lov summasi mavjud qarzga mos emas")

            left = amount
            for row in rows:
                if left == 0:
                    break
                paid = min(left, row["remaining_debt"])
                remaining = row["remaining_debt"] - paid

                await conn.execute(
                    """
                    UPDATE debts
                    SET remaining_debt = $1,
                        status = CASE WHEN $1 = 0 THEN 'paid' ELSE 'active' END,
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    remaining,
                    row["id"],
                )
                await conn.execute(
                    """
                    INSERT INTO payments
                        (client_id, debt_id, amount, currency, payment_type, payment_date)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    client_id,
                    row["id"],
                    paid,
                    currency.value,
                    "full" if remaining == 0 else "partial",
                    payment_date,
                )
                left -= paid
```

### 3.3 Nested connectionni yo'qotish

**Oldin:**

```python
async with self._pool.acquire() as conn:
    row = await conn.fetchrow("INSERT ... RETURNING id", ...)
    return await self.get_by_id(row["id"])
```

**Keyin:**

```python
async with self._pool.acquire() as conn:
    row = await conn.fetchrow(
        f"""
        INSERT INTO debts (...)
        VALUES (...)
        RETURNING {_SELECT_COLS}
        """,
        ...,
    )

if row is None:
    raise RuntimeError("Qarz saqlanmadi")
return self._map_row(row)
```

Shu pattern client va payment repositorylariga ham qo'llanadi.

### 3.4 Fail-closed konfiguratsiya

**Oldin:**

```python
admin_ids: list[int] | str = Field(default_factory=list)

if not self._settings.admin_ids:
    return await handler(event, data)
```

**Keyin:**

```python
from pydantic import model_validator

class Settings(BaseSettings):
    admin_ids: list[int]
    allow_open_access: bool = False

    @model_validator(mode="after")
    def require_authorization(self) -> "Settings":
        if not self.admin_ids and not self.allow_open_access:
            raise ValueError("ADMIN_IDS majburiy; ochiq rejim explicit yoqilishi kerak")
        return self
```

Production deploy policy `ALLOW_OPEN_ACCESS=false` qiymatini majburlashi kerak.

### 3.5 Strict input va miqdor chegaralari

**Oldin:**

```python
cleaned = re.sub(r"[^\d]", "", text.strip())
return int(cleaned)
```

**Keyin:**

```python
_MONEY_RE = re.compile(r"^[0-9]+(?:[ _.,][0-9]{3})*$")

def parse_money(text: str) -> int | None:
    value = text.strip()
    if not _MONEY_RE.fullmatch(value):
        return None
    parsed = int(re.sub(r"[ _.,]", "", value))
    return parsed if 0 <= parsed <= 9_000_000_000_000_000_000 else None
```

```python
from typing import Annotated
from pydantic import ConfigDict, StringConstraints

NonBlankName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]

class ProductItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonBlankName
    quantity: int = Field(ge=1, le=1_000_000)
    price_per_unit: int = Field(gt=0, le=9_000_000_000_000)

class CreateDebtDTO(BaseModel):
    products: list[ProductItemDTO] = Field(min_length=1, max_length=50)
```

## 4. Qadamma-qadam Action Plan

### 0–2 kun: release blockerlar

1. Production backup/snapshot olish va C-01 tuzatilguncha `ADMIN_IDS`ni majburiy
   tekshirish.
2. `debt_date`/`payment_date`ni `DATE`ga xavfsiz migratsiya qilish; month/year
   boundary testlarini qo'shish.
3. Create debt, multi-currency create, full payment va partial paymentni bitta DB
   transactionga o'tkazish; `FOR UPDATE` ishlatish.
4. Uchta repositorydagi nested pool acquisitionni `RETURNING` row bilan yo'qotish.
5. Destruktiv purge oldidan backup mavjudligini tekshirish; payment tarixini
   o'chirmaydigan modelga o'tguncha endpointni vaqtincha cheklash.

### 3–7 kun: ma'lumot yaxlitligi va regressiya himoyasi

6. Idempotency key/update deduplication va unique constraintlarni joriy qilish.
7. Client identity qoidalarini aniqlab, same-name merge va parallel duplicate
   holatlarini tuzatish.
8. Strict money/name/product validation, upper bound va DB `CHECK` constraintlar
   qo'shish.
9. Single-product USD va multi-currency atomicity xatolarini tuzatish.
10. Real PostgreSQL bilan integration/concurrency test suite yaratish.

### 1–4 hafta: scalability va operatsion barqarorlik

11. Summary/report querylarini optimallashtirish, keyset pagination va composite
    indekslarni `EXPLAIN (ANALYZE, BUFFERS)` bilan tekshirish.
12. Redis FSM storagega o'tish; horizontal scaling kerak bo'lsa webhook va queue
    arxitekturasini joriy qilish.
13. API rate limit, timeout, idempotency, no-store/Vary/CSP headerlarini qo'shish.
14. Telegram `RetryAfter`/backoff va uzun report paginationini qo'shish.
15. Structured log, actor/request ID, Sentry va Prometheus metrikalarini ulash.

### Keyingi bosqich

16. Versionlangan migration vositasi va alohida deploy migration job yaratish.
17. `routes.py`, `debt_creation.py` va frontend JSni feature modullariga ajratish.
18. Dependency lock, CI pipeline (`pytest`, PostgreSQL integration, `ruff`, strict
    `mypy`, dependency scan) va backup/restore drill joriy qilish.
19. README va deploy hujjatini PostgreSQL arxitekturasiga moslashtirish.

## 5. Verifikatsiya natijalari

| Tekshiruv | Natija |
|---|---|
| `.venv/bin/python -m pytest -q` | **50 passed**, 29 aiohttp `NotAppKeyWarning` |
| `.venv/bin/python -m mypy bot tests` | **Success**, 68 source file |
| `.venv/bin/python -m ruff check .` | **Failed:** 3 ta `E501` |
| Secret hygiene | `.env` ignored, tracked `.env` yoki real token topilmadi |
| Blocking I/O qidiruvi | Bot kodida aniq `time.sleep`, `requests`, sync DB topilmadi |

### Audit cheklovlari

- Live Supabase/PostgreSQLga ulanilmadi va production ma'lumotlari o'qilmadi.
- Load test, `EXPLAIN ANALYZE`, network/TLS va Render runtime testi bajarilmadi.
- Lokal test virtual environment Python 3.14 bilan ishladi; Render konfiguratsiyasi
  Python 3.11.9. CI aynan production Python versiyasida ham ishlashi kerak.
- BotFather/Webhook/Render/Supabase tashqi sozlamalari koddan tashqarida bo'lgani
  uchun faqat repositorydagi konfiguratsiya bo'yicha baholandi.
