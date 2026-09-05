# Qarzly — Keyingi qadamlar (deploy oldidan bajariladigan ishlar)

**Yaratildi:** 2026-09-02
**Bog'liq hujjatlar:** [audit_hisoboti.md](audit_hisoboti.md) (topilmalar) ·
[audit_tuzatishlar.md](audit_tuzatishlar.md) (nima tuzatilgani)

Kod tayyor va toza (86 test o'tadi, `ruff` va `mypy` xatosiz), ammo **haqiqiy
PostgreSQL va haqiqiy Telegram bilan hali sinalmagan**. Quyidagi tartib aynan
shu bo'shliqni yopadi. Tartib muhim: **A → B → C → D**.

---

## Umumiy checklist

- [ ] **A.** Supabase bazasini faqat o'qish (SELECT) so'rovlari bilan tekshirish
- [ ] **B.** Lokal PostgreSQL o'rnatib, integration testlarni ishga tushirish
- [ ] **C.** O'zgarishlarni alohida branch'ga commit qilish
- [ ] **D.** Backup → env o'zgaruvchilar → deploy → deploydan keyingi tekshiruv
- [ ] **E.** (zaxira) Kerak bo'lsa rollback
- [ ] **F.** Qolgan audit ishlari (M-06 / M-07 / M-12 va refactor)

---

## A. Supabase bazasini tekshirish (faqat SELECT — hech narsa o'zgarmaydi)

**Maqsad:** `002_date_columns` migratsiyasi bazadagi ma'lumotda to'xtab
qolmasligini oldindan bilish. Migratsiya xato topsa hech narsani o'zgartirmaydi,
lekin ilova ham ishga tushmaydi — shuning uchun buni **deploydan oldin** bilgan
ma'qul.

Supabase SQL Editor'da ketma-ket ishlating.

### A.1 — Ustun turlari (hozir `text` bo'lishi kerak)

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name IN ('debt_date', 'payment_date')
ORDER BY table_name;
```

### A.2 — Ma'lumot hajmi (migratsiyadan keyin solishtirish uchun yozib qo'ying)

```sql
SELECT
  (SELECT COUNT(*) FROM clients)  AS clients,
  (SELECT COUNT(*) FROM debts)    AS debts,
  (SELECT COUNT(*) FROM payments) AS payments,
  (SELECT COUNT(*) FROM trash)    AS trash;
```

### A.3 — Sana formati (uchalasi ham **0** bo'lishi shart)

```sql
SELECT 'debts'    AS jadval, COUNT(*) AS xato
FROM debts    WHERE debt_date    !~ '^[0-9]{2}[.][0-9]{2}[.][0-9]{4}$'
UNION ALL
SELECT 'payments', COUNT(*)
FROM payments WHERE payment_date !~ '^[0-9]{2}[.][0-9]{2}[.][0-9]{4}$'
UNION ALL
SELECT 'trash',    COUNT(*)
FROM trash    WHERE debt_date    !~ '^[0-9]{2}[.][0-9]{2}[.][0-9]{4}$';
```

Agar 0 bo'lmasa — muammoli yozuvlarni ko'ring va qo'lda tuzating:

```sql
SELECT id, client_id, debt_date FROM debts
WHERE debt_date !~ '^[0-9]{2}[.][0-9]{2}[.][0-9]{4}$' LIMIT 50;
```

### A.4 — Haqiqiy sana tekshiruvi (round-trip; **0** bo'lishi shart)

> Nega kerak: `TO_DATE('31.02.2026', 'DD.MM.YYYY')` xato bermaydi, sanani
> jimgina `03.03.2026` ga surib yuboradi. A.3 dagi shablon buni ushlamaydi.
> **A.3 natijasi 0 bo'lgandan keyin** ishlating.

```sql
SELECT 'debts' AS jadval, COUNT(*) AS xato
FROM debts    WHERE to_char(to_date(debt_date,    'DD.MM.YYYY'), 'DD.MM.YYYY') <> debt_date
UNION ALL
SELECT 'payments', COUNT(*)
FROM payments WHERE to_char(to_date(payment_date, 'DD.MM.YYYY'), 'DD.MM.YYYY') <> payment_date
UNION ALL
SELECT 'trash',    COUNT(*)
FROM trash    WHERE to_char(to_date(debt_date,    'DD.MM.YYYY'), 'DD.MM.YYYY') <> debt_date;
```

Bu so'rovning o'zi xato bersa (masalan `oy = 99`), demak bazada butunlay
yaroqsiz sana bor — uni ham A.3 kabi topib tuzatish kerak.

### A.5 — Dublikat telefonlar (`005_clients_phone_unique` uchun)

```sql
SELECT phone, COUNT(*) AS nechta, array_agg(id) AS client_ids
FROM clients WHERE phone <> ''
GROUP BY phone HAVING COUNT(*) > 1;
```

Bo'sh natija = index muammosiz qo'yiladi. Natija bo'lsa — ilova baribir
ishlaydi (bu migratsiya ixtiyoriy), faqat ERROR log yoziladi. Mijozlarni
birlashtirgandan keyin index o'zi qo'yiladi.

### A.6 — Yangi CHECK constraintlarni buzadigan qatorlar

```sql
SELECT COUNT(*) AS remaining_original_dan_katta FROM debts WHERE remaining_debt > original_debt;

SELECT COUNT(*) AS manfiy_summalar FROM debts
WHERE product_price < 0 OR exchange_product_price < 0 OR given_money < 0
   OR original_debt < 0 OR remaining_debt < 0 OR product_quantity < 0;

SELECT COUNT(*) AS manfiy_tolovlar FROM payments WHERE amount < 0;
```

Constraintlar `NOT VALID` qilib qo'yiladi — eski qatorlar o'chirilmaydi va
migratsiya to'xtamaydi. Ammo bunday qatorlar bo'lsa, kelajakdagi
yangilanishlarda muammo chiqishi mumkin, shuning uchun bilib qo'ygan yaxshi.

### A.7 — Ma'lumot uchun: bir xil ismli, turli telefonli mijozlar (M-02 ta'siri)

```sql
SELECT lower(full_name) AS ism, COUNT(DISTINCT phone) AS turli_telefon, array_agg(id)
FROM clients GROUP BY 1 HAVING COUNT(DISTINCT phone) > 1;
```

Yangi qoida: bunday mijozlar **birlashtirilmaydi ham, o'chirilmaydi ham** —
faqat bundan keyin bir xil ism + boshqa telefon kelsa, yangi mijoz yaratiladi.

### A.8 — Yetim to'lovlar

```sql
SELECT COUNT(*) FROM payments p
LEFT JOIN debts d ON d.id = p.debt_id
WHERE p.debt_id IS NOT NULL AND d.id IS NULL;
```

**A bosqichi natijasi:** A.3 va A.4 = 0 bo'lsa, migratsiya muammosiz o'tadi.

---

## B. Lokal PostgreSQL + integration testlar

**Maqsad:** `asyncpg` kod yo'llari (repository, Unit of Work, migratsiya SQL,
`FOR UPDATE`, pool) haqiqiy bazada bir marta ishlab ko'rsin. Hozir bu qism
faqat ko'z bilan tekshirilgan.

```bash
# 1. O'rnatish
brew install postgresql@17
brew services start postgresql@17
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"

# 2. Test bazasi (nomida "test" bo'lishi SHART — himoya to'sig'i bor)
createdb qarzly_test

# 3. Integration testlar
TEST_DATABASE_URL=postgresql://$(whoami)@localhost:5432/qarzly_test \
    .venv/bin/python -m pytest tests/integration -q

# 4. Barcha testlar
.venv/bin/python -m pytest -q
```

Nimani tekshiradi (8 ta test):

| Test | Qaysi topilma |
|---|---|
| `test_schema_uses_real_date_columns` | C-03 — ustunlar `DATE` |
| `test_fifo_order_comes_from_sql` | C-03 — SQL saralashi xronologik |
| `test_failed_use_case_rolls_back_everything` | C-02 — rollback |
| `test_debt_and_initial_payment_are_atomic` | C-02 — atomiklik |
| `test_concurrent_partial_payments_do_not_overdraw` | C-02 — `FOR UPDATE` |
| `test_concurrent_inserts_do_not_exhaust_pool` | C-04 — pool deadlock yo'q |
| `test_duplicate_phone_does_not_create_duplicate_client` | M-02 |
| `test_purge_trash_archives_payments` | M-08 — audit trail |

> ⚠️ Bu testlar jadvallarni `TRUNCATE` qiladi. `TEST_DATABASE_URL` nomida
> "test" bo'lmasa testlar ataylab ishlamaydi. **Hech qachon production DSN
> ko'rsatmang.**

Qo'shimcha: eski `TEXT` sanali bazada migratsiyani sinash uchun test bazasiga
eski sxemani qo'yib, `002_date_columns` ni ishlatib ko'rish mumkin — shunda
migratsiya real ma'lumotda bir marta tekshiriladi.

---

## C. Commit

```bash
git checkout -b audit/critical-fixes
git add -A
git commit   # xabar tayyorlanadi
```

`main` ga to'g'ridan-to'g'ri emas, alohida branch'ga. Hozir commit qilinmagan
o'zgarishlar: 36 fayl (~2 700 qator).

---

## D. Deploy

### D.1 — Backup (majburiy)

Supabase → Database → Backups → **snapshot oling**. `002_date_columns` ustun
turini o'zgartiradi; snapshot bo'lmasa orqaga qaytarish qiyinlashadi.

### D.2 — Render env o'zgaruvchilari

| O'zgaruvchi | Qiymat | Izoh |
|---|---|---|
| `ADMIN_IDS` | `123456789,...` | **Majburiy.** Bo'lmasa ilova ishga tushmaydi (ataylab) |
| `ALLOW_OPEN_ACCESS` | `false` | Productionda har doim false |
| `DATABASE_URL` | mavjud DSN | O'zgarmaydi |
| `APPLY_MIGRATIONS` | `true` | Startupda migratsiya (bitta instansiya uchun) |
| `LOG_JSON` | `true` (ixtiyoriy) | Structured loglar |

> `ADMIN_IDS` ni oldin qo'ying, keyin deploy qiling — aks holda birinchi
> startup xato bilan to'xtaydi.

### D.3 — Deploydan keyingi tekshiruv

```sql
-- Migratsiyalar qo'llanganmi (5 ta qator, 005 ixtiyoriy)
SELECT version, applied_at FROM schema_migrations ORDER BY version;

-- Ustunlar DATE ga o'tganmi
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND column_name IN ('debt_date','payment_date');

-- Yozuvlar soni A.2 dagi bilan bir xilmi (ma'lumot yo'qolmaganini tasdiqlaydi)
SELECT
  (SELECT COUNT(*) FROM clients)  AS clients,
  (SELECT COUNT(*) FROM debts)    AS debts,
  (SELECT COUNT(*) FROM payments) AS payments;
```

Ilova tomonidan:

- [ ] `/health` → `{"status":"ok"}`
- [ ] Botda `/start` → menyu ochiladi (admin ID bilan)
- [ ] Admin bo'lmagan akkaunt → "Ruxsat berilmagan" (fail-closed ishlayapti)
- [ ] Mini App: mijozlar ro'yxati, sanalar `DD.MM.YYYY` ko'rinishida
- [ ] Yangi qarz yaratish → saqlanadi
- [ ] Qisman to'lov → **eng eski** qarzdan yechiladi (FIFO)
- [ ] Mijoz hisoboti → sanalar va summalar to'g'ri
- [ ] Log'da `Migratsiya qo'llandi:` yoki `eng so'nggi holatda` yozuvi bor

---

## E. Rollback (agar kerak bo'lsa)

Eski kod sanani matn deb kutadi, shuning uchun kodni qaytarsangiz ustunlarni
ham qaytarish kerak. **Ma'lumot yo'qolmaydi** — format aynan tiklanadi:

```sql
ALTER TABLE debts    ALTER COLUMN debt_date    TYPE TEXT USING to_char(debt_date,    'DD.MM.YYYY');
ALTER TABLE payments ALTER COLUMN payment_date TYPE TEXT USING to_char(payment_date, 'DD.MM.YYYY');
ALTER TABLE trash    ALTER COLUMN debt_date    TYPE TEXT USING to_char(debt_date,    'DD.MM.YYYY');
DELETE FROM schema_migrations WHERE version = '002_date_columns';
```

Yangi jadval va ustunlar (`trash_payments`, `idempotency_keys`,
`trash.deleted_by`) eski kodga xalaqit bermaydi — ularni o'chirish shart emas.

---

## F. Qolgan audit ishlari (deploydan keyin)

| ID | Ish | Izoh |
|---|---|---|
| M-06 | Keyset (cursor) pagination va bitta JOIN/CTE summary query | Hozir: DB `LIMIT/OFFSET` + engil agregat bor. Ma'lumot ko'paygach kerak bo'ladi |
| M-07 | Redis FSM storage, webhook, queue | Bir nechta replica kerak bo'lgandagina. Infratuzilma qarori |
| M-12 | Sentry + Prometheus metrikalari | Hozir: JSON log va actor ID bor. Yangi dependency talab qiladi |
| Minor 3 | `debt_creation.py` (1081 qator), `routes.py`, `app.js` ni feature modullariga bo'lish | Sof refactor, xulq o'zgarmaydi |
| — | CI pipeline: `pytest` + PostgreSQL integration + `ruff` + `mypy` | B bosqichi ishlagach osson qo'shiladi |
| — | Backup/restore mashqi (drill) | Snapshotdan tiklashni bir marta sinab ko'rish |

---

## Eslatma: ma'lumot xavfsizligi

Migratsiyalarda birorta `DELETE`, `DROP` yoki `TRUNCATE` yo'q — faqat
`ALTER COLUMN ... TYPE` (joyida konvertatsiya), `ADD CONSTRAINT ... NOT VALID`,
`ADD COLUMN IF NOT EXISTS` va `CREATE INDEX`. Batafsil jadval:
[audit_tuzatishlar.md](audit_tuzatishlar.md) → "Ma'lumot xavfsizligi" bo'limi.

Biznes ma'lumotini o'chiradigan yagona amal — korzinani tozalash
(`POST /api/trash/purge`), u **ilgari ham bor edi** va endi xavfsizroq:
to'lovlar avval `trash_payments` arxiviga ko'chiriladi, to'lovi bor mijoz esa
o'chirilmaydi.
