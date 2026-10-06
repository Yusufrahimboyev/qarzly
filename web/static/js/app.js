/**
 * QARZ DAFTAR — TELEGRAM MINI APP JAVASCRIPT
 */

// Initialize Telegram WebApp
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    try {
        tg.enableClosingConfirmation();
    } catch (e) {}
}

// Mavzu: Sozlamalarda tanlangan (light/dark) yoki "Avtomatik" — Telegram
// sozlamasiga moslanadi. Tanlov shu qurilmada eslab qolinadi.
const THEME_STORAGE_KEY = 'qarz-theme';

function getThemePreference() {
    try {
        const saved = localStorage.getItem(THEME_STORAGE_KEY);
        return saved === 'light' || saved === 'dark' ? saved : 'auto';
    } catch (e) {
        return 'auto';
    }
}

function applyTheme() {
    const pref = getThemePreference();
    const scheme = pref === 'auto' ? tg?.colorScheme : pref;
    if (scheme === 'dark' || scheme === 'light') {
        document.documentElement.setAttribute('data-theme', scheme);
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
    const bg = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim();
    try {
        if (bg) {
            tg?.setHeaderColor?.(bg);
            tg?.setBackgroundColor?.(bg);
        }
    } catch (e) {}
}
applyTheme();
try {
    tg?.onEvent?.('themeChanged', applyTheme);
} catch (e) {}

function hapticSuccess() {
    try {
        tg?.HapticFeedback?.notificationOccurred('success');
    } catch (e) {}
}

function hapticError() {
    try {
        tg?.HapticFeedback?.notificationOccurred('error');
    } catch (e) {}
}

function hapticImpact() {
    try {
        tg?.HapticFeedback?.impactOccurred('light');
    } catch (e) {}
}

// Global App State
const state = {
    summaries: [],
    filter: 'all',
    sort: 'name_asc',
    searchQuery: '',
    selectedClientReport: null,
    renderedCount: 0,
    filteredList: [],
    summariesLoaded: false,
    gateShown: false,
};

// Utilities
function formatMoney(amount, currency = 'UZS') {
    const num = Math.round(Number(amount) || 0);
    const formatted = num.toLocaleString('ru-RU').replace(/,/g, ' ');
    return currency === 'USD' ? `${formatted} $` : `${formatted} ${t("so'm")}`;
}

// Bir nechta valyutadagi summalarni bitta qatorga yig'adi:
// {UZS: 1500000, USD: 200} -> "1 500 000 so'm + 200 $"
function formatMoneyMap(map) {
    if (!map || typeof map !== 'object') return formatMoney(0);
    const parts = [];
    if ((map.UZS || 0) > 0) parts.push(formatMoney(map.UZS, 'UZS'));
    if ((map.USD || 0) > 0) parts.push(formatMoney(map.USD, 'USD'));
    return parts.length > 0 ? parts.join(' + ') : formatMoney(0);
}

// Har bir valyutani alohida qatorda ko'rsatadi (uzun "+ ..." qatorlar o'rniga)
function formatMoneyLinesHTML(map) {
    const parts = [];
    if (map && (map.UZS || 0) > 0) parts.push(formatMoney(map.UZS, 'UZS'));
    if (map && (map.USD || 0) > 0) parts.push(formatMoney(map.USD, 'USD'));
    if (parts.length === 0) parts.push(formatMoney(0));
    return parts.map(p => `<span class="money-line">${escapeHtml(p)}</span>`).join('');
}

function icon(name, extraClass = '') {
    return `<svg width="20" height="20" class="icon ${extraClass}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

function getInitials(name) {
    const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return '?';
    const first = parts[0][0] || '';
    const second = parts.length > 1 ? (parts[1][0] || '') : '';
    return (first + second).toUpperCase();
}

// Bo'sh / xato holatlari uchun yagona komponent
function stateBlockHTML({ iconName = 'inbox', title, desc = '', action = null, isError = false }) {
    const actionHtml = action
        ? `<button type="button" class="btn btn-secondary btn-sm" data-state-action="${action.id}">${escapeHtml(action.label)}</button>`
        : '';
    return `
        <div class="empty-state ${isError ? 'is-error' : ''}">
            <div class="empty-state-icon">${icon(iconName)}</div>
            <div class="empty-state-title">${escapeHtml(title)}</div>
            ${desc ? `<div class="empty-state-desc">${escapeHtml(desc)}</div>` : ''}
            ${actionHtml}
        </div>
    `;
}

function skeletonRowsHTML(count = 3) {
    return '<div class="skeleton-row"></div>'.repeat(count);
}

// Tugmaning yuklanish holati: spinner + matn, keyin asl ko'rinishi qaytariladi
function setButtonLoading(btn, isLoading, loadingText = '') {
    if (!btn) return;
    if (isLoading) {
        if (!btn.dataset.originalHtml) btn.dataset.originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.setAttribute('aria-busy', 'true');
        btn.innerHTML = `<span class="btn-spinner" aria-hidden="true"></span>${escapeHtml(loadingText)}`;
    } else {
        if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
        delete btn.dataset.originalHtml;
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
    }
}

// Inline validatsiya: xato maydon ostida ko'rsatiladi va maydonga fokus beriladi
function setFieldError(input, message) {
    if (!input) {
        showToast(message, 'error');
        return;
    }
    clearFieldError(input);
    input.classList.add('is-invalid');
    input.setAttribute('aria-invalid', 'true');
    const err = document.createElement('div');
    err.className = 'field-error';
    err.id = `err-${Math.random().toString(36).slice(2, 9)}`;
    err.innerHTML = `${icon('alert-circle')}<span>${escapeHtml(message)}</span>`;
    const anchor = input.closest('.input-with-action, .select-field') || input;
    anchor.insertAdjacentElement('afterend', err);
    input.setAttribute('aria-describedby', err.id);
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    try {
        input.focus({ preventScroll: true });
    } catch (e) {}
    hapticError();
}

function clearFieldError(input) {
    if (!input) return;
    input.classList.remove('is-invalid');
    input.removeAttribute('aria-invalid');
    const errId = input.getAttribute('aria-describedby');
    if (errId) {
        document.getElementById(errId)?.remove();
        input.removeAttribute('aria-describedby');
    }
}

function clearFormErrors(form) {
    if (!form) return;
    form.querySelectorAll('.is-invalid').forEach(clearFieldError);
    form.querySelectorAll('.field-error').forEach(el => el.remove());
}

// Sana maydoni: raqam kiritilganda nuqtalar avtomatik qo'yiladi (DD.MM.YYYY)
function attachDateMask(input) {
    if (!input) return;
    input.addEventListener('input', (e) => {
        if (e.inputType && e.inputType.startsWith('delete')) return;
        const digits = input.value.replace(/\D/g, '').slice(0, 8);
        let out = digits.slice(0, 2);
        if (digits.length > 2) out += '.' + digits.slice(2, 4);
        if (digits.length > 4) out += '.' + digits.slice(4, 8);
        if (digits.length === 2 || digits.length === 4) out += '.';
        input.value = out;
    });
}

// Ikki valyuta xaritasini qo'shadi (UZS+UZS, USD+USD — valyutalar aralashmaydi)
function sumMaps(a, b) {
    const result = {};
    for (const cur of ['UZS', 'USD']) {
        result[cur] = ((a && a[cur]) || 0) + ((b && b[cur]) || 0);
    }
    return result;
}

// Sana matnini tekshiradi: DD.MM.YYYY va haqiqiy sana bo'lishi shart
function isValidDateString(str) {
    if (!/^\d{2}\.\d{2}\.\d{4}$/.test(str)) return false;
    const [d, m, y] = str.split('.').map(Number);
    if (m < 1 || m > 12) return false;
    const dt = new Date(y, m - 1, d);
    return dt.getDate() === d && dt.getMonth() === m - 1 && dt.getFullYear() === y;
}

function parseDateToTime(str) {
    if (!str || typeof str !== 'string') return 0;
    if (/^\d{2}\.\d{2}\.\d{4}$/.test(str)) {
        const [d, m, y] = str.split('.').map(Number);
        return new Date(y, m - 1, d).getTime();
    }
    const t = Date.parse(str);
    return isNaN(t) ? 0 : t;
}

function getTotalDebtUZS(item) {
    const rem = item.remaining || {};
    return (rem.UZS || 0) + ((rem.USD || 0) * 12800);
}

function debounce(fn, delay = 150) {
    let timer = null;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

function getTodayFormatted() {
    const now = new Date();
    const d = String(now.getDate()).padStart(2, '0');
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const y = now.getFullYear();
    return `${d}.${m}.${y}`;
}

let toastTimer = null;

// type: 'success' | 'error' | 'info'
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    const iconName = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'alert-circle';
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.innerHTML = `${icon(iconName)}<span>${escapeHtml(message)}</span>`;
    // Reflow — ketma-ket toastlarda animatsiya qayta ishlaydi
    void toast.offsetWidth;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), type === 'error' ? 4500 : 3000);
}

function showUnauthorizedState(message = t("Ushbu tizimga faqat ruxsat berilgan Telegram foydalanuvchilari kira oladi."), { title = 'Kirish cheklangan', canClose = true } = {}) {
    if (state.gateShown) return;
    state.gateShown = true;
    closeClientReportModal();
    // Eski toast (masalan, "yangilandi") kirish ekrani ustida qolib ketmasin
    clearTimeout(toastTimer);
    document.getElementById('toast')?.classList.remove('show');
    const app = document.getElementById('app') || document.body;
    const closeBtn = canClose && typeof tg?.close === 'function'
        ? `<button type="button" class="btn btn-primary btn-block" id="gate-close-btn">${t('Ilovani yopish')}</button>`
        : '';
    app.innerHTML = `
        <div class="gate">
            <div class="card gate-card" role="alert">
                <div class="gate-icon">${icon('lock')}</div>
                <h2 class="gate-title">${escapeHtml(title)}</h2>
                <p class="gate-text">${escapeHtml(message)}</p>
                ${closeBtn}
                <div class="gate-hint">${t('Ilovani bot menyusidagi «Mini App» tugmasi orqali qayta oching.')}</div>
            </div>
        </div>
    `;
    document.getElementById('gate-close-btn')?.addEventListener('click', () => {
        try {
            tg.close();
        } catch (e) {}
    });
}

// Har bir yozuv so'rovi uchun bir martalik kalit: tarmoq retry'i yoki
// tugmani ikki marta bosish dublikat qarz/to'lov yaratmasligi kerak.
function newIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
}

// Foydalanuvchiga ko'rsatiladigan xato: texnik tafsilotlar (JSON parse, TypeError) chiqmaydi
class ApiError extends Error {
    constructor(message, status = 0, { handled = false } = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        // true — xato allaqachon UI'da ko'rsatilgan (masalan, kirish cheklangan ekrani)
        this.handled = handled;
    }
}

const API_TIMEOUT_MS = 20000;

function statusErrorMessage(status) {
    if (status === 429) return t("So'rovlar juda tez yuborildi. Biroz kutib, qayta urinib ko'ring.");
    if (status === 502 || status === 503 || status === 504) return t("Server vaqtincha ishlamayapti (yangilanmoqda). 10–20 soniyadan so'ng qayta urinib ko'ring.");
    if (status >= 500) return t("Serverda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.");
    if (status === 404) return t("Ma'lumot topilmadi. Ro'yxatni yangilab, qayta urinib ko'ring.");
    return t("So'rovni bajarib bo'lmadi (kod {status}).", { status });
}

// Filial: har filialning ma'lumotlar bazasi alohida. Tanlov serverga `X-Branch`
// header'i bilan boradi; oxirgi tanlov faqat qulaylik uchun eslab qolinadi.
const BRANCH_STORAGE_KEY = 'qarz-branch';
let currentBranch = 'mangit';
try {
    currentBranch = localStorage.getItem(BRANCH_STORAGE_KEY) || currentBranch;
} catch (e) {}

function setCurrentBranch(code) {
    currentBranch = code;
    try {
        localStorage.setItem(BRANCH_STORAGE_KEY, code);
    } catch (e) {}
}

// Barcha API so'rovlarini Telegram initData imzosi bilan yuboradi.
// Server imzoni tekshiradi — begona shaxs URLni bilsa ham ma'lumot ololmaydi.
async function apiFetch(url, options = {}) {
    const requestBranch = currentBranch;
    const headers = { ...(options.headers || {}), 'X-Branch': requestBranch };
    if (tg && tg.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), options.timeout || API_TIMEOUT_MS);
    let res;
    try {
        res = await fetch(url, { ...options, headers, signal: controller.signal });
    } catch (err) {
        if (err && err.name === 'AbortError') {
            throw new ApiError(t("Server javob bermayapti. Internet tezligini tekshirib, qayta urinib ko'ring."));
        }
        throw new ApiError(navigator.onLine === false
            ? t("Internet aloqasi yo'q. Ulanishni tekshirib, qayta urinib ko'ring.")
            : t("Serverga ulanib bo'lmadi. Internet aloqasini tekshirib, qayta urinib ko'ring."));
    } finally {
        clearTimeout(timer);
    }
    // Filial almashgan bo'lsa, eski filialning kech kelgan o'qish javobi yangi
    // ma'lumotni bosib ketmasin (yoki xato ko'rsatmasin) — javob tashlanadi.
    // Yozuv (POST) javobi tashlanmaydi: u baribir bajarilgan.
    if (requestBranch !== currentBranch && (options.method || 'GET') === 'GET') {
        return new Promise(() => {});
    }
    if (res.status === 401) {
        // initData 24 soatdan keyin eskiradi — Mini App uzoq ochiq qolganda ham shu holat
        showUnauthorizedState(
            t("Sessiya muddati tugagan yoki ilova Telegram tashqarisida ochilgan. Xavfsizlik uchun ilovani qayta oching."),
            { title: t('Sessiya tugadi') },
        );
    } else if (res.status === 403) {
        showUnauthorizedState("Sizning Telegram akkauntingizga ushbu tizimdan foydalanish huquqi berilmagan.");
    }
    return res;
}

// JSON bo'lmagan javob (masalan, proxy'ning HTML xato sahifasi) ham xavfsiz o'qiladi
async function readJson(res) {
    try {
        return await res.json();
    } catch (e) {
        return null;
    }
}

// apiFetch + JSON + xatolarni yagona ko'rinishga keltirish
async function apiJson(url, options = {}) {
    const res = await apiFetch(url, options);
    const data = await readJson(res);
    if (!res.ok || (data && data.error)) {
        const handled = res.status === 401 || res.status === 403;
        const message = (data && typeof data.error === 'string' && data.error) || statusErrorMessage(res.status);
        throw new ApiError(message, res.status, { handled });
    }
    if (data === null) throw new ApiError(t("Serverdan noto'g'ri javob keldi. Qayta urinib ko'ring."), res.status);
    return data;
}

function notifyError(err) {
    if (err && err.handled) return;
    hapticError();
    showToast(err instanceof ApiError ? err.message : t("Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring."), 'error');
}

// ==========================================
// API REQUESTS
// ==========================================

function formatCount(n) {
    return t('{count} ta', { count: (Number(n) || 0).toLocaleString('ru-RU') });
}

async function fetchStats() {
    const totalEl = document.getElementById('stat-total-debt');
    try {
        const data = await apiJson('/api/stats');
        totalEl.classList.remove('is-loading');
        totalEl.innerHTML = formatMoneyLinesHTML(data.total_debt);
        document.getElementById('stat-debtors-count').textContent = formatCount(data.debtors_count);
        document.getElementById('stat-clients-count').textContent = formatCount(data.clients_count);
        return true;
    } catch (err) {
        console.error('Error fetching stats:', err);
        // Skeleton cheksiz "yuklanmoqda" bo'lib qolmasin
        if (totalEl && totalEl.classList.contains('is-loading')) {
            totalEl.classList.remove('is-loading');
            totalEl.textContent = '—';
        }
        return false;
    }
}

// Server ro'yxatlarni sahifalab beradi (default 200) — UI barcha yozuvlarni oladi
const LIST_LIMIT = 1000;

async function fetchSummaries() {
    const container = document.getElementById('clients-list');
    try {
        state.summaries = await apiJson(`/api/summaries?limit=${LIST_LIMIT}`);
        state.summariesLoaded = true;
        updateFilterCounts();
        renderClientsList();
        populatePaymentClients();
        return true;
    } catch (err) {
        console.error('Error fetching summaries:', err);
        if (err.handled) return false;
        // Avval yuklangan ro'yxat bo'lsa, uni saqlab qolamiz — faqat xabar beramiz
        if (state.summariesLoaded) {
            showToast(err.message, 'error');
            return false;
        }
        if (container) {
            container.removeAttribute('aria-busy');
            container.innerHTML = stateBlockHTML({
                iconName: 'alert-triangle',
                title: t("Mijozlar ro'yxatini yuklab bo'lmadi"),
                desc: err.message,
                action: { id: 'retry-summaries', label: t('Qayta urinish') },
                isError: true,
            });
        }
        return false;
    }
}

function updateFilterCounts() {
    const debtors = state.summaries.filter(s => s.has_debt).length;
    const counts = {
        all: state.summaries.length,
        debtors,
        paid: state.summaries.length - debtors,
    };
    document.querySelectorAll('.chip-count').forEach(el => {
        const key = el.getAttribute('data-count');
        el.textContent = counts[key] !== undefined ? String(counts[key]) : '';
    });
}

async function fetchClientReport(clientId) {
    try {
        return await apiJson(`/api/clients/${clientId}/report`);
    } catch (err) {
        console.error('Error fetching client report:', err);
        return null;
    }
}

// ==========================================
// TAB 1: RENDER CLIENTS LIST, FILTER & SORT (OPTIMIZED CHUNKED BATCHES)
// ==========================================

const BATCH_SIZE = 30;
let listObserver = null;

// O'zbekcha apostrof variantlari (o' o‘ oʻ o`) va ortiqcha bo'shliqlar bir xil ko'rinishga keltiriladi
function normalizeText(str) {
    return String(str || '')
        .toLowerCase()
        .replace(/[‘’ʻʼ`´]/g, "'")
        .replace(/\s+/g, ' ')
        .trim();
}

function digitsOnly(str) {
    return String(str || '').replace(/\D/g, '');
}

function matchesClientQuery(item, query) {
    const q = normalizeText(query);
    if (!q) return true;
    if (normalizeText(item.full_name).includes(q)) return true;
    const qDigits = digitsOnly(query);
    // "90 123 45" yoki "+998 90..." ko'rinishidagi qidiruv ham telefonga mos keladi
    if (qDigits.length >= 3 && digitsOnly(item.phone).includes(qDigits)) return true;
    return normalizeText(item.phone).includes(q);
}

function getProcessedList() {
    let list = [...state.summaries];

    // 1. Filter Chips
    if (state.filter === 'debtors') {
        list = list.filter(item => item.has_debt);
    } else if (state.filter === 'paid') {
        list = list.filter(item => !item.has_debt);
    }

    // 2. Search Query (apostrof variantlari va telefon formatiga sezgir emas)
    if (state.searchQuery.trim()) {
        list = list.filter(item => matchesClientQuery(item, state.searchQuery));
    }

    // 3. Sorting
    switch (state.sort) {
        case 'name_desc':
            list.sort((a, b) => (b.full_name || '').localeCompare(a.full_name || '', 'uz', { sensitivity: 'base' }));
            break;
        case 'date_desc':
            list.sort((a, b) => {
                const tA = parseDateToTime(a.latest_debt_date || a.created_at);
                const tB = parseDateToTime(b.latest_debt_date || b.created_at);
                return tB - tA;
            });
            break;
        case 'date_asc':
            list.sort((a, b) => {
                const tA = parseDateToTime(a.latest_debt_date || a.created_at);
                const tB = parseDateToTime(b.latest_debt_date || b.created_at);
                return tA - tB;
            });
            break;
        case 'debt_desc':
            list.sort((a, b) => getTotalDebtUZS(b) - getTotalDebtUZS(a));
            break;
        case 'debt_asc':
            list.sort((a, b) => getTotalDebtUZS(a) - getTotalDebtUZS(b));
            break;
        case 'name_asc':
        default:
            list.sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'uz', { sensitivity: 'base' }));
            break;
    }

    return list;
}

function renderClientCardHTML(item) {
    const phoneHtml = item.phone
        ? `<span class="row-meta-item">${icon('phone')}<span class="truncate">${escapeHtml(item.phone)}</span></span>`
        : `<span class="row-meta-item">${t('Telefon kiritilmagan')}</span>`;
    const dateHtml = item.latest_debt_date
        ? `<span class="row-meta-item">${icon('calendar')}<span class="truncate">${escapeHtml(item.latest_debt_date)}</span></span>`
        : '';
    const amountHtml = item.has_debt
        ? `<div class="row-amount client-debt-amount is-debt">${formatMoneyLinesHTML(item.remaining)}</div>`
        : '';
    const badgeHtml = item.has_debt
        ? `<span class="badge badge-danger">${t('Qarzdor')}</span>`
        : `<span class="badge badge-success">${t('Qarzsiz')}</span>`;
    const debtLabel = item.has_debt
        ? t('Qarzi: {amount}', { amount: formatMoneyMap(item.remaining) })
        : t("Qarzi yo'q");
    const ariaLabel = `${item.full_name}. ${debtLabel}. ${t('Hisobotni ochish')}`;
    return `
        <div class="list-row client-item-card" data-client-id="${item.id}" role="button" tabindex="0" aria-label="${escapeHtml(ariaLabel)}">
            <div class="avatar ${item.has_debt ? '' : 'is-muted'}" aria-hidden="true">${escapeHtml(getInitials(item.full_name))}</div>
            <div class="row-main">
                <div class="row-title">${escapeHtml(item.full_name)}</div>
                <div class="row-meta">${phoneHtml}${dateHtml}</div>
            </div>
            <div class="row-side">
                ${amountHtml}
                ${badgeHtml}
            </div>
            ${icon('chevron-right', 'row-chevron')}
        </div>
    `;
}

function updateResultCount() {
    const el = document.getElementById('clients-result-count');
    if (!el) return;
    const total = state.summaries.length;
    const shown = state.filteredList.length;
    el.textContent = shown === total
        ? t('{total} ta mijoz', { total })
        : t('{shown} / {total} ta mijoz', { shown, total });
}

function renderClientsList() {
    const container = document.getElementById('clients-list');
    if (!container) return;

    state.filteredList = getProcessedList();
    state.renderedCount = 0;
    container.removeAttribute('aria-busy');
    updateResultCount();

    if (state.filteredList.length === 0) {
        if (state.summaries.length === 0) {
            container.innerHTML = stateBlockHTML({
                iconName: 'users',
                title: t("Hali mijozlar yo'q"),
                desc: t("Birinchi qarz yozuvini yarating — mijoz avtomatik qo'shiladi."),
                action: { id: 'go-create', label: t("Yangi qarz qo'shish") },
            });
        } else if (state.searchQuery.trim()) {
            container.innerHTML = stateBlockHTML({
                iconName: 'search',
                title: t('Hech narsa topilmadi'),
                desc: t('"{query}" bo\'yicha mijoz topilmadi. Ism yoki raqamni tekshiring.', { query: state.searchQuery.trim() }),
                action: { id: 'clear-search', label: t('Qidiruvni tozalash') },
            });
        } else {
            container.innerHTML = stateBlockHTML({
                iconName: 'inbox',
                title: state.filter === 'debtors' ? t("Qarzdor mijozlar yo'q") : t("Qarzsiz mijozlar yo'q"),
                desc: state.filter === 'debtors' ? t("Barcha mijozlarning qarzi yopilgan.") : '',
            });
        }
        return;
    }

    container.innerHTML = '';
    appendClientBatch();
}

function appendClientBatch() {
    const container = document.getElementById('clients-list');
    if (!container) return;

    const oldSentinel = document.getElementById('client-list-sentinel');
    if (oldSentinel) oldSentinel.remove();

    const nextBatch = state.filteredList.slice(state.renderedCount, state.renderedCount + BATCH_SIZE);
    if (nextBatch.length === 0) return;

    const fragment = document.createDocumentFragment();
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = nextBatch.map(renderClientCardHTML).join('');

    while (tempDiv.firstChild) {
        fragment.appendChild(tempDiv.firstChild);
    }
    container.appendChild(fragment);

    state.renderedCount += nextBatch.length;

    if (state.renderedCount < state.filteredList.length) {
        const sentinel = document.createElement('div');
        sentinel.id = 'client-list-sentinel';
        sentinel.className = 'list-sentinel';
        sentinel.textContent = t('Yuklanmoqda…');
        container.appendChild(sentinel);

        if (!listObserver) {
            listObserver = new IntersectionObserver((entries) => {
                if (entries[0] && entries[0].isIntersecting) {
                    appendClientBatch();
                }
            }, { rootMargin: '200px' });
        }
        listObserver.observe(sentinel);
    }
}

// Jadvaldan tanlangan mavjud mijozga yangi qarz qo'shishni boshlaydi:
// Yaratish tabini ochib, ism/telefonni to'ldiradi (dublikat bo'lmaydi)
function startAddDebtForClient(person) {
    hapticImpact();
    switchTab('tab-create');

    // Sana har doim bugunga tenglanadi — keyingi qarz to'g'ri sanada yoziladi
    const dateInput = document.getElementById('create-date');
    if (dateInput) dateInput.value = getTodayFormatted();

    selectExistingClient(person);

    // Avto-foküs yo'q — aks holda klaviatura darrov ochilib,
    // pastki navigatsiya bar tepaga ko'tarilib qoladi
}

// Yaratish formasida mavjud mijozni tanlaydi: qarz shu mijozga yoziladi (dublikat yaratilmaydi)
function selectExistingClient(person) {
    const nameInput = document.getElementById('create-client-name');
    const phoneInput = document.getElementById('create-client-phone');
    if (nameInput) nameInput.value = person.full_name || '';
    // Telefon server uchun asosiy identifikator — telefonsiz mijozda maydon bo'sh qoladi
    if (phoneInput) phoneInput.value = person.phone || '';
    closeClientSuggestions();
    updateDuplicateHint();

    const banner = document.getElementById('create-client-banner');
    if (banner) {
        document.getElementById('banner-client-name').textContent = person.full_name || '-';
        document.getElementById('banner-client-phone').textContent = person.phone || t('Telefon kiritilmagan');
        banner.style.display = 'flex';
        // Ism/telefon allaqachon ma'lum — takroriy maydonlar yashiriladi
        document.getElementById('create-debt-form')?.classList.add('has-selected-client');
        clearFormErrors(document.getElementById('create-debt-form'));
    }

    // Mijozning eski qarzlarini ko'rsatamiz
    loadExistingDebts(person.id);
}

// ==========================================
// COMPONENT: MIJOZ TAKLIFLARI (combobox) — dublikat mijozlarning oldini oladi
// ==========================================

const suggestState = { items: [], activeIndex: -1 };

function findClientMatches(query, limit = 5) {
    const q = normalizeText(query);
    if (q.length < 2) return [];
    const scored = [];
    for (const item of state.summaries) {
        const name = normalizeText(item.full_name);
        let score = -1;
        if (name === q) score = 0;
        else if (name.startsWith(q)) score = 1;
        else if (name.split(' ').some(part => part.startsWith(q))) score = 2;
        else if (name.includes(q)) score = 3;
        if (score >= 0) scored.push({ item, score });
    }
    scored.sort((a, b) => a.score - b.score || (a.item.full_name || '').localeCompare(b.item.full_name || '', 'uz'));
    return scored.slice(0, limit).map(x => x.item);
}

function findExactClient(name) {
    const q = normalizeText(name);
    if (!q) return null;
    return state.summaries.find(item => normalizeText(item.full_name) === q) || null;
}

function renderClientSuggestions() {
    const input = document.getElementById('create-client-name');
    const listEl = document.getElementById('client-suggestions');
    if (!input || !listEl) return;
    const matches = findClientMatches(input.value);
    suggestState.items = matches;
    suggestState.activeIndex = -1;
    if (matches.length === 0) {
        closeClientSuggestions();
        return;
    }
    listEl.innerHTML = `
        <div class="dropdown-header">${t('Mavjud mijozlar — tanlasangiz qarz shu mijozga yoziladi')}</div>
        ${matches.map((m, i) => `
            <div class="dropdown-option" role="option" id="client-suggestion-${i}" data-index="${i}" aria-selected="false">
                <div class="avatar avatar-sm ${m.has_debt ? '' : 'is-muted'}" aria-hidden="true">${escapeHtml(getInitials(m.full_name))}</div>
                <div class="dropdown-option-texts">
                    <span class="dropdown-option-title">${escapeHtml(m.full_name)}</span>
                    <span class="dropdown-option-meta">${escapeHtml(m.phone || t('Telefon kiritilmagan'))}</span>
                </div>
                ${m.has_debt
                    ? `<span class="dropdown-option-amount text-danger">${escapeHtml(formatMoneyMap(m.remaining))}</span>`
                    : `<span class="badge badge-success">${t('Qarzsiz')}</span>`}
            </div>
        `).join('')}
    `;
    listEl.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    input.removeAttribute('aria-activedescendant');
}

function closeClientSuggestions() {
    const input = document.getElementById('create-client-name');
    const listEl = document.getElementById('client-suggestions');
    if (listEl) {
        listEl.hidden = true;
        listEl.innerHTML = '';
    }
    suggestState.items = [];
    suggestState.activeIndex = -1;
    input?.setAttribute('aria-expanded', 'false');
    input?.removeAttribute('aria-activedescendant');
}

function setActiveSuggestion(index) {
    const input = document.getElementById('create-client-name');
    const options = document.querySelectorAll('#client-suggestions .dropdown-option');
    if (!options.length) return;
    suggestState.activeIndex = (index + options.length) % options.length;
    options.forEach((opt, i) => {
        const active = i === suggestState.activeIndex;
        opt.setAttribute('aria-selected', String(active));
        opt.classList.toggle('is-active', active);
        if (active) opt.scrollIntoView({ block: 'nearest' });
    });
    input?.setAttribute('aria-activedescendant', `client-suggestion-${suggestState.activeIndex}`);
}

// Ro'yxatdan tanlanmagan, lekin aynan shu ismli mijoz mavjud bo'lsa — ogohlantiramiz
function updateDuplicateHint() {
    const input = document.getElementById('create-client-name');
    const phoneInput = document.getElementById('create-client-phone');
    const hint = document.getElementById('client-duplicate-hint');
    if (!input || !hint) return;
    const form = document.getElementById('create-debt-form');
    const existing = form?.classList.contains('has-selected-client') ? null : findExactClient(input.value);
    const phoneMatches = existing && existing.phone && digitsOnly(phoneInput?.value) === digitsOnly(existing.phone);
    if (!existing || phoneMatches) {
        hint.hidden = true;
        hint.innerHTML = '';
        return;
    }
    hint.hidden = false;
    hint.innerHTML = `
        ${icon('info')}
        <span>${t('«{name}» ismli mijoz allaqachon mavjud. Qarzni unga yozish uchun tanlang, aks holda yangi mijoz yaratiladi.', { name: escapeHtml(existing.full_name) })}</span>
        <button type="button" class="btn btn-ghost btn-sm" id="btn-use-existing-client" data-client-id="${existing.id}">${t('Tanlash')}</button>
    `;
}

function setupClientSuggestions() {
    const input = document.getElementById('create-client-name');
    const phoneInput = document.getElementById('create-client-phone');
    const listEl = document.getElementById('client-suggestions');
    if (!input || !listEl) return;

    input.addEventListener('input', () => {
        renderClientSuggestions();
        updateDuplicateHint();
    });
    input.addEventListener('focus', () => {
        if (input.value.trim().length >= 2) renderClientSuggestions();
    });
    // Tanlash uchun bosilgan option'ga fokus ketishidan oldin blur ro'yxatni yopmasligi uchun kechiktiramiz
    input.addEventListener('blur', () => setTimeout(closeClientSuggestions, 150));
    input.addEventListener('keydown', (e) => {
        if (listEl.hidden) return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActiveSuggestion(suggestState.activeIndex + 1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActiveSuggestion(suggestState.activeIndex - 1);
        } else if (e.key === 'Enter' && suggestState.activeIndex >= 0) {
            e.preventDefault();
            selectExistingClient(suggestState.items[suggestState.activeIndex]);
            hapticImpact();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            closeClientSuggestions();
        }
    });
    // mousedown/touch — input blur'idan oldin ishlaydi
    listEl.addEventListener('mousedown', (e) => e.preventDefault());
    listEl.addEventListener('click', (e) => {
        const opt = e.target.closest('.dropdown-option');
        if (!opt) return;
        const item = suggestState.items[Number(opt.getAttribute('data-index'))];
        if (item) {
            selectExistingClient(item);
            hapticImpact();
        }
    });

    phoneInput?.addEventListener('input', updateDuplicateHint);
    document.getElementById('client-duplicate-hint')?.addEventListener('click', (e) => {
        const btn = e.target.closest('#btn-use-existing-client');
        if (!btn) return;
        const item = state.summaries.find(s => String(s.id) === btn.getAttribute('data-client-id'));
        if (item) {
            selectExistingClient(item);
            hapticImpact();
        }
    });
}

// Mijozning joriy (yopilmagan) qarzlarini yuklab banner ostida ko'rsatadi
async function loadExistingDebts(clientId) {
    const card = document.getElementById('banner-debts-card');
    const listEl = document.getElementById('banner-debts-list');
    const totalEl = document.getElementById('banner-client-debt');
    if (!card || !listEl || !clientId) return;

    card.style.display = 'block';
    totalEl.textContent = '…';
    listEl.innerHTML = `<div class="banner-debt-loading">${t('Yuklanmoqda…')}</div>`;

    const data = await fetchClientReport(clientId);
    if (!data) {
        card.style.display = 'none';
        return;
    }

    const remaining = data.total_remaining_debt || {};
    const hasDebt = Object.values(remaining).some(v => (Number(v) || 0) > 0);
    totalEl.textContent = hasDebt ? formatMoneyMap(remaining) : t("Qarz yo'q");
    totalEl.className = hasDebt ? 'text-danger' : 'text-success';

    const activeDebts = (data.debts || []).filter(d => d.status === 'active');
    if (activeDebts.length === 0) {
        listEl.innerHTML = `<div class="banner-no-debt">${t("Yopilmagan qarzi yo'q")}</div>`;
        return;
    }

    listEl.innerHTML = activeDebts.map(d => {
        const qtyLabel = d.product_quantity > 1 ? ` × ${d.product_quantity}` : '';
        return `
            <div class="banner-debt-item">
                <span class="banner-debt-name"><span class="banner-debt-date">${escapeHtml(d.debt_date)}</span>${escapeHtml(d.product_name)}${qtyLabel}</span>
                <span class="banner-debt-sum">${formatMoney(d.remaining_debt, d.currency)}</span>
            </div>
        `;
    }).join('');
}

// Bannerdan voz kechish — boshqa (yangi) mijoz kiritish uchun maydonlarni bo'shatadi
function clearCreateClientBanner() {
    const banner = document.getElementById('create-client-banner');
    const debtsCard = document.getElementById('banner-debts-card');
    if (banner) banner.style.display = 'none';
    if (debtsCard) debtsCard.style.display = 'none';
    document.getElementById('create-debt-form')?.classList.remove('has-selected-client');
    const nameInput = document.getElementById('create-client-name');
    const phoneInput = document.getElementById('create-client-phone');
    if (nameInput) nameInput.value = '';
    if (phoneInput) phoneInput.value = '';
    updateDuplicateHint();
}

function escapeHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ==========================================
// CLIENT REPORT MODAL
// ==========================================

let modalReturnFocus = null;
let modalRequestId = 0;

function onModalBackButton() {
    closeClientReportModal();
}

function onModalKeydown(e) {
    const modal = document.getElementById('report-modal');
    if (!modal || modal.style.display === 'none') return;
    if (e.key === 'Escape') {
        e.preventDefault();
        closeClientReportModal();
        return;
    }
    // Fokus dialog ichida aylanadi (focus trap)
    if (e.key === 'Tab') {
        const focusables = [...modal.querySelectorAll('button:not([disabled]), [href], input, select, [tabindex]:not([tabindex="-1"])')]
            .filter(el => el.offsetParent !== null);
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    }
}

function historyEmptyHTML(text) {
    return `<div class="history-empty">${escapeHtml(text)}</div>`;
}

function renderDebtHistoryCard(d) {
    const products = d.products || [];
    const productListHtml = products.length > 1
        ? products.map((p, i) => {
            const pCur = p.currency || d.currency;
            const qtyPart = p.quantity > 1 ? ` · ${p.quantity} × ${formatMoney(p.price_per_unit, pCur)}` : '';
            return `
                <div class="history-card-detail is-sub">
                    <span>${i + 1}. ${escapeHtml(p.name)}${qtyPart}</span>
                    <span>${formatMoney(p.quantity * p.price_per_unit, pCur)}</span>
                </div>
            `;
        }).join('')
        : '';

    const isActive = d.status === 'active';
    const statusHtml = isActive
        ? `<span class="history-amount text-danger">${formatMoney(d.remaining_debt, d.currency)}</span>`
        : `<span class="badge badge-success">${t('Yopilgan')}</span>`;

    return `
        <div class="history-card">
            <div class="history-card-header">
                <span>${escapeHtml(d.product_name)}${d.product_quantity > 1 ? ` × ${d.product_quantity}` : ''}</span>
                ${statusHtml}
            </div>
            ${productListHtml}
            <div class="history-card-detail">
                <span class="row-meta-item">${icon('calendar')}${escapeHtml(d.debt_date)}</span>
                <span>${t('Narxi: {amount}', { amount: formatMoney(d.product_price, d.currency) })}</span>
            </div>
            ${d.exchange_exists ? `
            <div class="history-card-detail is-exchange">
                <span>${t('Exchange: {name}', { name: escapeHtml(d.exchange_product_name || t('Tovar')) })}</span>
                <span>−${formatMoney(d.exchange_product_price, d.currency)}</span>
            </div>` : ''}
            ${d.given_money > 0 ? `
            <div class="history-card-detail is-given">
                <span>${t("Boshlang'ich to'lov")}</span>
                <span>−${formatMoney(d.given_money, d.currency)}</span>
            </div>` : ''}
        </div>
    `;
}

async function openClientReportModal(clientId) {
    hapticImpact();
    const modal = document.getElementById('report-modal');
    if (!modal) return;
    const requestId = ++modalRequestId;

    // 1. Keshdagi mijoz ma'lumotlari orqali modalni DARHOL ochamiz (0ms kechikish)
    const cached = state.summaries.find(s => String(s.id) === String(clientId));
    const remainingEl = document.getElementById('modal-total-remaining');
    if (cached) {
        document.getElementById('modal-client-name').textContent = cached.full_name;
        document.getElementById('modal-client-phone').textContent = cached.phone || t('Telefon kiritilmagan');
        remainingEl.textContent = cached.has_debt ? formatMoneyMap(cached.remaining) : t("Qarz yo'q");
    } else {
        document.getElementById('modal-client-name').textContent = t('Mijoz hisoboti');
        document.getElementById('modal-client-phone').textContent = t('Yuklanmoqda…');
        remainingEl.textContent = '…';
    }
    document.getElementById('modal-total-products').textContent = '…';
    document.getElementById('modal-total-paid').textContent = '…';

    const debtsList = document.getElementById('modal-debts-list');
    const paymentsList = document.getElementById('modal-payments-list');
    if (debtsList) debtsList.innerHTML = `<div class="history-loading">${t('Tarix yuklanmoqda…')}</div>`;
    if (paymentsList) paymentsList.innerHTML = `<div class="history-loading">${t('Yuklanmoqda…')}</div>`;

    // Hisobot yuklanmaguncha amallar o'chiq turadi
    const payBtn = document.getElementById('modal-pay-now-btn');
    const addBtn = document.getElementById('modal-add-debt-btn');
    if (payBtn) payBtn.disabled = true;
    if (addBtn) addBtn.disabled = true;

    const wasOpen = modal.style.display !== 'none';
    modal.style.display = 'flex';
    if (!wasOpen) {
        modalReturnFocus = document.activeElement;
        document.body.classList.add('modal-open');
        document.addEventListener('keydown', onModalKeydown);
        try {
            tg?.BackButton?.onClick(onModalBackButton);
            tg?.BackButton?.show();
        } catch (e) {}
        document.getElementById('modal-close-btn')?.focus({ preventScroll: true });
    }

    // 2. Fonda to'liq hisobotni yuklab, modalni to'ldiramiz
    const data = await fetchClientReport(clientId);
    // Foydalanuvchi bu orada modalni yopgan yoki boshqa mijozni ochgan bo'lishi mumkin
    if (requestId !== modalRequestId || modal.style.display === 'none') return;
    if (!data) {
        if (debtsList) debtsList.innerHTML = historyEmptyHTML(t("Hisobotni yuklab bo'lmadi"));
        if (paymentsList) paymentsList.innerHTML = historyEmptyHTML('—');
        showToast(t("Mijoz ma'lumotlarini yuklab bo'lmadi"), 'error');
        return;
    }

    state.selectedClientReport = data;

    document.getElementById('modal-client-name').textContent = data.client.full_name;
    document.getElementById('modal-client-phone').textContent = data.client.phone || t('Telefon kiritilmagan');
    document.getElementById('modal-total-products').innerHTML = formatMoneyLinesHTML(data.total_product_price);
    document.getElementById('modal-total-paid').innerHTML = formatMoneyLinesHTML(sumMaps(data.total_paid_after, data.total_given_money));

    const remainingValues = Object.values(data.total_remaining_debt || {});
    const hasAnyDebt = remainingValues.some(v => (Number(v) || 0) > 0);
    remainingEl.textContent = hasAnyDebt ? formatMoneyMap(data.total_remaining_debt) : t("Qarz yo'q");
    remainingEl.classList.toggle('text-danger', hasAnyDebt);
    remainingEl.classList.toggle('text-success', !hasAnyDebt);
    remainingEl.closest('.modal-kpi')?.classList.toggle('modal-kpi-primary', hasAnyDebt);

    // Qarzlar tarixi — ko'p tovarli bo'lsa har bir tovar alohida ko'rsatiladi
    debtsList.innerHTML = data.debts.length === 0
        ? historyEmptyHTML(t('Qarzlar mavjud emas'))
        : data.debts.map(renderDebtHistoryCard).join('');

    // To'lovlar tarixi
    const actualPayments = data.payments.filter(p => p.payment_type !== 'initial');
    paymentsList.innerHTML = actualPayments.length === 0
        ? historyEmptyHTML(t("To'lovlar mavjud emas"))
        : actualPayments.map(p => `
            <div class="history-card">
                <div class="history-card-header">
                    <span class="history-amount text-success">+${formatMoney(p.amount, p.currency)}</span>
                    <span class="badge badge-neutral">${p.payment_type === 'full' ? t("To'liq") : t('Qisman')}</span>
                </div>
                <div class="history-card-detail">
                    <span class="row-meta-item">${icon('calendar')}${escapeHtml(p.payment_date)}</span>
                </div>
            </div>
        `).join('');

    if (addBtn) addBtn.disabled = false;
    if (payBtn) {
        payBtn.disabled = false;
        payBtn.style.display = hasAnyDebt ? '' : 'none';
    }
    modal.querySelector('.modal-footer')?.classList.toggle('single-action', !hasAnyDebt);
}

function closeClientReportModal() {
    const modal = document.getElementById('report-modal');
    if (!modal || modal.style.display === 'none') return;
    modal.style.display = 'none';
    state.selectedClientReport = null;
    document.body.classList.remove('modal-open');
    document.removeEventListener('keydown', onModalKeydown);
    try {
        tg?.BackButton?.offClick(onModalBackButton);
        tg?.BackButton?.hide();
    } catch (e) {}
    if (modalReturnFocus && document.contains(modalReturnFocus)) {
        try {
            modalReturnFocus.focus({ preventScroll: true });
        } catch (e) {}
    }
    modalReturnFocus = null;
}

// ==========================================
// TAB 2: CREATE DEBT FORM — DINAMIK TOVARLAR (har biri o'z valyutasida)
// ==========================================

// Tovar va exchange kartalari bir xil tuzilishda: nomi, soni, narxi, valyutasi
// Matnlar t() bilan ishlatilgan joyda o'giriladi ({num} — tartib raqami)
const GROUP_KINDS = {
    product: {
        container: 'products-container',
        title: N_('{num}-tovar'),
        remove: N_("{num}-tovarni o'chirish"),
        noName: N_('{num}-tovar nomini kiriting'),
        noPrice: N_('{num}-tovar narxini kiriting'),
        placeholder: N_('Masalan: Shina, Akkumulyator'),
    },
    exchange: {
        container: 'exchanges-container',
        title: N_('{num}-exchange'),
        remove: N_("{num}-exchange'ni o'chirish"),
        noName: N_('{num}-exchange nomini kiriting'),
        noPrice: N_('{num}-exchange narxini kiriting'),
        placeholder: N_('Masalan: Eski shina R16'),
    },
};

function createProductGroupHTML(index, kind = 'product') {
    const g = GROUP_KINDS[kind];
    const num = index + 1;
    const removeBtn = index > 0
        ? `<button type="button" class="btn-remove-product" aria-label="${escapeHtml(t(g.remove, { num }))}">${icon('trash')}${t("O'chirish")}</button>`
        : '';
    return `
        <div class="product-group" data-product-index="${index}">
            <div class="product-group-header">
                <span class="product-group-title">${t(g.title, { num })}</span>
                ${removeBtn}
            </div>
            <div class="form-group">
                <label>${t('Nomi')} <span class="req" aria-hidden="true">*</span></label>
                <input type="text" class="product-name" placeholder="${escapeHtml(t(g.placeholder))}" autocomplete="off" required>
            </div>
            <div class="product-row">
                <div class="form-group">
                    <label>${t('Soni')}</label>
                    <input type="number" class="product-qty" placeholder="1" min="1" step="1" value="1" inputmode="numeric" required>
                </div>
                <div class="form-group">
                    <label>${t('Narxi (1 dona)')} <span class="req" aria-hidden="true">*</span></label>
                    <input type="number" class="product-price" placeholder="0" min="1" step="1000" inputmode="numeric" required>
                </div>
            </div>
            <div class="product-footer">
                <div class="currency-chips" role="group" aria-label="${escapeHtml(t('Valyuta'))}">
                    <button type="button" class="cur-chip active" data-currency="UZS" aria-pressed="true">${t("So'm")}</button>
                    <button type="button" class="cur-chip" data-currency="USD" aria-pressed="false">${t('Dollar')}</button>
                </div>
                <div class="product-subtotal">
                    <span>${t('Jami')}</span>
                    <strong class="product-subtotal-val">${formatMoney(0)}</strong>
                </div>
            </div>
        </div>
    `;
}

function getProductGroups(kind = 'product') {
    return document.querySelectorAll(`#${GROUP_KINDS[kind].container} .product-group`);
}

function getGroupCurrency(group) {
    const active = group.querySelector('.cur-chip.active');
    return active ? active.getAttribute('data-currency') : 'UZS';
}

function renumberProductGroups(kind = 'product') {
    const g = GROUP_KINDS[kind];
    const groups = getProductGroups(kind);
    groups.forEach((group, i) => {
        const title = group.querySelector('.product-group-title');
        if (title) title.textContent = t(g.title, { num: i + 1 });
        group.querySelector('.btn-remove-product')?.setAttribute('aria-label', t(g.remove, { num: i + 1 }));
        group.setAttribute('data-product-index', i);
    });
}

function getProductsData(kind = 'product') {
    const groups = getProductGroups(kind);
    const products = [];
    groups.forEach(group => {
        const name = group.querySelector('.product-name')?.value.trim() || '';
        const qty = Math.max(1, Math.floor(Number(group.querySelector('.product-qty')?.value) || 1));
        const price = Math.floor(Number(group.querySelector('.product-price')?.value) || 0);
        const currency = getGroupCurrency(group);
        if (name && price > 0) {
            products.push({ name, quantity: qty, price_per_unit: price, currency });
        }
    });
    return products;
}

function getChipsCurrency(containerId) {
    const active = document.querySelector(`#${containerId} .cur-chip.active`);
    return active ? active.getAttribute('data-currency') : 'UZS';
}

function attachChipsListeners(container) {
    container.querySelectorAll('.cur-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            // Faqat shu guruh ichidagi chipslardan aktivlikni olib tashlaymiz
            chip.closest('.currency-chips').querySelectorAll('.cur-chip').forEach(c => {
                c.classList.remove('active');
                c.setAttribute('aria-pressed', 'false');
            });
            chip.classList.add('active');
            chip.setAttribute('aria-pressed', 'true');
            updateCreateCalculation();
            hapticImpact();
        });
    });
}

function updateCreateCalculation() {
    const products = getProductsData();

    // Har bir guruhning (tovar va exchange) subtotal'ini o'z valyutasida yangilaymiz
    const groups = [...getProductGroups(), ...getProductGroups('exchange')];
    groups.forEach(group => {
        const qty = Math.max(1, Math.floor(Number(group.querySelector('.product-qty')?.value) || 1));
        const price = Math.floor(Number(group.querySelector('.product-price')?.value) || 0);
        const currency = getGroupCurrency(group);
        const subtotal = qty * price;
        const subtotalEl = group.querySelector('.product-subtotal-val');
        if (subtotalEl) {
            subtotalEl.textContent = qty > 1
                ? `${qty} × ${formatMoney(price, currency)} = ${formatMoney(subtotal, currency)}`
                : formatMoney(price, currency);
        }
    });

    // Valyutalar bo'yicha tovarlar jami
    const totals = {};
    products.forEach(p => {
        totals[p.currency] = (totals[p.currency] || 0) + p.quantity * p.price_per_unit;
    });

    const exchangeToggle = document.getElementById('create-exchange-toggle');
    const givenToggle = document.getElementById('create-given-toggle');
    const givenAmountInput = document.getElementById('create-given-amount');

    const hasExchange = exchangeToggle?.checked;
    const exchangeTotals = {};
    if (hasExchange) {
        getProductsData('exchange').forEach(e => {
            exchangeTotals[e.currency] = (exchangeTotals[e.currency] || 0) + e.quantity * e.price_per_unit;
        });
    }
    const hasGiven = givenToggle?.checked;
    const givenCurrency = getChipsCurrency('given-currency-chips');
    const givenAmount = hasGiven ? (Number(givenAmountInput?.value) || 0) : 0;

    const productCalcEl = document.getElementById('calc-product-price');
    if (productCalcEl) {
        if (products.length === 1) {
            const p = products[0];
            productCalcEl.textContent = p.quantity > 1
                ? `${p.quantity} × ${formatMoney(p.price_per_unit, p.currency)} = ${formatMoney(p.quantity * p.price_per_unit, p.currency)}`
                : formatMoney(p.price_per_unit, p.currency);
        } else {
            productCalcEl.textContent = formatMoneyMap(totals);
        }
    }

    const exRow = document.getElementById('calc-exchange-row');
    if (exRow) {
        exRow.style.display = hasExchange ? 'flex' : 'none';
        document.getElementById('calc-exchange-price').textContent = `-${formatMoneyMap(exchangeTotals)}`;
    }

    const givenRow = document.getElementById('calc-given-row');
    if (givenRow) {
        givenRow.style.display = hasGiven ? 'flex' : 'none';
        document.getElementById('calc-given-price').textContent = `-${formatMoney(givenAmount, givenCurrency)}`;
    }

    // Har bir valyutada alohida hisoblab, jami qarzni yig'amiz
    const remaining = { ...totals };
    Object.entries(exchangeTotals).forEach(([cur, amount]) => {
        remaining[cur] = Math.max(0, (remaining[cur] || 0) - amount);
    });
    if (hasGiven && givenAmount > 0) {
        remaining[givenCurrency] = Math.max(0, (remaining[givenCurrency] || 0) - givenAmount);
    }
    document.getElementById('calc-total-debt').textContent = formatMoneyMap(remaining);
}

function attachProductGroupListeners(container) {
    // Narx/miqdor o'zgarganda subtotal + grand total yangilanadi
    container.querySelectorAll('.product-qty, .product-price, .product-name').forEach(el => {
        el.addEventListener('input', () => {
            clearFieldError(el);
            updateCreateCalculation();
        });
    });
    // Valyuta chipslari
    attachChipsListeners(container);
    // O'chirish tugmasi
    container.querySelectorAll('.btn-remove-product').forEach(btn => {
        btn.addEventListener('click', () => {
            const group = btn.closest('.product-group');
            if (group) {
                const kind = group.closest('#exchanges-container') ? 'exchange' : 'product';
                group.remove();
                renumberProductGroups(kind);
                updateCreateCalculation();
                hapticImpact();
            }
        });
    });
}

function setupCreateForm() {
    const dateInput = document.getElementById('create-date');
    const btnToday = document.getElementById('btn-set-today');
    const btnAddProduct = document.getElementById('btn-add-product');
    const exchangeToggle = document.getElementById('create-exchange-toggle');
    const exchangeFields = document.getElementById('exchange-fields');
    const exchangesContainer = document.getElementById('exchanges-container');
    const btnAddExchange = document.getElementById('btn-add-exchange');
    const givenToggle = document.getElementById('create-given-toggle');
    const givenFields = document.getElementById('given-money-fields');
    const givenAmountInput = document.getElementById('create-given-amount');
    const submitBtn = document.getElementById('btn-submit-debt');

    const form = document.getElementById('create-debt-form');
    const nameInput = document.getElementById('create-client-name');
    const phoneInput = document.getElementById('create-client-phone');

    // Enter tugmasi formani sahifa bo'ylab yubormasligi uchun
    form?.addEventListener('submit', (e) => e.preventDefault());

    // Default Date to Today
    if (dateInput) dateInput.value = getTodayFormatted();
    attachDateMask(dateInput);
    [dateInput, nameInput, phoneInput].forEach(el => {
        el?.addEventListener('input', () => clearFieldError(el));
    });
    if (btnToday) {
        btnToday.addEventListener('click', () => {
            if (dateInput) dateInput.value = getTodayFormatted();
            clearFieldError(dateInput);
            hapticImpact();
        });
    }

    // Boshlang'ich tovar guruhiga listenerlar qo'shamiz
    const container = document.getElementById('products-container');
    if (container) attachProductGroupListeners(container);

    // Yangi tovar yoki exchange kartasini qo'shadi
    const addGroup = (kind, scroll = true) => {
        const target = document.getElementById(GROUP_KINDS[kind].container);
        const wrapper = document.createElement('div');
        wrapper.innerHTML = createProductGroupHTML(getProductGroups(kind).length, kind);
        const newGroup = wrapper.firstElementChild;
        target.appendChild(newGroup);
        attachProductGroupListeners(newGroup);
        updateCreateCalculation();
        hapticImpact();

        // Yangi kartani ko'rinadigan joyga silliq suramiz —
        // fokus qo'ymaymiz, klaviatura o'z-o'zidan ochilib yuborilmaydi
        if (scroll) {
            setTimeout(() => {
                newGroup.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 50);
        }
    };
    btnAddProduct?.addEventListener('click', () => addGroup('product'));
    btnAddExchange?.addEventListener('click', () => addGroup('exchange'));

    // Toggle Exchange: yoqilganda birinchi exchange kartasi paydo bo'ladi
    if (exchangeToggle) {
        exchangeToggle.addEventListener('change', () => {
            exchangeFields.style.display = exchangeToggle.checked ? 'block' : 'none';
            if (exchangesContainer) exchangesContainer.innerHTML = '';
            if (exchangeToggle.checked) addGroup('exchange', false);
            updateCreateCalculation();
            hapticImpact();
        });
    }

    // Toggle Given Money
    if (givenToggle) {
        givenToggle.addEventListener('change', () => {
            givenFields.style.display = givenToggle.checked ? 'block' : 'none';
            if (!givenToggle.checked && givenAmountInput) givenAmountInput.value = '';
            updateCreateCalculation();
            hapticImpact();
        });
    }

    // Berilgan pul valyuta chipslari va input'i
    attachChipsListeners(document.getElementById('given-currency-chips') || document.createElement('div'));
    givenAmountInput?.addEventListener('input', () => {
        clearFieldError(givenAmountInput);
        updateCreateCalculation();
    });

    // Submit New Debt
    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const clientName = document.getElementById('create-client-name')?.value.trim();
            const clientPhone = document.getElementById('create-client-phone')?.value.trim();
            const debtDate = dateInput?.value.trim() || getTodayFormatted();

            const products = getProductsData();

            const hasExchange = exchangeToggle?.checked || false;
            const exchanges = hasExchange ? getProductsData('exchange') : [];

            const hasGiven = givenToggle?.checked || false;
            const givenCurrency = getChipsCurrency('given-currency-chips');
            const givenMoney = hasGiven ? (Number(givenAmountInput?.value) || 0) : 0;

            clearFormErrors(form);
            const hasSelectedClient = form?.classList.contains('has-selected-client');

            if (!clientName) {
                if (hasSelectedClient) clearCreateClientBanner();
                setFieldError(nameInput, t('Mijozning ism-familiyasini kiriting'));
                return;
            }
            if (clientPhone) {
                const phoneDigits = clientPhone.replace(/\D/g, '');
                if (phoneDigits.length < 7 || phoneDigits.length > 15) {
                    setFieldError(phoneInput, t("Telefon raqami noto'g'ri. Masalan: +998901234567"));
                    return;
                }
            }
            if (!isValidDateString(debtDate)) {
                setFieldError(dateInput, t("Sana noto'g'ri. KK.OO.YYYY ko'rinishida kiriting, masalan: 16.08.2026"));
                return;
            }

            // Har bir tovar/exchange kartasini tekshiramiz: yarim to'ldirilgan kartani o'tkazib yubormaymiz
            const groups = [...getProductGroups()];
            for (const kind of hasExchange ? ['product', 'exchange'] : ['product']) {
                const kindGroups = [...getProductGroups(kind)];
                const g = GROUP_KINDS[kind];
                for (let i = 0; i < kindGroups.length; i++) {
                    const nameEl = kindGroups[i].querySelector('.product-name');
                    const priceEl = kindGroups[i].querySelector('.product-price');
                    const hasName = !!nameEl?.value.trim();
                    const hasPrice = (Number(priceEl?.value) || 0) > 0;
                    if (hasName && !hasPrice) {
                        setFieldError(priceEl, t(g.noPrice, { num: i + 1 }));
                        return;
                    }
                    if (!hasName && hasPrice) {
                        setFieldError(nameEl, t(g.noName, { num: i + 1 }));
                        return;
                    }
                }
            }
            if (products.length === 0) {
                const firstName = groups[0]?.querySelector('.product-name');
                setFieldError(firstName, t('Kamida bitta tovar nomi va narxini kiriting'));
                return;
            }

            // Har bir valyutada chegirmalar tovarlar jami narxidan oshmasligi kerak
            const totals = {};
            products.forEach(p => {
                totals[p.currency] = (totals[p.currency] || 0) + p.quantity * p.price_per_unit;
            });
            const deductions = {};
            exchanges.forEach(e => {
                deductions[e.currency] = (deductions[e.currency] || 0) + e.quantity * e.price_per_unit;
            });
            if (hasGiven && givenMoney > 0) {
                deductions[givenCurrency] = (deductions[givenCurrency] || 0) + givenMoney;
            }
            for (const cur of Object.keys(deductions)) {
                if ((deductions[cur] || 0) > (totals[cur] || 0)) {
                    const target = (hasGiven && givenCurrency === cur)
                        ? givenAmountInput
                        : getProductGroups('exchange')[0]?.querySelector('.product-price');
                    setFieldError(target, cur === 'USD'
                        ? t("Exchange va boshlang'ich to'lov dollardagi tovarlar narxidan oshmasligi kerak")
                        : t("Exchange va boshlang'ich to'lov so'mdagi tovarlar narxidan oshmasligi kerak"));
                    return;
                }
            }

            setButtonLoading(submitBtn, true, t('Saqlanmoqda…'));

            try {
                const payload = {
                    client_name: clientName,
                    client_phone: clientPhone,
                    debt_date: debtDate,
                    products: products,
                    exchanges: exchanges,
                    given_money: givenMoney,
                    given_currency: givenCurrency,
                };

                const json = await apiJson('/api/debts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Idempotency-Key': newIdempotencyKey(),
                    },
                    body: JSON.stringify(payload),
                });

                hapticSuccess();
                const remainingText = json.remaining_by_currency ? formatMoneyMap(json.remaining_by_currency) : '';
                showToast(remainingText
                    ? t('Qarz saqlandi: {name} — {amount}', { name: clientName, amount: remainingText })
                    : t('Qarz muvaffaqiyatli saqlandi'), 'success');

                // Reset form — bitta tovar guruhigacha qisqartiramiz
                const productsContainer = document.getElementById('products-container');
                if (productsContainer) {
                    productsContainer.innerHTML = createProductGroupHTML(0);
                    attachProductGroupListeners(productsContainer);
                }

                document.getElementById('create-client-name').value = '';
                document.getElementById('create-client-phone').value = '';
                if (dateInput) dateInput.value = getTodayFormatted();
                if (exchangeFields) exchangeFields.style.display = 'none';
                if (givenFields) givenFields.style.display = 'none';
                if (exchangeToggle) exchangeToggle.checked = false;
                if (exchangesContainer) exchangesContainer.innerHTML = '';
                if (givenToggle) givenToggle.checked = false;
                // Valyuta chipslarini UZSga qaytaramiz
                document.querySelectorAll('#given-currency-chips .cur-chip').forEach(chip => {
                    chip.classList.toggle('active', chip.getAttribute('data-currency') === 'UZS');
                    chip.setAttribute('aria-pressed', String(chip.classList.contains('active')));
                });
                if (givenAmountInput) givenAmountInput.value = '';
                // Banner va eski qarzlar ro'yxati yashiriladi
                clearCreateClientBanner();
                clearFormErrors(form);

                updateCreateCalculation();

                // Jadvalga qaytamiz — switchTab ma'lumotlarni o'zi yangilaydi
                switchTab('tab-table');
            } catch (err) {
                notifyError(err);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        });
    }
}

// ==========================================
// TAB 3: PAYMENT FORM
// ==========================================

// Qarzdorlar ko'p bo'lsa, ro'yxat ustida filtr maydoni ko'rsatiladi
const PAY_SEARCH_THRESHOLD = 8;

function populatePaymentClients() {
    const select = document.getElementById('pay-client-select');
    if (!select) return;

    const previous = select.value;
    const debtors = state.summaries.filter(s => s.has_debt);
    const query = document.getElementById('pay-client-search')?.value || '';
    const searchWrap = document.getElementById('pay-client-search-wrap');
    if (searchWrap) searchWrap.hidden = debtors.length < PAY_SEARCH_THRESHOLD;

    // Tanlangan mijoz filtrga mos kelmasa ham ro'yxatda qoladi — tanlov yo'qolmaydi
    const visible = debtors.filter(d => matchesClientQuery(d, query) || String(d.id) === previous);
    let placeholder = t('Mijozni tanlang');
    if (debtors.length === 0) placeholder = t("Qarzdor mijozlar yo'q");
    else if (query.trim()) {
        placeholder = visible.length
            ? t('{count} ta mos mijoz — tanlang', { count: visible.length })
            : t('Mos mijoz topilmadi');
    }

    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>` +
        visible.map(d => `
            <option value="${d.id}" data-name="${escapeHtml(d.full_name)}" data-phone="${escapeHtml(d.phone)}"
                    data-remaining-uzs="${(d.remaining && d.remaining.UZS) || 0}"
                    data-remaining-usd="${(d.remaining && d.remaining.USD) || 0}">
                ${escapeHtml(d.full_name)} — ${formatMoneyMap(d.remaining)}
            </option>
        `).join('');
    if (previous && visible.some(d => String(d.id) === previous)) {
        select.value = previous;
    } else if (previous) {
        // Mijoz qarzi yopilgan (ro'yxatdan chiqqan) — to'lov kartasi ham yashiriladi
        select.dispatchEvent(new Event('change'));
    }
}

function getPaymentCurrency() {
    return document.querySelector('input[name="payment_currency"]:checked')?.value || 'UZS';
}

function getSelectedDebtInCurrency(opt, currency) {
    if (!opt) return 0;
    const attr = currency === 'USD' ? 'data-remaining-usd' : 'data-remaining-uzs';
    return Number(opt.getAttribute(attr)) || 0;
}

function setupPaymentForm() {
    const form = document.getElementById('payment-form');
    const select = document.getElementById('pay-client-select');
    const payDateInput = document.getElementById('pay-date');
    const btnPayToday = document.getElementById('btn-pay-set-today');
    const infoCard = document.getElementById('pay-client-info-card');
    const optionsWrapper = document.getElementById('pay-options-wrapper');
    const radioModes = document.querySelectorAll('input[name="payment_mode"]');
    const partialGroup = document.getElementById('partial-amount-group');
    const partialInput = document.getElementById('pay-partial-amount');
    const previewAmount = document.getElementById('pay-preview-amount');
    const previewRemaining = document.getElementById('pay-preview-remaining');
    const submitBtn = document.getElementById('btn-submit-payment');

    form?.addEventListener('submit', (e) => e.preventDefault());

    const searchInput = document.getElementById('pay-client-search');
    searchInput?.addEventListener('input', debounce(() => populatePaymentClients(), 120));

    // Default Payment Date to Today
    if (payDateInput) payDateInput.value = getTodayFormatted();
    attachDateMask(payDateInput);
    payDateInput?.addEventListener('input', () => clearFieldError(payDateInput));
    if (btnPayToday) {
        btnPayToday.addEventListener('click', () => {
            if (payDateInput) payDateInput.value = getTodayFormatted();
            clearFieldError(payDateInput);
            hapticImpact();
        });
    }

    if (select) {
        select.addEventListener('change', () => {
            clearFieldError(select);
            const opt = select.selectedOptions[0];
            if (!opt || !opt.value) {
                if (infoCard) infoCard.style.display = 'none';
                if (optionsWrapper) optionsWrapper.style.display = 'none';
                return;
            }

            const name = opt.getAttribute('data-name') || opt.text.split('—')[0].trim();
            const phone = opt.getAttribute('data-phone');
            const remainingMap = {
                UZS: getSelectedDebtInCurrency(opt, 'UZS'),
                USD: getSelectedDebtInCurrency(opt, 'USD'),
            };

            document.getElementById('pay-selected-client-name').textContent = name;
            document.getElementById('pay-selected-client-phone').textContent = phone || t('Telefon kiritilmagan');
            document.getElementById('pay-selected-client-debt').innerHTML = formatMoneyLinesHTML(remainingMap);

            // Qarz faqat bitta valyutada bo'lsa, qisman to'lov valyutasi avtomatik tanlanadi
            if (remainingMap.UZS <= 0 && remainingMap.USD > 0) {
                const usdRadio = document.querySelector('input[name="payment_currency"][value="USD"]');
                if (usdRadio) usdRadio.checked = true;
            } else if (remainingMap.USD <= 0 && remainingMap.UZS > 0) {
                const uzsRadio = document.querySelector('input[name="payment_currency"][value="UZS"]');
                if (uzsRadio) uzsRadio.checked = true;
            }

            infoCard.style.display = 'flex';
            optionsWrapper.style.display = 'block';
            updatePaymentCalculation();
            hapticImpact();
        });
    }

    radioModes.forEach(radio => {
        radio.addEventListener('change', () => {
            const isPartial = radio.value === 'partial';
            if (partialGroup) partialGroup.style.display = isPartial ? 'block' : 'none';
            if (payDateInput && !payDateInput.value) {
                payDateInput.value = getTodayFormatted();
            }
            clearFieldError(partialInput);
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    // Valyuta almashtirilganda hisob yangilanadi
    document.querySelectorAll('input[name="payment_currency"]').forEach(radio => {
        radio.addEventListener('change', () => {
            clearFieldError(partialInput);
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    if (partialInput) {
        partialInput.addEventListener('input', () => {
            clearFieldError(partialInput);
            updatePaymentCalculation();
        });
    }

    // Quick chip buttons
    document.querySelectorAll('.btn-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            const opt = select?.selectedOptions[0];
            const totalDebt = getSelectedDebtInCurrency(opt, getPaymentCurrency());
            const quick = btn.getAttribute('data-quick');

            if (quick === 'half') {
                if (partialInput) partialInput.value = Math.floor(totalDebt / 2);
            } else {
                if (partialInput) partialInput.value = Number(quick) || 0;
            }
            clearFieldError(partialInput);
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    function updatePaymentCalculation() {
        const opt = select?.selectedOptions[0];
        const mode = document.querySelector('input[name="payment_mode"]:checked')?.value || 'full';
        const remainingMap = {
            UZS: getSelectedDebtInCurrency(opt, 'UZS'),
            USD: getSelectedDebtInCurrency(opt, 'USD'),
        };

        if (mode === 'full') {
            // To'liq yopish serverda BARCHA valyutadagi qarzni yopadi
            if (previewAmount) previewAmount.innerHTML = formatMoneyLinesHTML(remainingMap);
            if (previewRemaining) {
                previewRemaining.textContent = formatMoney(0);
                previewRemaining.className = 'text-success';
            }
            return;
        }

        const currency = getPaymentCurrency();
        const totalDebt = remainingMap[currency];
        const otherCurrency = currency === 'USD' ? 'UZS' : 'USD';
        const otherDebt = remainingMap[otherCurrency];

        // Quick-chips valyutaga moslanadi: so'mda 100k/500k/1M, dollarda 10/50/100
        updateQuickChips(currency);

        const payAmount = Number(partialInput?.value) || 0;
        const remaining = Math.max(0, totalDebt - Math.min(payAmount, totalDebt));
        if (previewAmount) {
            previewAmount.textContent = formatMoney(payAmount, currency);
            previewAmount.className = payAmount > totalDebt ? 'text-danger' : 'text-success';
        }
        if (previewRemaining) {
            const remMap = { [currency]: remaining, [otherCurrency]: otherDebt };
            previewRemaining.innerHTML = formatMoneyLinesHTML(remMap);
            previewRemaining.className = (remaining === 0 && otherDebt === 0) ? 'text-success' : 'text-danger';
        }
    }

    function updateQuickChips(currency) {
        const chips = document.querySelectorAll('#partial-amount-group .btn-chip');
        if (chips.length === 0) return;
        const values = currency === 'USD'
            ? [{ v: 10, label: '10 $' }, { v: 50, label: '50 $' }, { v: 100, label: '100 $' }, { v: 'half', label: '50%' }]
            : [{ v: 100000, label: t('100 ming') }, { v: 500000, label: t('500 ming') }, { v: 1000000, label: t('1 mln') }, { v: 'half', label: '50%' }];
        chips.forEach((chip, i) => {
            chip.setAttribute('data-quick', String(values[i].v));
            chip.textContent = values[i].label;
        });
    }

    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const clientId = Number(select?.value) || 0;
            const mode = document.querySelector('input[name="payment_mode"]:checked')?.value || 'full';
            const currency = getPaymentCurrency();
            const opt = select?.selectedOptions[0];
            const totalDebt = getSelectedDebtInCurrency(opt, currency);
            const payDate = payDateInput?.value.trim() || getTodayFormatted();

            clearFormErrors(form);

            if (!clientId) {
                setFieldError(select, t('Qarzdor mijozni tanlang'));
                return;
            }

            if (!isValidDateString(payDate)) {
                setFieldError(payDateInput, t("To'lov sanasi noto'g'ri. Masalan: 20.08.2026"));
                return;
            }

            let amount = totalDebt;
            if (mode === 'partial') {
                amount = Number(partialInput?.value) || 0;
                if (amount <= 0) {
                    setFieldError(partialInput, t("To'lov summasini kiriting"));
                    return;
                }
                if (totalDebt <= 0) {
                    setFieldError(partialInput, currency === 'USD'
                        ? t("Mijozning dollardagi qarzi yo'q. Boshqa valyutani tanlang")
                        : t("Mijozning so'mdagi qarzi yo'q. Boshqa valyutani tanlang"));
                    return;
                }
                if (amount > totalDebt) {
                    setFieldError(partialInput, t('Summa qarzdan oshmasligi kerak (maksimal: {amount})', { amount: formatMoney(totalDebt, currency) }));
                    return;
                }
            }

            setButtonLoading(submitBtn, true, t('Qabul qilinmoqda…'));

            try {
                const json = await apiJson('/api/payments', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Idempotency-Key': newIdempotencyKey(),
                    },
                    body: JSON.stringify({
                        client_id: clientId,
                        payment_type: mode,
                        amount: amount,
                        currency: currency,
                        payment_date: payDate,
                    })
                });

                hapticSuccess();
                showToast(json.is_closed ? t("To'lov qabul qilindi — qarz to'liq yopildi") : t("To'lov muvaffaqiyatli qabul qilindi"), 'success');

                // Reset payment form
                form?.reset();
                clearFormErrors(form);
                if (payDateInput) payDateInput.value = getTodayFormatted();
                if (infoCard) infoCard.style.display = 'none';
                if (optionsWrapper) optionsWrapper.style.display = 'none';
                if (partialGroup) partialGroup.style.display = 'none';

                // Jadvalga qaytamiz — switchTab ma'lumotlarni o'zi yangilaydi
                switchTab('tab-table');
            } catch (err) {
                notifyError(err);
            } finally {
                setButtonLoading(submitBtn, false);
            }
        });
    }
}

// ==========================================
// TABS & NAVIGATION
// ==========================================

function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(tab => {
        tab.classList.toggle('active', tab.id === tabId);
    });
    document.querySelectorAll('.nav-item').forEach(btn => {
        const isActive = btn.getAttribute('data-tab') === tabId;
        btn.classList.toggle('active', isActive);
        if (isActive) btn.setAttribute('aria-current', 'page');
        else btn.removeAttribute('aria-current');
    });
    // Boshqa tabga o'tilganda tanlash rejimi yopiladi — amal paneli boshqa sahifada qolib ketmasin
    if (tabId !== 'tab-paid' && paidList.isSelecting) paidList.exit();
    if (tabId !== 'tab-trash' && trashList.isSelecting) trashList.exit();
    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (tabId === 'tab-paid') fetchAndRenderPaidDebts();
    if (tabId === 'tab-trash') fetchAndRenderTrash();
    if (tabId === 'tab-table') {
        fetchStats();
        fetchSummaries();
    }
}

// ==========================================
// EVENT LISTENERS INITIALIZATION
// ==========================================

// ==========================================
// SOZLAMALAR: til (bot bilan umumiy) va mavzu
// ==========================================

function readStoredLanguage() {
    try {
        return localStorage.getItem(LANG_STORAGE_KEY);
    } catch (e) {
        return null;
    }
}

// Til serverda saqlanadi (bot bilan umumiy). Shu qurilmadagi tanlov eskirgan
// bo'lsa (masalan, botda o'zgartirilgan) — sahifa yangi tilda qayta yuklanadi.
async function syncLanguageFromServer() {
    let data;
    try {
        data = await apiJson('/api/settings');
    } catch (e) {
        return;
    }
    if (data.language && data.language !== currentLang) {
        setLanguage(data.language);
        // localStorage ishlamasa qayta yuklash cheksiz takrorlanardi
        if (readStoredLanguage() === data.language) location.reload();
    }
}

function setupSettings() {
    document.getElementById('btn-settings')?.addEventListener('click', () => {
        switchTab('tab-settings');
        hapticImpact();
    });

    document.querySelectorAll('input[name="app_language"]').forEach(radio => {
        radio.checked = radio.value === currentLang;
        radio.addEventListener('change', async () => {
            if (!radio.checked || radio.value === currentLang) return;
            hapticImpact();
            try {
                await apiJson('/api/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ language: radio.value }),
                });
            } catch (err) {
                notifyError(err);
                document.querySelector(`input[name="app_language"][value="${currentLang}"]`).checked = true;
                return;
            }
            setLanguage(radio.value);
            location.reload();
        });
    });

    document.querySelectorAll('input[name="app_theme"]').forEach(radio => {
        radio.checked = radio.value === getThemePreference();
        radio.addEventListener('change', () => {
            if (!radio.checked) return;
            try {
                if (radio.value === 'auto') localStorage.removeItem(THEME_STORAGE_KEY);
                else localStorage.setItem(THEME_STORAGE_KEY, radio.value);
            } catch (e) {}
            applyTheme();
            hapticImpact();
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    setLanguage(currentLang);
    translateDom(document.body);

    // Agar Telegram Mini App ichida ochilmagan bo'lsa (URL orqali brauzerdan kirilsa)
    if (!tg || !tg.initData) {
        showUnauthorizedState(t("Ilovadan foydalanish uchun uni Telegram bot orqali oching."));
        return;
    }

    // Refresh Button — barcha tablar ma'lumotini qayta yuklaydi
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.classList.add('rotating');
            hapticImpact();
            refreshBtn.disabled = true;
            const results = await refreshAllData();
            setTimeout(() => {
                refreshBtn.classList.remove('rotating');
                refreshBtn.disabled = false;
            }, 400);
            if (state.gateShown) return;
            if (results.every(Boolean)) {
                showToast(t("Ma'lumotlar yangilandi"), 'success');
            } else {
                hapticError();
                showToast(t("Ba'zi ma'lumotlarni yangilab bo'lmadi. Internet aloqasini tekshiring."), 'error');
            }
        });
    }

    // Tarmoq holati: aloqa uzilsa ogohlantiramiz, tiklansa ma'lumotlar jimgina yangilanadi
    const networkBanner = document.getElementById('network-banner');
    const setOffline = (offline) => {
        if (networkBanner) networkBanner.hidden = !offline;
    };
    window.addEventListener('offline', () => setOffline(true));
    window.addEventListener('online', () => {
        setOffline(false);
        refreshAllData();
    });
    setOffline(navigator.onLine === false);

    // Bo'sh / xato holatlaridagi tugmalar (delegation — kontent dinamik)
    document.addEventListener('click', (e) => {
        const actionBtn = e.target.closest('[data-state-action]');
        if (!actionBtn) return;
        const action = actionBtn.getAttribute('data-state-action');
        hapticImpact();
        if (action === 'retry-summaries') {
            const list = document.getElementById('clients-list');
            if (list) list.innerHTML = skeletonRowsHTML(4);
            fetchStats();
            fetchSummaries();
        } else if (action === 'go-create') {
            switchTab('tab-create');
        } else if (action === 'clear-search') {
            document.getElementById('clear-search-btn')?.click();
        } else if (action === 'retry-paid') {
            fetchAndRenderPaidDebts();
        } else if (action === 'retry-trash') {
            fetchAndRenderTrash();
        }
    });

    // Event delegation on clients list container (Single listener for entire list)
    const clientsListContainer = document.getElementById('clients-list');
    if (clientsListContainer) {
        clientsListContainer.addEventListener('click', (e) => {
            const card = e.target.closest('.client-item-card');
            if (card) {
                const clientId = card.getAttribute('data-client-id');
                if (clientId) openClientReportModal(clientId);
            }
        });
        // Klaviatura: Enter/Space qator bosilishiga teng
        clientsListContainer.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            const card = e.target.closest('.client-item-card');
            if (!card) return;
            e.preventDefault();
            const clientId = card.getAttribute('data-client-id');
            if (clientId) openClientReportModal(clientId);
        });
    }

    // Search Input with Debounce (150ms)
    const searchInput = document.getElementById('table-search-input');
    const clearSearchBtn = document.getElementById('clear-search-btn');
    if (searchInput) {
        const handleSearch = debounce((val) => {
            state.searchQuery = val;
            renderClientsList();
        }, 150);

        searchInput.addEventListener('input', (e) => {
            const val = e.target.value;
            if (clearSearchBtn) clearSearchBtn.style.display = val ? 'grid' : 'none';
            handleSearch(val);
        });
    }
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (searchInput) {
                searchInput.value = '';
                searchInput.focus({ preventScroll: true });
            }
            state.searchQuery = '';
            clearSearchBtn.style.display = 'none';
            renderClientsList();
            hapticImpact();
        });
    }

    // Sort Selector (A-Z, Z-A, Sana, Qarz)
    const sortSelect = document.getElementById('table-sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            state.sort = e.target.value;
            hapticImpact();
            renderClientsList();
        });
    }

    // Filter Chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.chip').forEach(c => {
                c.classList.remove('active');
                c.setAttribute('aria-pressed', 'false');
            });
            chip.classList.add('active');
            chip.setAttribute('aria-pressed', 'true');
            state.filter = chip.getAttribute('data-filter') || 'all';
            renderClientsList();
            hapticImpact();
        });
    });

    // Modal Close
    const modalCloseBtn = document.getElementById('modal-close-btn');
    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeClientReportModal);

    const modalOverlay = document.getElementById('report-modal');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) closeClientReportModal();
        });
    }

    // Modal "Pay Now" Quick Action
    const modalPayBtn = document.getElementById('modal-pay-now-btn');
    if (modalPayBtn) {
        modalPayBtn.addEventListener('click', () => {
            if (!state.selectedClientReport) return;
            const clientId = state.selectedClientReport.client.id;
            closeClientReportModal();
            switchTab('tab-payment');

            // Select this client in dropdown
            const select = document.getElementById('pay-client-select');
            const paySearch = document.getElementById('pay-client-search');
            if (paySearch && paySearch.value) {
                paySearch.value = '';
                populatePaymentClients();
            }
            if (select) {
                select.value = String(clientId);
                select.dispatchEvent(new Event('change'));
                if (!select.value) showToast(t("Bu mijozda to'lanadigan qarz topilmadi"), 'info');
            }
        });
    }

    // Modal "Yana qarz" — hisobotdan to'g'ridan-to'g'ri qarz qo'shish
    const modalAddDebtBtn = document.getElementById('modal-add-debt-btn');
    if (modalAddDebtBtn) {
        modalAddDebtBtn.addEventListener('click', () => {
            if (!state.selectedClientReport) return;
            const client = { ...state.selectedClientReport.client };
            closeClientReportModal();
            startAddDebtForClient(client);
        });
    }

    // Banner × tugmasi — mavjud mijoz tanlovini bekor qilish
    const bannerClearBtn = document.getElementById('banner-clear-btn');
    if (bannerClearBtn) {
        bannerClearBtn.addEventListener('click', () => {
            clearCreateClientBanner();
            hapticImpact();
        });
    }

    // Setup forms
    setupCreateForm();
    setupClientSuggestions();
    setupPaymentForm();
    setupPaidTab();
    setupTrashTab();
    setupSettings();

    // Klaviatura xulq-atvori: input'ga foküs qilinganda (klaviatura ochilganda)
    // pastki navigatsiya bar ekranning o'rtasiga ko'tarilib qolmasligi uchun
    // yashiriladi, foküs ketganda qaytib chiqadi
    const bottomNav = document.querySelector('.bottom-nav');
    // Checkbox/radio/switch klaviatura ochmaydi — faqat matn kiritish maydonlari hisobga olinadi
    const isFormField = (el) => !!el && (
        el.tagName === 'TEXTAREA' ||
        (el.tagName === 'INPUT' && !['checkbox', 'radio', 'button', 'submit'].includes(el.type))
    );
    if (bottomNav) {
        document.addEventListener('focusin', (e) => {
            if (isFormField(e.target)) bottomNav.classList.add('nav-keyboard-hidden');
        });
        document.addEventListener('focusout', () => {
            // Fokus boshqa input'ga o'tgan bo'lishi mumkin — biroz kutib tekshiramiz
            setTimeout(() => {
                if (!isFormField(document.activeElement)) {
                    bottomNav.classList.remove('nav-keyboard-hidden');
                }
            }, 150);
        });
    }

    // Tab switch listener
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            switchTab(tabId);
            hapticImpact();
        });
    });

    initBranches();
    syncLanguageFromServer();

    // Initial Fetch — barcha asosiy ma'lumotlarni birdaniga yuklaymiz
    fetchStats();
    fetchSummaries();
    fetchAndRenderPaidDebts();
    fetchAndRenderTrash();
});

// ==========================================
// UTILITY: TAP / LONG-PRESS (event delegation — ro'yxatga bitta listener)
// ==========================================

function attachListGestures(container, rowSelector, { onTap, onLongPress }) {
    let timer = null;
    let isLong = false;
    let moved = false;
    let startX = 0;
    let startY = 0;
    let activeRow = null;

    const clear = () => {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    };

    container.addEventListener('touchstart', (e) => {
        const row = e.target.closest(rowSelector);
        if (!row || e.target.closest('button, a')) return;
        activeRow = row;
        isLong = false;
        moved = false;
        startX = e.touches[0]?.clientX || 0;
        startY = e.touches[0]?.clientY || 0;
        clear();
        timer = setTimeout(() => {
            if (!moved && activeRow) {
                isLong = true;
                hapticImpact();
                onLongPress(activeRow);
            }
        }, 380);
    }, { passive: true });

    container.addEventListener('touchmove', (e) => {
        if (!activeRow || !e.touches[0]) return;
        if (Math.abs(e.touches[0].clientX - startX) > 8 || Math.abs(e.touches[0].clientY - startY) > 8) {
            moved = true;
            clear();
        }
    }, { passive: true });

    container.addEventListener('touchend', (e) => {
        clear();
        if (activeRow && !moved) {
            // Sintetik "click" (tap va long-press'dan keyin ham) ikkinchi marta ishlamasligi uchun
            if (e.cancelable) e.preventDefault();
            if (!isLong) onTap(activeRow);
        }
        activeRow = null;
    });

    container.addEventListener('touchcancel', () => {
        clear();
        activeRow = null;
    });

    // Sichqoncha (desktop)
    container.addEventListener('click', (e) => {
        const row = e.target.closest(rowSelector);
        if (!row || e.target.closest('button, a')) return;
        onTap(row);
    });

    // Klaviatura: Enter / Space
    container.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const row = e.target.closest(rowSelector);
        if (!row) return;
        e.preventDefault();
        onTap(row);
    });
}

// ==========================================
// COMPONENT: TANLANADIGAN RO'YXAT (Yopilgan / Korzina)
// Ikkala tab bir xil xulq-atvorga ega — yagona komponent, faqat konfiguratsiya farq qiladi.
// ==========================================

function renderDebtRowHTML(item, { isSelected, isSelecting, statusHtml }) {
    const qty = item.product_quantity > 1 ? ` × ${item.product_quantity}` : '';
    return `
        <div class="list-row trash-item ${isSelected ? 'selected' : ''}" data-id="${item.id}"
             role="option" tabindex="0" aria-selected="${isSelecting ? String(isSelected) : 'false'}">
            <input type="checkbox" class="trash-item-checkbox" tabindex="-1" aria-hidden="true" ${isSelected ? 'checked' : ''}>
            <div class="row-main">
                <div class="row-title">${escapeHtml(item.product_name)}${qty}</div>
                <div class="row-meta">
                    <span class="row-meta-item">${icon('user')}<span class="truncate">${escapeHtml(item.client_name)}</span></span>
                    <span class="row-meta-item">${icon('calendar')}<span class="truncate">${escapeHtml(item.debt_date)}</span></span>
                </div>
            </div>
            <div class="row-side">
                <div class="row-amount">${formatMoney(item.original_debt, item.currency)}</div>
                ${statusHtml}
            </div>
        </div>
    `;
}

const SELECTABLE_BATCH = 40;

function createSelectableList(cfg) {
    const st = { items: [], selected: new Set(), isSelecting: false, rendered: 0 };
    const $ = (id) => document.getElementById(id);
    let observer = null;

    function rowHTML(item) {
        return renderDebtRowHTML(item, {
            isSelected: st.selected.has(item.id),
            isSelecting: st.isSelecting,
            statusHtml: cfg.statusHtml,
        });
    }

    // Katta ro'yxatlar bo'laklab chiziladi — DOM kichik, "Barchasini tanlash" tez
    function appendBatch() {
        const container = $(cfg.listId);
        if (!container) return;
        container.querySelector('.list-sentinel')?.remove();
        const next = st.items.slice(st.rendered, st.rendered + SELECTABLE_BATCH);
        if (next.length === 0) return;
        container.insertAdjacentHTML('beforeend', next.map(rowHTML).join(''));
        st.rendered += next.length;
        if (st.rendered < st.items.length) {
            const sentinel = document.createElement('div');
            sentinel.className = 'list-sentinel';
            sentinel.setAttribute('role', 'presentation');
            sentinel.textContent = t('Yuklanmoqda…');
            container.appendChild(sentinel);
            if (!observer) {
                observer = new IntersectionObserver((entries) => {
                    if (entries.some(e => e.isIntersecting)) appendBatch();
                }, { rootMargin: '300px' });
            }
            observer.observe(sentinel);
        }
    }

    function syncRows() {
        const listEl = $(cfg.listId);
        if (!listEl) return;
        listEl.classList.toggle('selection-active', st.isSelecting);
        listEl.setAttribute('aria-multiselectable', 'true');
        listEl.querySelectorAll('.list-row[data-id]').forEach(row => {
            const isSelected = st.selected.has(Number(row.getAttribute('data-id')));
            row.classList.toggle('selected', isSelected);
            row.setAttribute('aria-selected', st.isSelecting ? String(isSelected) : 'false');
            const cb = row.querySelector('.trash-item-checkbox');
            if (cb) cb.checked = isSelected;
        });
    }

    function updateToolbar() {
        const cnt = st.selected.size;
        const countLabel = $(cfg.countLabelId);
        if (countLabel) countLabel.textContent = cnt > 0 ? t('{count} ta tanlandi', { count: cnt }) : t('Yozuvlarni tanlang');
        const actionBtn = $(cfg.actionBtnId);
        if (actionBtn && !actionBtn.dataset.originalHtml) {
            actionBtn.disabled = cnt === 0;
            actionBtn.innerHTML = `${icon(cfg.actionIcon)}${cfg.actionLabel}${cnt > 0 ? ` (${cnt})` : ''}`;
        }
        const allBtn = $(cfg.selectAllBtnId);
        if (allBtn) {
            const allSelected = st.items.length > 0 && cnt === st.items.length;
            allBtn.textContent = allSelected ? t('Hech biri') : t('Barchasi');
        }
    }

    function setBarsVisible(selecting) {
        const normalBar = $(cfg.normalBarId);
        const selectBar = $(cfg.selectBarId);
        const floatingBar = $(cfg.floatingBarId);
        if (normalBar) normalBar.style.display = selecting ? 'none' : 'flex';
        if (selectBar) selectBar.style.display = selecting ? 'flex' : 'none';
        if (floatingBar) floatingBar.style.display = selecting ? 'block' : 'none';
    }

    function enter(initialId = null) {
        st.isSelecting = true;
        if (initialId !== null && initialId !== undefined) st.selected.add(initialId);
        setBarsVisible(true);
        syncRows();
        updateToolbar();
    }

    function exit() {
        st.isSelecting = false;
        st.selected.clear();
        setBarsVisible(false);
        syncRows();
        updateToolbar();
    }

    function toggle(id) {
        if (st.selected.has(id)) st.selected.delete(id);
        else st.selected.add(id);
        syncRows();
        updateToolbar();
        hapticImpact();
    }

    function toggleAll() {
        if (st.items.length > 0 && st.selected.size === st.items.length) {
            st.selected.clear();
        } else {
            st.items.forEach(i => st.selected.add(i.id));
        }
        syncRows();
        updateToolbar();
        hapticImpact();
    }

    function render() {
        const container = $(cfg.listId);
        if (!container) return;
        const badge = $(cfg.badgeId);
        if (badge) badge.textContent = formatCount(st.items.length);
        $(cfg.enterBtnId)?.toggleAttribute('disabled', st.items.length === 0);

        if (st.items.length === 0) {
            container.removeAttribute('role');
            container.innerHTML = stateBlockHTML(cfg.emptyState);
            cfg.onRender?.(st.items);
            exit();
            return;
        }

        container.setAttribute('role', 'listbox');
        container.setAttribute('aria-label', cfg.listLabel);
        container.innerHTML = '';
        st.rendered = 0;
        appendBatch();
        syncRows();
        cfg.onRender?.(st.items);
    }

    async function load() {
        const container = $(cfg.listId);
        if (!container) return false;
        if (!st.items.length) container.innerHTML = skeletonRowsHTML(2);
        try {
            st.items = await apiJson(`${cfg.endpoint}?limit=${LIST_LIMIT}`);
            // Yangilangan ro'yxatda mavjud bo'lmagan tanlovlar tashlanadi
            const ids = new Set(st.items.map(i => i.id));
            [...st.selected].forEach(id => { if (!ids.has(id)) st.selected.delete(id); });
            render();
            updateToolbar();
            return true;
        } catch (err) {
            console.error(`Error fetching ${cfg.endpoint}:`, err);
            if (err.handled) return false;
            container.removeAttribute('role');
            container.innerHTML = stateBlockHTML({
                iconName: 'alert-triangle',
                title: cfg.errorTitle,
                desc: err.message,
                action: { id: `retry-${cfg.key}`, label: t('Qayta urinish') },
                isError: true,
            });
            cfg.onError?.();
            return false;
        }
    }

    async function runAction() {
        const actionBtn = $(cfg.actionBtnId);
        const ids = [...st.selected];
        if (ids.length === 0 || !actionBtn) return;
        setButtonLoading(actionBtn, true, cfg.actionLoadingLabel);
        try {
            const json = await apiJson(cfg.actionEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ debt_ids: ids }),
            });
            hapticSuccess();
            showToast(cfg.successMessage(json, ids.length), 'success');
            setButtonLoading(actionBtn, false);
            exit();
            await refreshAllData();
        } catch (err) {
            notifyError(err);
            setButtonLoading(actionBtn, false);
            updateToolbar();
        }
    }

    function setup() {
        $(cfg.enterBtnId)?.addEventListener('click', () => {
            enter();
            hapticImpact();
            $(cfg.listId)?.querySelector('.list-row')?.focus({ preventScroll: true });
        });
        $(cfg.cancelBtnId)?.addEventListener('click', () => {
            exit();
            hapticImpact();
        });
        $(cfg.selectAllBtnId)?.addEventListener('click', toggleAll);
        $(cfg.actionBtnId)?.addEventListener('click', runAction);

        const listEl = $(cfg.listId);
        if (listEl) {
            // Qator bosilganda: tanlash rejimida — belgilash, aks holda — shu qator bilan tanlashni boshlash
            const handle = (row) => {
                const id = Number(row.getAttribute('data-id'));
                if (st.isSelecting) toggle(id);
                else {
                    enter(id);
                    hapticImpact();
                }
            };
            attachListGestures(listEl, '.list-row[data-id]', { onTap: handle, onLongPress: handle });
        }
    }

    return {
        state: st,
        enter,
        exit,
        load,
        setup,
        get isSelecting() { return st.isSelecting; },
    };
}

const paidList = createSelectableList({
    key: 'paid',
    listId: 'paid-debts-list',
    listLabel: t('Yopilgan qarzlar'),
    endpoint: '/api/paid-debts',
    actionEndpoint: '/api/trash/move',
    normalBarId: 'paid-normal-bar',
    selectBarId: 'paid-select-bar',
    floatingBarId: 'paid-floating-action-bar',
    badgeId: 'paid-total-badge',
    countLabelId: 'paid-selected-count-label',
    selectAllBtnId: 'btn-paid-select-all-toggle',
    enterBtnId: 'btn-paid-enter-select',
    cancelBtnId: 'btn-paid-cancel-select',
    actionBtnId: 'btn-move-to-trash',
    actionIcon: 'trash',
    actionLabel: t('Korzinaga yuborish'),
    actionLoadingLabel: t('Yuborilmoqda…'),
    statusHtml: `<span class="badge badge-success">${t('Yopilgan')}</span>`,
    errorTitle: t("Yopilgan qarzlarni yuklab bo'lmadi"),
    emptyState: {
        iconName: 'check-circle',
        title: t("Yopilgan qarzlar yo'q"),
        desc: t("To'liq to'langan qarzlar shu yerda ko'rinadi."),
    },
    successMessage: (json, n) => t('{count} ta yozuv korzinaga yuborildi', { count: json.moved ?? n }),
});

const trashList = createSelectableList({
    key: 'trash',
    listId: 'trash-list',
    listLabel: t('Korzinadagi yozuvlar'),
    endpoint: '/api/trash',
    actionEndpoint: '/api/trash/restore',
    normalBarId: 'trash-normal-bar',
    selectBarId: 'trash-select-bar',
    floatingBarId: 'trash-floating-action-bar',
    badgeId: 'trash-total-badge',
    countLabelId: 'trash-selected-count-label',
    selectAllBtnId: 'btn-trash-select-all-toggle',
    enterBtnId: 'btn-trash-enter-select',
    cancelBtnId: 'btn-trash-cancel-select',
    actionBtnId: 'btn-restore-from-trash',
    actionIcon: 'restore',
    actionLabel: t('Yopilganlarga qaytarish'),
    actionLoadingLabel: t('Qaytarilmoqda…'),
    statusHtml: `<span class="badge badge-neutral">${t('Korzinada')}</span>`,
    errorTitle: t("Korzinani yuklab bo'lmadi"),
    emptyState: {
        iconName: 'trash',
        title: t("Korzina bo'sh"),
        desc: t("Yopilgan bo'limidan yuborilgan yozuvlar shu yerda saqlanadi."),
    },
    successMessage: (json, n) => t('{count} ta yozuv yopilganlarga qaytarildi', { count: json.restored ?? n }),
    // Korzina bo'sh yoki yuklanmagan bo'lsa, tozalash paneli ko'rinmaydi
    onRender: (items) => {
        const bar = document.getElementById('trash-purge-bar');
        if (!bar) return;
        bar.style.display = items.length ? 'flex' : 'none';
        if (items.length) hidePurgeConfirm();
    },
    onError: () => {
        const bar = document.getElementById('trash-purge-bar');
        if (bar) bar.style.display = 'none';
    },
});

// Mavjud nomlar saqlanadi — boshqa joylardan chaqiriladi
function fetchAndRenderPaidDebts() {
    return paidList.load();
}

function fetchAndRenderTrash() {
    return trashList.load();
}

function setupPaidTab() {
    paidList.setup();
}

// Filial almashganda avvalgi filial ma'lumoti ekranda qolib ketmasligi uchun
// barcha ro'yxat va qidiruv holati tozalanib, qayta yuklanadi.
function resetForBranchChange() {
    state.summaries = [];
    state.filteredList = [];
    state.renderedCount = 0;
    state.summariesLoaded = false;
    state.selectedClientReport = null;
    state.searchQuery = '';
    const search = document.getElementById('table-search-input');
    if (search) search.value = '';
    if (paidList.isSelecting) paidList.exit();
    if (trashList.isSelecting) trashList.exit();
    const list = document.getElementById('clients-list');
    if (list) list.innerHTML = skeletonRowsHTML(4);
}

function renderBranchSwitch(branches) {
    const box = document.getElementById('branch-switch');
    if (!box) return;
    box.innerHTML = branches.map(b => `
        <button type="button" class="branch-chip${b.code === currentBranch ? ' active' : ''}"
                data-branch="${escapeHtml(b.code)}" aria-pressed="${b.code === currentBranch}">
            ${escapeHtml(b.title)}
        </button>`).join('');
    box.hidden = branches.length < 2;
}

async function initBranches() {
    let info;
    try {
        info = await apiJson('/api/branches');
    } catch (err) {
        return;
    }
    const branches = info.branches || [];
    if (!branches.length) return;
    // Saqlangan filial endi mavjud bo'lmasa — asosiy filialga qaytamiz.
    if (!branches.some(b => b.code === currentBranch)) {
        setCurrentBranch(info.default || branches[0].code);
        resetForBranchChange();
        refreshAllData();
    }
    renderBranchSwitch(branches);
    document.getElementById('branch-switch')?.addEventListener('click', (e) => {
        const chip = e.target.closest('[data-branch]');
        if (!chip || chip.dataset.branch === currentBranch) return;
        hapticImpact();
        setCurrentBranch(chip.dataset.branch);
        renderBranchSwitch(branches);
        resetForBranchChange();
        refreshAllData();
    });
}

// Yozuv amallaridan keyin barcha ko'rinishlar bir vaqtda yangilanadi
function refreshAllData() {
    return Promise.all([
        fetchStats(),
        fetchSummaries(),
        fetchAndRenderPaidDebts(),
        fetchAndRenderTrash(),
    ]);
}

// Korzinani tozalash uchun inline confirm paneli
function showPurgeConfirm() {
    const bar = document.getElementById('trash-purge-bar');
    if (!bar) return;
    hapticImpact();
    bar.innerHTML = `
        <div class="danger-zone-texts" role="alert">
            <span class="danger-zone-title">${t("{count} ta yozuv butunlay o'chirilsinmi?", { count: trashList.state.items.length })}</span>
            <span class="purge-bar-text">${t("Bu amalni ortga qaytarib bo'lmaydi.")}</span>
        </div>
        <div class="danger-zone-actions">
            <button id="btn-purge-cancel" class="btn btn-secondary btn-sm" type="button">${t('Bekor qilish')}</button>
            <button id="btn-purge-confirm" class="btn btn-danger btn-sm" type="button">${t("Ha, o'chirish")}</button>
        </div>
    `;
    document.getElementById('btn-purge-cancel')?.addEventListener('click', hidePurgeConfirm);
    document.getElementById('btn-purge-confirm')?.addEventListener('click', executePurge);
    document.getElementById('btn-purge-cancel')?.focus({ preventScroll: true });
}

function hidePurgeConfirm() {
    const bar = document.getElementById('trash-purge-bar');
    if (!bar) return;
    bar.innerHTML = `
        <div class="danger-zone-texts">
            <span class="danger-zone-title">${t('Korzinani tozalash')}</span>
            <span class="purge-bar-text">${t("Barcha yozuvlar butunlay o'chiriladi. Bu amalni ortga qaytarib bo'lmaydi.")}</span>
        </div>
        <button id="btn-purge-trash" class="btn btn-danger-outline btn-sm" type="button">${icon('trash')} ${t('Tozalash')}</button>
    `;
    document.getElementById('btn-purge-trash')?.addEventListener('click', showPurgeConfirm);
}

async function executePurge() {
    const confirmBtn = document.getElementById('btn-purge-confirm');
    const cancelBtn = document.getElementById('btn-purge-cancel');
    setButtonLoading(confirmBtn, true, t("O'chirilmoqda…"));
    if (cancelBtn) cancelBtn.disabled = true;
    try {
        const json = await apiJson('/api/trash/purge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        hapticSuccess();
        showToast(t("{count} ta yozuv butunlay o'chirildi", { count: json.deleted }), 'success');
        hidePurgeConfirm();
        trashList.exit();
        await refreshAllData();
    } catch (err) {
        notifyError(err);
        hidePurgeConfirm();
    }
}

function setupTrashTab() {
    trashList.setup();
    // Purge tugmasi — inline confirm orqali
    document.getElementById('btn-purge-trash')?.addEventListener('click', showPurgeConfirm);
}
