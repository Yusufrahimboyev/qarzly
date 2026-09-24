# UI/UX audit va Design System — Telegram Mini App

Qamrov: `web/templates/index.html`, `web/static/css/style.css`, `web/static/js/app.js`.
Backend, API kontrakti va DOM ID'lari o'zgartirilmagan — barcha 154 test o'tadi.

## 1. Aniqlangan muammolar va yechimlar

### Kritik (funksional / noto'g'ri ma'lumot)

| # | Muammo | Yechim |
|---|--------|--------|
| 1 | **Light rejim buzilgan**: mijoz va korzina kartalari `rgba(15,23,42,.72)` bilan qattiq kodlangan — yorug' mavzuda qora karta ustida qora matn o'qilmaydi. Toast, selection bar, hover holatlari ham faqat dark uchun yozilgan. | Barcha ranglar semantik tokenlarga o'tkazildi; light va dark to'liq qo'llab-quvvatlanadi. |
| 2 | **To'liq to'lov preview'i noto'g'ri**: server `pay_full_debt` barcha valyutalarni yopadi, UI esa faqat so'mni ko'rsatib "qoldiq: 0 so'm + 150 $" deb yozardi. | "To'liq yopish" rejimida barcha valyutalar ko'rsatiladi, qoldiq 0. |
| 3 | **Faqat dollarda qarzi bor mijoz** uchun qisman to'lov so'mda boshlanib, server xatosiga olib kelardi. | Qarz bitta valyutada bo'lsa, to'lov valyutasi avtomatik tanlanadi; oldindan tekshiriladi. |
| 4 | JS ishlatadigan CSS klasslar umuman yo'q edi: `.text-danger`, `.text-success`, `.nav-keyboard-hidden`, `.rotating`, `.btn-remove-product`, `.product-group-header`. Natijada: hisobotda status ranglari chiqmasdi, klaviatura ochilganda nav yashirinmasdi, refresh animatsiyasi ishlamasdi, "tovarni o'chirish" tugmasi stilsiz edi. | Barchasi design system ichida aniqlandi. |
| 5 | Ro'yxatlar `limit`siz so'ralardi — server default 200 ta qaytaradi, 200 dan ortiq mijoz jimgina yo'qolardi (statistika esa to'liq sonni ko'rsatardi). | `?limit=1000` (server maksimumi). |
| 6 | `/api/summaries` xatosida (`!res.ok`) ro'yxat abadiy "Yuklanmoqda..." holatida qolardi. | Xato holati + "Qayta urinish" tugmasi; avval yuklangan ma'lumot saqlanib qoladi. |
| 7 | `onsubmit="return false;"` inline handler CSP (`script-src` da `unsafe-inline` yo'q) tomonidan bloklanadi. | JS orqali `submit` preventDefault. |

### UX

| Muammo | Yechim |
|--------|--------|
| Sticky header + statistika har bir tabda ekranning ~25% ini egallardi. | Kompakt 56px app bar; KPI faqat "Mijozlar" sahifasida, scroll bilan ketadi. |
| Navigatsiya tartibi: Jadval, Yopilgan, Korzina, Yaratish, To'lov — asosiy amallar oxirida. | Foydalanish chastotasi bo'yicha: Mijozlar → Yangi qarz → To'lov → Yopilgan → Korzina. |
| Mijoz kartasida karta va 📊 tugma bir xil ishni qilardi (ortiqcha target). | Butun qator bitta target + chevron indikator. |
| Validatsiya faqat toast orqali: qaysi maydon xatoligi ko'rinmasdi, uzun toast mobil ekrandan chiqib ketardi (`white-space: nowrap`). | Inline xatolar maydon ostida, fokus + scroll xato maydonga, yozish boshlanganda tozalanadi. Toast matni o'raladi, turlari bor (success/error/info). |
| Yarim to'ldirilgan tovar kartasi (nom bor, narx yo'q) jimgina tashlab yuborilardi. | Har bir karta tekshiriladi: aniq qaysi tovar va qaysi maydon. |
| Mavjud mijozga qarz qo'shishda ism/telefon maydonlari banner bilan takrorlanardi. | Mijoz tanlanganda maydonlar yashirinadi; "Almashtirish" tugmasi bilan qaytadi. |
| To'lov sanasi faqat qisman rejimda ko'rinardi, lekin to'liq to'lov ham shu sanani yuborardi. | Sana ikkala rejimda ko'rinadi. |
| Sana `DD.MM.YYYY` qo'lda nuqtalar bilan kiritilardi. | Raqamli klaviatura + avtomatik nuqta maskasi. |
| Bo'sh holatlar bitta umumiy matn edi. | "Mijoz yo'q" (CTA: Yangi qarz), "Qidiruvda topilmadi" (CTA: tozalash), filtr bo'yicha bo'sh — alohida. |
| Yuklanish: matnli "Yuklanmoqda..." va statistikada noto'g'ri "0 so'm". | Skeleton qatorlar, KPI placeholder. |
| Tanlash rejimi boshqa tabga o'tganda amal paneli qolib ketishi mumkin edi. | Tab o'zgarganda tanlash rejimi yopiladi. |
| Filtr chiplarida son yo'q edi. | "Barchasi 24 · Qarzdorlar 18 · Yopilgan 6". |
| Ko'p valyutali summa bitta uzun qatorda ("2 500 000 so'm + 150 $") qisqartirilib ketardi. | Har bir valyuta alohida qatorda, tabular raqamlar. |

### Accessibility

- Modal: `role="dialog"`, `aria-modal`, Escape bilan yopish, focus trap, fokus qaytarilishi, body scroll lock, Telegram **BackButton** modalni yopadi.
- Mijoz qatorlari klaviatura bilan ochiladi (`role="button"`, Enter/Space), `aria-label` summasi bilan.
- Global `:focus-visible` halqasi; switch, radio-card, segmented control fokuslari ko'rinadi.
- `aria-pressed` (chiplar), `aria-current` (nav), `aria-live` (toast, tanlangan soni), `aria-invalid` + `aria-describedby` (xatolar).
- Barcha matn tokenlari WCAG AA (≥ 4.5:1) ikkala mavzuda tekshirilgan.
- Zoom bloklash (`user-scalable=no`) olib tashlandi; iOS auto-zoom input 16px shrift orqali oldi olingan.
- `prefers-reduced-motion` qo'llab-quvvatlanadi.
- Emoji-ikonkalar (platformaga qarab turlicha ko'rinadi, ekran o'quvchida shovqin) yagona SVG ikonka to'plamiga almashtirildi.

### Responsive

- 320px da gorizontal overflow yo'q (tekshirilgan); ≤360px uchun alohida moslashuvlar.
- iPhone safe-area (`env(safe-area-inset-bottom)`) nav, amal paneli va modal footer'da hisobga olingan.
- ≥600px (Telegram Desktop / planshet): KPI ikki ustunli, modal markazlashgan dialog.
- Sensor ekranlarda "yopishib qolgan" hover holatlari o'chirilgan.
- Glassmorphism `backdrop-filter` (zaif Android qurilmalarda sekin) olib tashlandi.

## 2. Design System

Barcha qiymatlar `style.css` boshidagi `:root` tokenlarida. Mavzu `html[data-theme]` orqali
Telegram `colorScheme`dan olinadi (`themeChanged` hodisasi kuzatiladi), bo'lmasa `prefers-color-scheme`.

| Kategoriya | Tokenlar |
|------------|----------|
| Surface | `--color-bg`, `--color-surface`, `--color-surface-2`, `--color-surface-hover`, `--color-overlay` |
| Border | `--color-border`, `--color-border-strong` |
| Text | `--color-text`, `--color-text-secondary`, `--color-text-tertiary`, `--color-text-disabled` |
| Primary | `--color-primary` (solid fon), `--color-primary-fg` (matn/ikonka), `--color-primary-soft(-border)` |
| Semantic | `success`, `danger`, `warning` — har biri `-fg`, `-soft`, `-soft-border` (+ solid tugma uchun `--color-success`, `--color-danger`) |
| Tipografiya | Inter; 12 / 13 / 14 / 15 / 17 / 20 / 26 px; og'irliklar 400 / 500 / 600 / 700; pul uchun `tabular-nums` |
| Spacing | 4px grid: `--space-1…8` (4, 8, 12, 16, 20, 24, 32) |
| Radius | `--radius-sm` 8 · `md` 10 (input, tugma) · `lg` 14 (karta) · `xl` 20 (sheet) · `full` |
| Elevation | `--shadow-sm/md/lg` (dark mavzuda soya o'rniga border) |
| Control | balandlik 44px (touch target), kichik 36px |

Komponentlar: `.btn` (`-primary`, `-success`, `-danger`, `-secondary`, `-ghost`, `-dashed`, `-danger-outline`; `-sm`, `-lg`, `-block`),
`.card`, `.form-group` + `.field-error`, `.select-field`, `.segmented` / `.currency-chips`, `.switch`, `.radio-cards`,
`.badge` (`-danger`, `-success`, `-neutral`), `.count-badge`, `.avatar`, `.list` / `.list-row`, `.summary-card`,
`.empty-state` (`.is-error`), `.skeleton-row`, `.toast` (`-success`, `-error`, `-info`), `.modal-*` (bottom sheet),
`.danger-zone`, `.bottom-nav`, `.floating-action-bar`.

JS yordamchilari: `icon()`, `stateBlockHTML()`, `skeletonRowsHTML()`, `setButtonLoading()`,
`setFieldError()` / `clearFieldError()`, `showToast(message, type)`, `formatMoneyLinesHTML()`,
`apiJson()` / `ApiError` / `notifyError()`, `normalizeText()` / `matchesClientQuery()`,
`createSelectableList()`, `attachListGestures()`.

## 3. Ikkinchi bosqich (QA + polish)

Qizil jamoa usulida edge-case'lar (juda uzun matn, katta summalar, API xatolari, sekin tarmoq,
offline, sessiya tugashi, 1000 ta yozuv) sinab ko'rildi. Topilgan va tuzatilgan muammolar:

| Sev | Muammo | Yechim |
|-----|--------|--------|
| HIGH | Mavjud mijoz ismini telefonsiz yozish serverda **dublikat mijoz** yaratardi (server telefon yoki telefonsiz ism bo'yicha moslaydi). | Ism maydoniga mijoz takliflari (combobox, klaviatura bilan) + aynan shu ism mavjud bo'lsa ogohlantirish va "Tanlash". |
| HIGH | 320px da katta summa ism/telefon ustiga chiqib ketardi; modal KPI'da "so'm" kesilardi. | Qator flex modeli qayta qurildi (nom `basis: 0`, summa kontent bo'yicha, max 58%), raqam hech qachon o'rtasidan bo'linmaydi, tor ekranda avatar yashiriladi. |
| HIGH | 502 HTML javobi foydalanuvchiga `Unexpected token '<'…` bo'lib chiqardi; `fetch` timeout'siz — sekin tarmoqda skeleton abadiy aylanardi. | `apiJson()`: 20s timeout, xavfsiz JSON, status bo'yicha tushunarli xabarlar. |
| MEDIUM | Statistika yuklanmasa KPI skeleton abadiy; offline holat ko'rsatilmasdi; "Yangilash" xato bo'lsa ham "yangilandi" derdi. | Xato holati "—", offline banner + aloqa tiklanganda avtomatik yangilash, natijaga mos toast. |
| MEDIUM | To'lovda yuzlab qarzdorlar uchun qidiruvsiz select. | 8+ qarzdorda filtr maydoni (tanlangan mijoz filtrdan qat'i nazar saqlanadi). |
| MEDIUM | Sessiya muddati tugaganda (24 soat) noto'g'ri matn va chiqish yo'li yo'q. | "Sessiya tugadi" ekrani + "Ilovani yopish" (`tg.close`). |
| MEDIUM | Yopilgan/Korzina ~250 qator takroriy kod, har qatorda 4–5 listener, 1000 yozuv birdan chiziladi. | Yagona `createSelectableList()` komponenti, event delegation, 40 talik bo'laklab chizish. |
| MEDIUM | Saqlashdan keyin ma'lumot ikki marta so'ralardi (4 so'rov, navigatsiya kechikardi). | Bitta yangilash; darhol jadvalga o'tish. |
| MEDIUM | `telegram-web-app.js` `<head>`da sinxron — birinchi chizishni bloklardi. | `defer` (ikkala skript, tartib saqlanadi). |
| LOW | "Yopilgan" ham qarzsiz mijoz, ham yopilgan qarz yozuvi ma'nosida. | Mijoz darajasida — "Qarzsiz", qarz darajasida — "Yopilgan". |
| LOW | Qidiruv `o‘`/`o'`/`oʻ` va `90 123` kabi formatlarni topmasdi. | Apostrof va telefon raqamlari normalizatsiyasi. |
| LOW | Korzina/Yopilgan qatorlari klaviatura bilan tanlanmasdi; kichik touch target'lar (28–30px). | `listbox`/`option` + `aria-selected`, Enter/Space; min 32px. |

Performance (1000 mijoz + 1000 yopilgan yozuv, CPU 4× sekinlashtirilgan):

| Ko'rsatkich | Oldin | Keyin |
|---|---|---|
| DOM tugunlari | 50 599 | 9 539 |
| JS event listener'lar | 6 068 / 12 081 | 91 / 104 |
| JS heap | 4.4 MB | 1.6 MB |
| Yopilgan tabini ochish | 304 ms | 125 ms |
| "Barchasini tanlash" | 725 ms | 55 ms |

Qolgan tavsiyalar (biznes qarori talab qilinadi, shuning uchun o'zgartirilmadi):
- `enableClosingConfirmation()` har doim yoqilgan — faqat saqlanmagan forma bo'lganda yoqish qulayroq.
- Yopilgan tabida qatorni bosish darhol tanlash rejimini yoqadi; bosish — mijoz hisobotini ochish,
  uzoq bosish — tanlash (platforma konvensiyasi) ko'rib chiqilishi mumkin.
- Bot `/help` matni mavjud bo'lmagan "ℹ️ Yordam" tugmasini tilga oladi va Mini App'ni eslatmaydi.
