# Qarzly — Code & Architecture Audit Rejasi

> **Holat: bajarildi (2026-08-31).** Yakuniy natija:
> [audit_hisoboti.md](audit_hisoboti.md). Verifikatsiya: 50 test o'tdi, mypy
> xatosiz, ruff 3 ta style xatosini topdi.

## Maqsad

Telegram bot va unga tegishli backend kodini senior-backend darajasida mustaqil
texnik auditdan o'tkazish. Auditning maqsadi — xavfsizlik, ishonchlilik,
unumdorlik va kengayuvchanlikka ta'sir qiladigan muammolarni dalil bilan topish,
ularni ustuvorlashtirish va amaliy tuzatish yo'lini ko'rsatish.

Audit mavjud kodni o'zgartirmaydi. Faqat kerak bo'lganda alohida, minimal
"oldin/keyin" namunalar taklif qilinadi.

## Dastlabki texnik kontekst

Kod bazasi hujjatlariga ko'ra loyiha quyidagi asosiy qismlardan iborat:

- Python 3.11+, Aiogram 3.x va `asyncio`;
- aiohttp asosidagi Mini App va REST API;
- PostgreSQL uchun `asyncpg` (kod va migratsiyalar bilan tasdiqlanadi);
- APScheduler;
- qatlamli arxitektura: `core`, `domain`, `application`, `infrastructure`,
  `presentation` va `app.py` composition root;
- testlar: pytest / pytest-asyncio.

README hamda dependency fayllari o'rtasida nomuvofiqliklar bo'lishi mumkin;
ular alohida tekshirilib, audit natijasida qayd etiladi.

## Audit qamrovi

| Yo'nalish | Tekshiriladigan qismlar | Asosiy savollar |
|---|---|---|
| Arxitektura | `bot/app.py`, barcha qatlamlar, konfiguratsiya, dependency wiring | Qatlamlar mustaqilmi, qaramliklar to'g'ri yo'nalganmi, use-case'lar va repository'lar ajratilganmi? |
| Bot va asyncio | handler, middleware, filter, FSM, scheduler, Telegram mijoz chaqiruvlari | Event loop bloklanmayaptimi, cancellation va timeoutlar boshqarilganmi, handlerlar xavfsiz hamda idempotentmi? |
| Web/API | aiohttp route, Mini App autentifikatsiyasi, request/response sxemalari | Endpointlar autentifikatsiyalanganmi, input tekshiriladimi, CORS va xato javoblari xavfsizmi? |
| Xavfsizlik | `core/config.py`, `.env.example`, tokenlar, auth/authz, loglar | Secretlar sizib chiqmayaptimi, ruxsatlar default holatda xavfsizmi, Telegram `initData` to'liq tekshiriladimi? |
| Ma'lumotlar bazasi | connection/pool, schema, SQL, repository, transaction, indekslar | SQL injection, N+1, race condition, noto'g'ri transaction yoki sekin so'rovlar bormi? |
| Ishonchlilik | exception handling, retry, startup/shutdown, backup, deploy | Bir xato botni to'xtatadimi, restartdan so'ng ma'lumot saqlanadimi, resurslar toza yopiladimi? |
| Observability va sifat | logging, audit log, metrikalar, testlar, lint/type check | Muhim voqealarni kuzatish mumkinmi, PII oshkor bo'lmayaptimi, regressiyani ushlaydigan testlar yetarlimi? |

## Bajarish bosqichlari

1. **Inventarizatsiya va ishga tushirish yo'lini xaritalash**
   - loyiha daraxti, package/dependency fayllari, `README`, deploy va environment
     konfiguratsiyasini solishtirish;
   - entrypointdan (`python -m bot`) handler, web server, scheduler va DBgacha
     bo'lgan oqimni aniqlash;
   - mavjud test, lint va type-check buyruqlarini aniqlash.

2. **Arxitektura va dependency audit**
   - domain qatlamining framework/DBdan mustaqilligini tekshirish;
   - service, repository va presentation chegaralarini ko'rib chiqish;
   - DI lifetime'lari (app/request/update), global mutable state va circular
     import xavflarini baholash.

3. **Asyncio, Aiogram va Telegram oqimi auditı**
   - synchronous I/O (`requests`, fayl/DB I/O, `time.sleep`, CPU-heavy ishlar)
     event loopda ishlatilmaganini qidirish;
   - handler/middleware xatolari, FSM storage va cleanup, task yaratish hamda
     cancellation strategiyasini tekshirish;
   - polling/webhook tanlovi, Telegram flood-limit, retry/backoff va
     backpressure muomalasini baholash.

4. **Xavfsizlik auditi**
   - konfiguratsiya, secretlar va loglarda token/PII chiqishini tekshirish;
   - admin authorization va barcha API route'laridagi access controlni tekshirish;
   - Telegram WebApp `initData`: HMAC, `auth_date`, replay protection va user ID
     tekshiruvi;
   - input validation, chegaralar, xabar formatlash, SQL parametrizatsiyasi,
     error disclosure hamda HTTP security sozlamalarini tekshirish.

5. **DB, transaction va cache audit**
   - pool/connection lifecycle, query parametrizatsiyasi va transaction
     chegaralarini tekshirish;
   - debt/payment kabi bir nechta yozuvni yangilaydigan operatsiyalarda
     atomiklik, lock va concurrent update xavfini tekshirish;
   - query count, N+1, pagination, sorting/filtering indekslari va agregat
     so'rovlarni tahlil qilish;
   - Redis/Memcached mavjud bo'lsa, TTL, invalidation va session/cache
     xavfsizligini tekshirish; mavjud bo'lmasa, zaruratini asoslash.

6. **Verifikatsiya**
   - mavjud testlarni ishga tushirish va natijalarni qayd etish;
   - mumkin bo'lsa `ruff check` va `mypy`ni ishga tushirish;
   - audit topilmalari asosida minimal reproduksiya yoki test ssenariylarini
     ko'rsatish. Hech qaysi tekshiruv production ma'lumotlari yoki secretlarga
     muhtoj bo'lmasligi kerak.

7. **Hisobot va ustuvorlashtirish**
   - har bir topilmani fayl/qatordagi dalil, ta'sir, exploit/failure ssenariysi
     va aniq yechim bilan yozish;
   - muammolarni Critical, Major/Moderate va Minor/Style guruhlariga ajratish;
   - 30/60/90 kunlik yoki bosqichma-bosqich action plan tuzish.

## Severity mezonlari

| Daraja | Mezon | Misollar |
|---|---|---|
| 🔴 Critical | Ma'lumot sizishi yoki yo'qolishi, authorization bypass, SQL injection, bot/service to'xtashi, hisob-kitobning buzilishi ehtimoli yuqori. | Ochiq API, tekshirilmagan `initData`, transaction yo'qligi sabab ikki karra to'lov. |
| 🟡 Major / Moderate | Yuklama oshganda degradatsiya, xato natija, operatsion risk yoki arxitektura qarzi yuzaga keltiradi. | Bloklovchi I/O, N+1, pool lifecycle xatosi, retry/rate-limit yo'qligi. |
| 🟢 Minor / Style | O'qiluvchanlik, saqlab turish qulayligi yoki kelajakdagi regressiya xavfiga ta'sir qiladi, ammo bevosita incident xavfi past. | Typing, nomlash, takror kod, log formati, PEP 8. |

## Hisobot formati

Yakuniy hisobot quyidagi bo'limlardan iborat bo'ladi:

1. **Executive Summary** — umumiy holat, 1–10 baho, eng katta 3–5 risk.
2. **Topilmalar** — severity bo'yicha tartiblangan jadval: ID, joylashuv,
   muammo, ta'sir, dalil va tavsiya.
3. **Oldin / Keyin** — eng muhim muammolar uchun xavfsiz va asinxron
   optimallashtirilgan kod namunalari.
4. **Action Plan** — avval 0–7 kun ichidagi critical tuzatishlar, keyin
   1–4 haftalik barqarorlashtirish va uzoq muddatli yaxshilashlar.
5. **Tekshiruv cheklovlari** — audit vaqtida mavjud bo'lmagan infratuzilma,
   konfiguratsiya yoki yuklama sinovi kabi cheklovlar ochiq ko'rsatiladi.

## Qabul mezoni

Audit yakunlangan deb hisoblanadi, agar barcha public entrypointlar, bot
handlerlari, web API route'lari, auth qatlamlari, DB repository/so'rovlari va
startup/shutdown jarayonlari ko'rib chiqilgan bo'lsa; mavjud avtomatlashtirilgan
tekshiruvlar bajarilgan bo'lsa; va har bir muhim riskga bajariladigan amaliy
tavsiya berilgan bo'lsa.
