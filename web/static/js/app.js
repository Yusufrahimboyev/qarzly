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

// Mavzu Telegram sozlamasiga moslanadi (tizim sozlamasi bilan farq qilishi mumkin)
function applyTheme() {
    const scheme = tg?.colorScheme;
    if (scheme === 'dark' || scheme === 'light') {
        document.documentElement.setAttribute('data-theme', scheme);
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
};

// Utilities
function formatMoney(amount, currency = 'UZS') {
    const num = Math.round(Number(amount) || 0);
    const formatted = num.toLocaleString('ru-RU').replace(/,/g, ' ');
    return currency === 'USD' ? `${formatted} $` : `${formatted} so'm`;
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
    return `<svg class="icon ${extraClass}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
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

function showUnauthorizedState(message = "Ushbu tizimga faqat ruxsat berilgan Telegram foydalanuvchilari kira oladi.") {
    const app = document.getElementById('app') || document.body;
    document.querySelector('.bottom-nav')?.remove();
    app.innerHTML = `
        <div class="gate">
            <div class="card gate-card" role="alert">
                <div class="gate-icon">${icon('lock')}</div>
                <h2 class="gate-title">Kirish cheklangan</h2>
                <p class="gate-text">${escapeHtml(message)}</p>
                <div class="gate-hint">Ilovani vakolatli Telegram akkauntingizdagi bot orqali oching.</div>
            </div>
        </div>
    `;
}

// Har bir yozuv so'rovi uchun bir martalik kalit: tarmoq retry'i yoki
// tugmani ikki marta bosish dublikat qarz/to'lov yaratmasligi kerak.
function newIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
}

// Barcha API so'rovlarini Telegram initData imzosi bilan yuboradi.
// Server imzoni tekshiradi — begona shaxs URLni bilsa ham ma'lumot ololmaydi.
async function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (tg && tg.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }
    const res = await fetch(url, { ...options, headers });
    if (res.status === 429) {
        showToast("So'rovlar juda tez yuborildi. Biroz kutib, qayta urinib ko'ring.", 'error');
    } else if (res.status === 401) {
        showUnauthorizedState("Ruxsat berilmagan. Ilovani Telegram boti ichida oching.");
    } else if (res.status === 403) {
        showUnauthorizedState("Sizning Telegram akkauntingizga ushbu tizimdan foydalanish huquqi berilmagan.");
    } else if (res.status === 502 || res.status === 503) {
        showToast("Server yangilanmoqda. 10–20 soniyadan so'ng qayta urinib ko'ring.", 'error');
    }
    return res;
}

// ==========================================
// API REQUESTS
// ==========================================

async function fetchStats() {
    try {
        const res = await apiFetch('/api/stats');
        if (res.status === 401 || res.status === 403) return;
        if (!res.ok) return;
        const data = await res.json();
        const totalEl = document.getElementById('stat-total-debt');
        totalEl.classList.remove('is-loading');
        totalEl.innerHTML = formatMoneyLinesHTML(data.total_debt);
        document.getElementById('stat-debtors-count').textContent = `${data.debtors_count} ta`;
        document.getElementById('stat-clients-count').textContent = `${data.clients_count} ta`;
    } catch (err) {
        console.error('Error fetching stats:', err);
    }
}

// Server ro'yxatlarni sahifalab beradi (default 200) — UI barcha yozuvlarni oladi
const LIST_LIMIT = 1000;

async function fetchSummaries() {
    const container = document.getElementById('clients-list');
    try {
        const res = await apiFetch(`/api/summaries?limit=${LIST_LIMIT}`);
        if (res.status === 401 || res.status === 403) {
            showUnauthorizedState();
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        state.summaries = await res.json();
        state.summariesLoaded = true;
        updateFilterCounts();
        renderClientsList();
        populatePaymentClients();
    } catch (err) {
        console.error('Error fetching summaries:', err);
        // Avval yuklangan ro'yxat bo'lsa, uni saqlab qolamiz — faqat xabar beramiz
        if (state.summariesLoaded) {
            showToast("Ro'yxatni yangilab bo'lmadi. Internet aloqasini tekshiring.", 'error');
            return;
        }
        if (container) {
            container.removeAttribute('aria-busy');
            container.innerHTML = stateBlockHTML({
                iconName: 'alert-triangle',
                title: "Ma'lumotlarni yuklab bo'lmadi",
                desc: "Internet aloqasini tekshiring va qayta urinib ko'ring.",
                action: { id: 'retry-summaries', label: 'Qayta urinish' },
                isError: true,
            });
        }
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
        const res = await apiFetch(`/api/clients/${clientId}/report`);
        if (res.status === 401 || res.status === 403) {
            showToast('Ma\'lumotlarni ko\'rish uchun Telegram ichida oching');
            return null;
        }
        if (!res.ok) throw new Error('Hisobot topilmadi');
        return await res.json();
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

function getProcessedList() {
    let list = [...state.summaries];

    // 1. Filter Chips
    if (state.filter === 'debtors') {
        list = list.filter(item => item.has_debt);
    } else if (state.filter === 'paid') {
        list = list.filter(item => !item.has_debt);
    }

    // 2. Search Query
    if (state.searchQuery.trim()) {
        const q = state.searchQuery.toLowerCase().trim();
        list = list.filter(item =>
            (item.full_name && item.full_name.toLowerCase().includes(q)) ||
            (item.phone && item.phone.toLowerCase().includes(q))
        );
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
        ? `<span class="row-meta-item">${icon('phone')}${escapeHtml(item.phone)}</span>`
        : '<span class="row-meta-item">Telefon kiritilmagan</span>';
    const dateHtml = item.latest_debt_date
        ? `<span class="row-meta-item">${icon('calendar')}${escapeHtml(item.latest_debt_date)}</span>`
        : '';
    const amountHtml = item.has_debt
        ? `<div class="row-amount client-debt-amount is-debt">${formatMoneyLinesHTML(item.remaining)}</div>`
        : '';
    const badgeHtml = item.has_debt
        ? '<span class="badge badge-danger">Qarzdor</span>'
        : '<span class="badge badge-success">Yopilgan</span>';
    const ariaLabel = `${item.full_name}. ${item.has_debt ? `Qarzi: ${formatMoneyMap(item.remaining)}` : 'Qarzi yo\'q'}. Hisobotni ochish`;
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
    el.textContent = shown === total ? `${total} ta mijoz` : `${shown} / ${total} ta mijoz`;
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
                title: "Hali mijozlar yo'q",
                desc: "Birinchi qarz yozuvini yarating — mijoz avtomatik qo'shiladi.",
                action: { id: 'go-create', label: "Yangi qarz qo'shish" },
            });
        } else if (state.searchQuery.trim()) {
            container.innerHTML = stateBlockHTML({
                iconName: 'search',
                title: 'Hech narsa topilmadi',
                desc: `"${state.searchQuery.trim()}" bo'yicha mijoz topilmadi. Ism yoki raqamni tekshiring.`,
                action: { id: 'clear-search', label: 'Qidiruvni tozalash' },
            });
        } else {
            container.innerHTML = stateBlockHTML({
                iconName: 'inbox',
                title: state.filter === 'debtors' ? "Qarzdor mijozlar yo'q" : "Qarzi yopilgan mijozlar yo'q",
                desc: state.filter === 'debtors' ? "Barcha mijozlarning qarzi yopilgan." : '',
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
        sentinel.textContent = 'Yuklanmoqda…';
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

    const nameInput = document.getElementById('create-client-name');
    const phoneInput = document.getElementById('create-client-phone');
    if (nameInput && person.full_name) nameInput.value = person.full_name;
    if (phoneInput && person.phone) phoneInput.value = person.phone;

    const banner = document.getElementById('create-client-banner');
    if (banner) {
        document.getElementById('banner-client-name').textContent = person.full_name || '-';
        document.getElementById('banner-client-phone').textContent = person.phone || 'Telefon kiritilmagan';
        banner.style.display = 'flex';
        // Ism/telefon allaqachon ma'lum — takroriy maydonlar yashiriladi
        document.getElementById('create-debt-form')?.classList.add('has-selected-client');
        clearFormErrors(document.getElementById('create-debt-form'));
    }

    // Sana har doim bugunga tenglanadi — keyingi qarz to'g'ri sanada yoziladi
    const dateInput = document.getElementById('create-date');
    if (dateInput) dateInput.value = getTodayFormatted();

    // Mijozning eski qarzlarini ko'rsatamiz
    loadExistingDebts(person.id);

    // Avto-foküs yo'q — aks holda klaviatura darrov ochilib,
    // pastki navigatsiya bar tepaga ko'tarilib qoladi
}

// Mijozning joriy (yopilmagan) qarzlarini yuklab banner ostida ko'rsatadi
async function loadExistingDebts(clientId) {
    const card = document.getElementById('banner-debts-card');
    const listEl = document.getElementById('banner-debts-list');
    const totalEl = document.getElementById('banner-client-debt');
    if (!card || !listEl || !clientId) return;

    card.style.display = 'block';
    totalEl.textContent = '…';
    listEl.innerHTML = '<div class="banner-debt-loading">Yuklanmoqda…</div>';

    const data = await fetchClientReport(clientId);
    if (!data) {
        card.style.display = 'none';
        return;
    }

    const remaining = data.total_remaining_debt || {};
    const hasDebt = Object.values(remaining).some(v => (Number(v) || 0) > 0);
    totalEl.textContent = hasDebt ? formatMoneyMap(remaining) : "Qarz yo'q";
    totalEl.className = hasDebt ? 'text-danger' : 'text-success';

    const activeDebts = (data.debts || []).filter(d => d.status === 'active');
    if (activeDebts.length === 0) {
        listEl.innerHTML = '<div class="banner-no-debt">Yopilmagan qarzi yo&#8217;q</div>';
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
        : '<span class="badge badge-success">Yopilgan</span>';

    return `
        <div class="history-card">
            <div class="history-card-header">
                <span>${escapeHtml(d.product_name)}${d.product_quantity > 1 ? ` × ${d.product_quantity}` : ''}</span>
                ${statusHtml}
            </div>
            ${productListHtml}
            <div class="history-card-detail">
                <span class="row-meta-item">${icon('calendar')}${escapeHtml(d.debt_date)}</span>
                <span>Narxi: ${formatMoney(d.product_price, d.currency)}</span>
            </div>
            ${d.exchange_exists ? `
            <div class="history-card-detail is-exchange">
                <span>Exchange: ${escapeHtml(d.exchange_product_name || 'Tovar')}</span>
                <span>−${formatMoney(d.exchange_product_price, d.currency)}</span>
            </div>` : ''}
            ${d.given_money > 0 ? `
            <div class="history-card-detail is-given">
                <span>Boshlang'ich to'lov</span>
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
        document.getElementById('modal-client-phone').textContent = cached.phone || 'Telefon kiritilmagan';
        remainingEl.textContent = cached.has_debt ? formatMoneyMap(cached.remaining) : "Qarz yo'q";
    } else {
        document.getElementById('modal-client-name').textContent = 'Mijoz hisoboti';
        document.getElementById('modal-client-phone').textContent = 'Yuklanmoqda…';
        remainingEl.textContent = '…';
    }
    document.getElementById('modal-total-products').textContent = '…';
    document.getElementById('modal-total-paid').textContent = '…';

    const debtsList = document.getElementById('modal-debts-list');
    const paymentsList = document.getElementById('modal-payments-list');
    if (debtsList) debtsList.innerHTML = '<div class="history-loading">Tarix yuklanmoqda…</div>';
    if (paymentsList) paymentsList.innerHTML = '<div class="history-loading">Yuklanmoqda…</div>';

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
        if (debtsList) debtsList.innerHTML = historyEmptyHTML("Hisobotni yuklab bo'lmadi");
        if (paymentsList) paymentsList.innerHTML = historyEmptyHTML('—');
        showToast("Mijoz ma'lumotlarini yuklab bo'lmadi", 'error');
        return;
    }

    state.selectedClientReport = data;

    document.getElementById('modal-client-name').textContent = data.client.full_name;
    document.getElementById('modal-client-phone').textContent = data.client.phone || 'Telefon kiritilmagan';
    document.getElementById('modal-total-products').innerHTML = formatMoneyLinesHTML(data.total_product_price);
    document.getElementById('modal-total-paid').innerHTML = formatMoneyLinesHTML(sumMaps(data.total_paid_after, data.total_given_money));

    const remainingValues = Object.values(data.total_remaining_debt || {});
    const hasAnyDebt = remainingValues.some(v => (Number(v) || 0) > 0);
    remainingEl.textContent = hasAnyDebt ? formatMoneyMap(data.total_remaining_debt) : "Qarz yo'q";
    remainingEl.classList.toggle('text-danger', hasAnyDebt);
    remainingEl.classList.toggle('text-success', !hasAnyDebt);
    remainingEl.closest('.modal-kpi')?.classList.toggle('modal-kpi-primary', hasAnyDebt);

    // Qarzlar tarixi — ko'p tovarli bo'lsa har bir tovar alohida ko'rsatiladi
    debtsList.innerHTML = data.debts.length === 0
        ? historyEmptyHTML('Qarzlar mavjud emas')
        : data.debts.map(renderDebtHistoryCard).join('');

    // To'lovlar tarixi
    const actualPayments = data.payments.filter(p => p.payment_type !== 'initial');
    paymentsList.innerHTML = actualPayments.length === 0
        ? historyEmptyHTML("To'lovlar mavjud emas")
        : actualPayments.map(p => `
            <div class="history-card">
                <div class="history-card-header">
                    <span class="history-amount text-success">+${formatMoney(p.amount, p.currency)}</span>
                    <span class="badge badge-neutral">${p.payment_type === 'full' ? "To'liq" : 'Qisman'}</span>
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

function createProductGroupHTML(index) {
    const removeBtn = index > 0
        ? `<button type="button" class="btn-remove-product" aria-label="${index + 1}-tovarni o'chirish">${icon('trash')}O'chirish</button>`
        : '';
    return `
        <div class="product-group" data-product-index="${index}">
            <div class="product-group-header">
                <span class="product-group-title">${index + 1}-tovar</span>
                ${removeBtn}
            </div>
            <div class="form-group">
                <label>Tovar nomi <span class="req" aria-hidden="true">*</span></label>
                <input type="text" class="product-name" placeholder="Masalan: Shina, Akkumulyator" autocomplete="off" required>
            </div>
            <div class="product-row">
                <div class="form-group">
                    <label>Soni</label>
                    <input type="number" class="product-qty" placeholder="1" min="1" step="1" value="1" inputmode="numeric" required>
                </div>
                <div class="form-group">
                    <label>Narxi (1 dona) <span class="req" aria-hidden="true">*</span></label>
                    <input type="number" class="product-price" placeholder="0" min="1" step="1000" inputmode="numeric" required>
                </div>
            </div>
            <div class="product-footer">
                <div class="currency-chips" role="group" aria-label="Valyuta">
                    <button type="button" class="cur-chip active" data-currency="UZS" aria-pressed="true">So'm</button>
                    <button type="button" class="cur-chip" data-currency="USD" aria-pressed="false">Dollar</button>
                </div>
                <div class="product-subtotal">
                    <span>Jami</span>
                    <strong class="product-subtotal-val">0 so'm</strong>
                </div>
            </div>
        </div>
    `;
}

function getProductGroups() {
    return document.querySelectorAll('#products-container .product-group');
}

function getGroupCurrency(group) {
    const active = group.querySelector('.cur-chip.active');
    return active ? active.getAttribute('data-currency') : 'UZS';
}

function renumberProductGroups() {
    const groups = getProductGroups();
    groups.forEach((group, i) => {
        const title = group.querySelector('.product-group-title');
        if (title) title.textContent = `${i + 1}-tovar`;
        group.querySelector('.btn-remove-product')?.setAttribute('aria-label', `${i + 1}-tovarni o'chirish`);
        group.setAttribute('data-product-index', i);
    });
}

function getProductsData() {
    const groups = getProductGroups();
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

    // Har bir guruhning subtotal'ini o'z valyutasida yangilaymiz
    const groups = getProductGroups();
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
    const exchangePriceInput = document.getElementById('create-exchange-price');
    const givenToggle = document.getElementById('create-given-toggle');
    const givenAmountInput = document.getElementById('create-given-amount');

    const hasExchange = exchangeToggle?.checked;
    const exchangeCurrency = getChipsCurrency('exchange-currency-chips');
    const exchangePrice = hasExchange ? (Number(exchangePriceInput?.value) || 0) : 0;
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
        document.getElementById('calc-exchange-price').textContent = `-${formatMoney(exchangePrice, exchangeCurrency)}`;
    }

    const givenRow = document.getElementById('calc-given-row');
    if (givenRow) {
        givenRow.style.display = hasGiven ? 'flex' : 'none';
        document.getElementById('calc-given-price').textContent = `-${formatMoney(givenAmount, givenCurrency)}`;
    }

    // Har bir valyutada alohida hisoblab, jami qarzni yig'amiz
    const remaining = { ...totals };
    if (hasExchange && exchangePrice > 0) {
        remaining[exchangeCurrency] = Math.max(0, (remaining[exchangeCurrency] || 0) - exchangePrice);
    }
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
                group.remove();
                renumberProductGroups();
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
    const exchangePriceInput = document.getElementById('create-exchange-price');
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

    // "Yana tovar qo'shish" tugmasi
    if (btnAddProduct) {
        btnAddProduct.addEventListener('click', () => {
            const groups = getProductGroups();
            const newIndex = groups.length;
            const html = createProductGroupHTML(newIndex);
            const wrapper = document.createElement('div');
            wrapper.innerHTML = html;
            const newGroup = wrapper.firstElementChild;
            container.appendChild(newGroup);
            attachProductGroupListeners(newGroup);
            updateCreateCalculation();
            hapticImpact();

            // Yangi tovar kartini ko'rinadigan joyga silliq suramiz —
            // fokus qo'ymaymiz, klaviatura o'z-o'zidan ochilib yuborilmaydi
            setTimeout(() => {
                newGroup.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 50);
        });
    }

    // Toggle Exchange
    if (exchangeToggle) {
        exchangeToggle.addEventListener('change', () => {
            exchangeFields.style.display = exchangeToggle.checked ? 'block' : 'none';
            if (!exchangeToggle.checked && exchangePriceInput) exchangePriceInput.value = '';
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

    // Exchange/given valyuta chipslari va input'lari
    attachChipsListeners(document.getElementById('exchange-currency-chips') || document.createElement('div'));
    attachChipsListeners(document.getElementById('given-currency-chips') || document.createElement('div'));
    [exchangePriceInput, givenAmountInput].forEach(el => {
        if (el) el.addEventListener('input', () => {
            clearFieldError(el);
            updateCreateCalculation();
        });
    });

    // Submit New Debt
    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const clientName = document.getElementById('create-client-name')?.value.trim();
            const clientPhone = document.getElementById('create-client-phone')?.value.trim();
            const debtDate = dateInput?.value.trim() || getTodayFormatted();

            const products = getProductsData();

            const hasExchange = exchangeToggle?.checked || false;
            const exchangeName = document.getElementById('create-exchange-name')?.value.trim() || null;
            const exchangeCurrency = getChipsCurrency('exchange-currency-chips');
            const exchangePrice = hasExchange ? (Number(exchangePriceInput?.value) || 0) : 0;

            const hasGiven = givenToggle?.checked || false;
            const givenCurrency = getChipsCurrency('given-currency-chips');
            const givenMoney = hasGiven ? (Number(givenAmountInput?.value) || 0) : 0;

            clearFormErrors(form);
            const hasSelectedClient = form?.classList.contains('has-selected-client');

            if (!clientName) {
                if (hasSelectedClient) clearCreateClientBanner();
                setFieldError(nameInput, 'Mijozning ism-familiyasini kiriting');
                return;
            }
            if (clientPhone) {
                const phoneDigits = clientPhone.replace(/\D/g, '');
                if (phoneDigits.length < 7 || phoneDigits.length > 15) {
                    setFieldError(phoneInput, "Telefon raqami noto'g'ri. Masalan: +998901234567");
                    return;
                }
            }
            if (!isValidDateString(debtDate)) {
                setFieldError(dateInput, "Sana noto'g'ri. KK.OO.YYYY ko'rinishida kiriting, masalan: 16.08.2026");
                return;
            }

            // Har bir tovar kartasini tekshiramiz: yarim to'ldirilgan kartani o'tkazib yubormaymiz
            const groups = [...getProductGroups()];
            for (let i = 0; i < groups.length; i++) {
                const nameEl = groups[i].querySelector('.product-name');
                const priceEl = groups[i].querySelector('.product-price');
                const hasName = !!nameEl?.value.trim();
                const hasPrice = (Number(priceEl?.value) || 0) > 0;
                if (hasName && !hasPrice) {
                    setFieldError(priceEl, `${i + 1}-tovar narxini kiriting`);
                    return;
                }
                if (!hasName && hasPrice) {
                    setFieldError(nameEl, `${i + 1}-tovar nomini kiriting`);
                    return;
                }
            }
            if (products.length === 0) {
                const firstName = groups[0]?.querySelector('.product-name');
                setFieldError(firstName, 'Kamida bitta tovar nomi va narxini kiriting');
                return;
            }

            // Har bir valyutada chegirmalar tovarlar jami narxidan oshmasligi kerak
            const totals = {};
            products.forEach(p => {
                totals[p.currency] = (totals[p.currency] || 0) + p.quantity * p.price_per_unit;
            });
            const deductions = {};
            if (hasExchange && exchangePrice > 0) {
                deductions[exchangeCurrency] = (deductions[exchangeCurrency] || 0) + exchangePrice;
            }
            if (hasGiven && givenMoney > 0) {
                deductions[givenCurrency] = (deductions[givenCurrency] || 0) + givenMoney;
            }
            for (const cur of Object.keys(deductions)) {
                if ((deductions[cur] || 0) > (totals[cur] || 0)) {
                    const curLabel = cur === 'USD' ? 'dollar' : "so'm";
                    const target = (hasGiven && givenCurrency === cur) ? givenAmountInput : exchangePriceInput;
                    setFieldError(target, `Exchange va boshlang'ich to'lov ${curLabel}dagi tovarlar narxidan oshmasligi kerak`);
                    return;
                }
            }

            setButtonLoading(submitBtn, true, 'Saqlanmoqda…');

            try {
                const payload = {
                    client_name: clientName,
                    client_phone: clientPhone,
                    debt_date: debtDate,
                    products: products,
                    exchange_exists: hasExchange,
                    exchange_product_name: exchangeName,
                    exchange_product_price: exchangePrice,
                    exchange_currency: exchangeCurrency,
                    given_money: givenMoney,
                    given_currency: givenCurrency,
                };

                const res = await apiFetch('/api/debts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Idempotency-Key': newIdempotencyKey(),
                    },
                    body: JSON.stringify(payload),
                });

                const json = await res.json();
                if (!res.ok || json.error) {
                    throw new Error(json.error || 'Qarzni saqlashda xatolik');
                }

                hapticSuccess();
                const remainingText = json.remaining_by_currency ? formatMoneyMap(json.remaining_by_currency) : '';
                showToast(remainingText
                    ? `Qarz saqlandi: ${clientName} — ${remainingText}`
                    : 'Qarz muvaffaqiyatli saqlandi', 'success');

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
                if (givenToggle) givenToggle.checked = false;
                // Valyuta chipslarini UZSga qaytaramiz
                document.querySelectorAll('#exchange-currency-chips .cur-chip, #given-currency-chips .cur-chip').forEach(chip => {
                    chip.classList.toggle('active', chip.getAttribute('data-currency') === 'UZS');
                });
                document.querySelectorAll('#exchange-currency-chips .cur-chip, #given-currency-chips .cur-chip').forEach(chip => {
                    chip.setAttribute('aria-pressed', String(chip.classList.contains('active')));
                });
                ['create-exchange-name', 'create-exchange-price', 'create-given-amount'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.value = '';
                });
                // Banner va eski qarzlar ro'yxati yashiriladi
                clearCreateClientBanner();
                clearFormErrors(form);

                updateCreateCalculation();

                // Refresh data and switch to tab 1
                await fetchStats();
                await fetchSummaries();
                switchTab('tab-table');
            } catch (err) {
                hapticError();
                showToast(err.message, 'error');
            } finally {
                setButtonLoading(submitBtn, false);
            }
        });
    }
}

// ==========================================
// TAB 3: PAYMENT FORM
// ==========================================

function populatePaymentClients() {
    const select = document.getElementById('pay-client-select');
    if (!select) return;

    const previous = select.value;
    const debtors = state.summaries.filter(s => s.has_debt);
    select.innerHTML = `<option value="">${debtors.length ? 'Mijozni tanlang' : "Qarzdor mijozlar yo'q"}</option>` +
        debtors.map(d => `
            <option value="${d.id}" data-name="${escapeHtml(d.full_name)}" data-phone="${escapeHtml(d.phone)}"
                    data-remaining-uzs="${(d.remaining && d.remaining.UZS) || 0}"
                    data-remaining-usd="${(d.remaining && d.remaining.USD) || 0}">
                ${escapeHtml(d.full_name)} — ${formatMoneyMap(d.remaining)}
            </option>
        `).join('');
    // Ro'yxat yangilanganda tanlangan mijoz saqlanib qoladi
    if (previous && debtors.some(d => String(d.id) === previous)) {
        select.value = previous;
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
            document.getElementById('pay-selected-client-phone').textContent = phone || 'Telefon kiritilmagan';
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
            : [{ v: 100000, label: '100 ming' }, { v: 500000, label: '500 ming' }, { v: 1000000, label: '1 mln' }, { v: 'half', label: '50%' }];
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
                setFieldError(select, 'Qarzdor mijozni tanlang');
                return;
            }

            if (!isValidDateString(payDate)) {
                setFieldError(payDateInput, "To'lov sanasi noto'g'ri. Masalan: 20.08.2026");
                return;
            }

            let amount = totalDebt;
            if (mode === 'partial') {
                amount = Number(partialInput?.value) || 0;
                if (amount <= 0) {
                    setFieldError(partialInput, "To'lov summasini kiriting");
                    return;
                }
                if (totalDebt <= 0) {
                    setFieldError(partialInput, `Mijozning ${currency === 'USD' ? 'dollar' : "so'm"}dagi qarzi yo'q. Boshqa valyutani tanlang`);
                    return;
                }
                if (amount > totalDebt) {
                    setFieldError(partialInput, `Summa qarzdan oshmasligi kerak (maksimal: ${formatMoney(totalDebt, currency)})`);
                    return;
                }
            }

            setButtonLoading(submitBtn, true, 'Qabul qilinmoqda…');

            try {
                const res = await apiFetch('/api/payments', {
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

                const json = await res.json();
                if (!res.ok || json.error) {
                    throw new Error(json.error || "To'lovni qabul qilishda xatolik");
                }

                hapticSuccess();
                showToast(json.is_closed ? "To'lov qabul qilindi — qarz to'liq yopildi" : "To'lov muvaffaqiyatli qabul qilindi", 'success');

                // Reset payment form
                form?.reset();
                clearFormErrors(form);
                if (payDateInput) payDateInput.value = getTodayFormatted();
                if (infoCard) infoCard.style.display = 'none';
                if (optionsWrapper) optionsWrapper.style.display = 'none';
                if (partialGroup) partialGroup.style.display = 'none';

                // Refresh data and switch to tab 1
                await fetchStats();
                await fetchSummaries();
                switchTab('tab-table');
            } catch (err) {
                hapticError();
                showToast(err.message, 'error');
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
    if (tabId !== 'tab-paid' && paidState.isSelecting) exitPaidSelection();
    if (tabId !== 'tab-trash' && trashState.isSelecting) exitTrashSelection();
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

document.addEventListener('DOMContentLoaded', () => {
    // Agar Telegram Mini App ichida ochilmagan bo'lsa (URL orqali brauzerdan kirilsa)
    if (!tg || !tg.initData) {
        showUnauthorizedState("Ilovadan foydalanish uchun uni Telegram bot orqali oching.");
        return;
    }

    // Refresh Button — barcha tablar ma'lumotini qayta yuklaydi
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.classList.add('rotating');
            hapticImpact();
            refreshBtn.disabled = true;
            await Promise.all([
                fetchStats(),
                fetchSummaries(),
                fetchAndRenderPaidDebts(),
                fetchAndRenderTrash(),
            ]);
            setTimeout(() => {
                refreshBtn.classList.remove('rotating');
                refreshBtn.disabled = false;
            }, 400);
            showToast("Ma'lumotlar yangilandi", 'success');
        });
    }

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
            if (select) {
                select.value = String(clientId);
                select.dispatchEvent(new Event('change'));
                if (!select.value) showToast("Bu mijozda to'lanadigan qarz topilmadi", 'info');
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
    setupPaymentForm();
    setupPaidTab();
    setupTrashTab();

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

    // Initial Fetch — barcha asosiy ma'lumotlarni birdaniga yuklaymiz
    fetchStats();
    fetchSummaries();
    fetchAndRenderPaidDebts();
    fetchAndRenderTrash();
});

// ==========================================
// UTILITY: LONG-PRESS & TAP GESTURE HANDLER
// ==========================================

// ==========================================
// UTILITY: LONG-PRESS & TAP GESTURE HANDLER
// ==========================================

function attachCardGesture(card, onLongPress, onClick) {
    let timer = null;
    let isLong = false;
    let startX = 0;
    let startY = 0;
    let touchMoved = false;

    card.addEventListener('touchstart', (e) => {
        if (e.target.closest('input[type="checkbox"], button, a')) return;
        isLong = false;
        touchMoved = false;
        if (e.touches && e.touches.length > 0) {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }
        timer = setTimeout(() => {
            if (!touchMoved) {
                isLong = true;
                hapticImpact();
                onLongPress();
            }
        }, 380);
    }, { passive: true });

    card.addEventListener('touchmove', (e) => {
        if (e.touches && e.touches.length > 0) {
            const dx = Math.abs(e.touches[0].clientX - startX);
            const dy = Math.abs(e.touches[0].clientY - startY);
            if (dx > 8 || dy > 8) {
                touchMoved = true;
                if (timer) {
                    clearTimeout(timer);
                    timer = null;
                }
            }
        }
    }, { passive: true });

    card.addEventListener('touchend', () => {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
        if (!touchMoved && !isLong && onClick) {
            onClick();
        }
    });

    card.addEventListener('touchcancel', () => {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    });

    // Desktop mouse click
    card.addEventListener('click', (e) => {
        if (e.target.closest('input[type="checkbox"], button, a')) return;
        if (!window.matchMedia('(pointer: coarse)').matches && onClick) {
            onClick();
        }
    });
}

// ==========================================
// TAB: YOPILGANLAR (CLOSED DEBTS)
// ==========================================

// Yopilgan / Korzina qatorlari uchun yagona shablon
function renderDebtRowHTML(item, { isSelected, cbClass, statusHtml }) {
    const qty = item.product_quantity > 1 ? ` × ${item.product_quantity}` : '';
    return `
        <div class="list-row trash-item ${isSelected ? 'selected' : ''}" data-id="${item.id}">
            <input type="checkbox" class="trash-item-checkbox ${cbClass}" data-id="${item.id}" ${isSelected ? 'checked' : ''}
                   aria-label="${escapeHtml(item.product_name)} — ${escapeHtml(item.client_name)}ni tanlash">
            <div class="row-main">
                <div class="row-title">${escapeHtml(item.product_name)}${qty}</div>
                <div class="row-meta">
                    <span class="row-meta-item">${icon('user')}${escapeHtml(item.client_name)}</span>
                    <span class="row-meta-item">${icon('calendar')}${escapeHtml(item.debt_date)}</span>
                </div>
            </div>
            <div class="row-side">
                <div class="row-amount">${formatMoney(item.original_debt, item.currency)}</div>
                ${statusHtml}
            </div>
        </div>
    `;
}

const paidState = {
    items: [],
    selected: new Set(),
    isSelecting: false,
};

function enterPaidSelection(initialId = null) {
    paidState.isSelecting = true;
    const listEl = document.getElementById('paid-debts-list');
    if (listEl) listEl.classList.add('selection-active');

    const normalBar = document.getElementById('paid-normal-bar');
    const selectBar = document.getElementById('paid-select-bar');
    const floatingBar = document.getElementById('paid-floating-action-bar');
    if (normalBar) normalBar.style.display = 'none';
    if (selectBar) selectBar.style.display = 'flex';
    if (floatingBar) floatingBar.style.display = 'block';

    if (initialId !== null && initialId !== undefined) {
        paidState.selected.add(initialId);
        const card = document.querySelector(`#paid-debts-list .trash-item[data-id="${initialId}"]`);
        const cb = document.querySelector(`.paid-cb[data-id="${initialId}"]`);
        if (card) card.classList.add('selected');
        if (cb) cb.checked = true;
    }
    updatePaidToolbar();
}

function exitPaidSelection() {
    paidState.isSelecting = false;
    paidState.selected.clear();

    const listEl = document.getElementById('paid-debts-list');
    if (listEl) {
        listEl.classList.remove('selection-active');
        listEl.querySelectorAll('.trash-item').forEach(c => c.classList.remove('selected'));
        listEl.querySelectorAll('.paid-cb').forEach(cb => { cb.checked = false; });
    }

    const normalBar = document.getElementById('paid-normal-bar');
    const selectBar = document.getElementById('paid-select-bar');
    const floatingBar = document.getElementById('paid-floating-action-bar');
    if (normalBar) normalBar.style.display = 'flex';
    if (selectBar) selectBar.style.display = 'none';
    if (floatingBar) floatingBar.style.display = 'none';

    updatePaidToolbar();
}

function togglePaidItem(id) {
    if (paidState.selected.has(id)) {
        paidState.selected.delete(id);
    } else {
        paidState.selected.add(id);
    }
    const card = document.querySelector(`#paid-debts-list .trash-item[data-id="${id}"]`);
    const cb = document.querySelector(`.paid-cb[data-id="${id}"]`);
    const isSelected = paidState.selected.has(id);
    if (card) card.classList.toggle('selected', isSelected);
    if (cb) cb.checked = isSelected;
    updatePaidToolbar();
    hapticImpact();
}

function renderPaidDebts() {
    const container = document.getElementById('paid-debts-list');
    const badge = document.getElementById('paid-total-badge');
    if (!container) return;

    if (badge) badge.textContent = `${paidState.items.length} ta`;

    document.getElementById('btn-paid-enter-select')?.toggleAttribute('disabled', paidState.items.length === 0);

    if (paidState.items.length === 0) {
        container.innerHTML = stateBlockHTML({
            iconName: 'check-circle',
            title: "Yopilgan qarzlar yo'q",
            desc: "To'liq to'langan qarzlar shu yerda ko'rinadi.",
        });
        exitPaidSelection();
        return;
    }

    container.innerHTML = paidState.items.map(item => renderDebtRowHTML(item, {
        isSelected: paidState.selected.has(item.id),
        cbClass: 'paid-cb',
        statusHtml: '<span class="badge badge-success">Yopilgan</span>',
    })).join('');

    if (paidState.isSelecting) {
        container.classList.add('selection-active');
    } else {
        container.classList.remove('selection-active');
    }

    // Har bir kartochkaga gesture ulaymiz
    container.querySelectorAll('.trash-item').forEach(card => {
        const id = Number(card.getAttribute('data-id'));

        attachCardGesture(
            card,
            () => {
                if (!paidState.isSelecting) {
                    enterPaidSelection(id);
                } else {
                    togglePaidItem(id);
                }
            },
            () => {
                if (paidState.isSelecting) {
                    togglePaidItem(id);
                } else {
                    enterPaidSelection(id);
                }
            }
        );
    });

    // Checkbox bosilganda
    container.querySelectorAll('.paid-cb').forEach(cb => {
        cb.addEventListener('change', () => {
            const id = Number(cb.getAttribute('data-id'));
            togglePaidItem(id);
        });
    });
}

function updatePaidToolbar() {
    const countLabel = document.getElementById('paid-selected-count-label');
    const moveBtn = document.getElementById('btn-move-to-trash');
    const allBtn = document.getElementById('btn-paid-select-all-toggle');
    const cnt = paidState.selected.size;

    if (countLabel) {
        countLabel.textContent = cnt > 0 ? `${cnt} ta tanlandi` : 'Yozuvlarni tanlang';
    }
    if (moveBtn && !moveBtn.dataset.originalHtml) {
        moveBtn.disabled = cnt === 0;
        moveBtn.innerHTML = `${icon('trash')}${cnt > 0 ? `Korzinaga yuborish (${cnt})` : 'Korzinaga yuborish'}`;
    }
    if (allBtn) {
        const allSelected = paidState.items.length > 0 && cnt === paidState.items.length;
        allBtn.textContent = allSelected ? 'Hech biri' : 'Barchasi';
    }
}

async function fetchAndRenderPaidDebts() {
    const container = document.getElementById('paid-debts-list');
    if (!container) return;
    try {
        const res = await apiFetch(`/api/paid-debts?limit=${LIST_LIMIT}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        paidState.items = await res.json();
        paidState.selected.clear();
        renderPaidDebts();
    } catch (err) {
        console.error('Error fetching paid debts:', err);
        container.innerHTML = stateBlockHTML({
            iconName: 'alert-triangle',
            title: "Yopilgan qarzlarni yuklab bo'lmadi",
            desc: "Internet aloqasini tekshiring va qayta urinib ko'ring.",
            action: { id: 'retry-paid', label: 'Qayta urinish' },
            isError: true,
        });
    }
}

function setupPaidTab() {
    // "Tanlash" tugmasi
    document.getElementById('btn-paid-enter-select')?.addEventListener('click', () => {
        enterPaidSelection();
        hapticImpact();
    });

    // "Bekor qilish" tugmasi
    document.getElementById('btn-paid-cancel-select')?.addEventListener('click', () => {
        exitPaidSelection();
        hapticImpact();
    });

    // "Barchasi / Hech biri" tugmasi
    document.getElementById('btn-paid-select-all-toggle')?.addEventListener('click', () => {
        const listEl = document.getElementById('paid-debts-list');
        if (paidState.selected.size === paidState.items.length) {
            paidState.selected.clear();
            listEl?.querySelectorAll('.trash-item').forEach(c => c.classList.remove('selected'));
            listEl?.querySelectorAll('.paid-cb').forEach(cb => { cb.checked = false; });
        } else {
            paidState.items.forEach(i => paidState.selected.add(i.id));
            listEl?.querySelectorAll('.trash-item').forEach(c => c.classList.add('selected'));
            listEl?.querySelectorAll('.paid-cb').forEach(cb => { cb.checked = true; });
        }
        updatePaidToolbar();
        hapticImpact();
    });

    // "Korzinaga yuborish" tugmasi
    const moveBtn = document.getElementById('btn-move-to-trash');
    if (moveBtn) {
        moveBtn.addEventListener('click', async () => {
            const ids = [...paidState.selected];
            if (ids.length === 0) return;

            setButtonLoading(moveBtn, true, 'Yuborilmoqda…');

            try {
                const res = await apiFetch('/api/trash/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ debt_ids: ids }),
                });
                const json = await res.json();
                if (!res.ok || json.error) throw new Error(json.error || 'Xatolik');
                hapticSuccess();
                showToast(`${json.moved} ta yozuv korzinaga yuborildi`, 'success');
                setButtonLoading(moveBtn, false);
                exitPaidSelection();
                await Promise.all([
                    fetchStats(),
                    fetchSummaries(),
                    fetchAndRenderPaidDebts(),
                    fetchAndRenderTrash(),
                ]);
            } catch (err) {
                hapticError();
                showToast(err.message, 'error');
                setButtonLoading(moveBtn, false);
                updatePaidToolbar();
            }
        });
    }
}

// ==========================================
// TAB: KORZINA (TRASH)
// ==========================================

const trashState = {
    items: [],
    selected: new Set(),
    isSelecting: false,
};

function enterTrashSelection(initialId = null) {
    trashState.isSelecting = true;
    const listEl = document.getElementById('trash-list');
    if (listEl) listEl.classList.add('selection-active');

    const normalBar = document.getElementById('trash-normal-bar');
    const selectBar = document.getElementById('trash-select-bar');
    const floatingBar = document.getElementById('trash-floating-action-bar');
    if (normalBar) normalBar.style.display = 'none';
    if (selectBar) selectBar.style.display = 'flex';
    if (floatingBar) floatingBar.style.display = 'block';

    if (initialId !== null && initialId !== undefined) {
        trashState.selected.add(initialId);
        const card = document.querySelector(`#trash-list .trash-item[data-id="${initialId}"]`);
        const cb = document.querySelector(`.trash-cb[data-id="${initialId}"]`);
        if (card) card.classList.add('selected');
        if (cb) cb.checked = true;
    }
    updateTrashToolbar();
}

function exitTrashSelection() {
    trashState.isSelecting = false;
    trashState.selected.clear();

    const listEl = document.getElementById('trash-list');
    if (listEl) {
        listEl.classList.remove('selection-active');
        listEl.querySelectorAll('.trash-item').forEach(c => c.classList.remove('selected'));
        listEl.querySelectorAll('.trash-cb').forEach(cb => { cb.checked = false; });
    }

    const normalBar = document.getElementById('trash-normal-bar');
    const selectBar = document.getElementById('trash-select-bar');
    const floatingBar = document.getElementById('trash-floating-action-bar');
    if (normalBar) normalBar.style.display = 'flex';
    if (selectBar) selectBar.style.display = 'none';
    if (floatingBar) floatingBar.style.display = 'none';

    updateTrashToolbar();
}

function toggleTrashItem(id) {
    if (trashState.selected.has(id)) {
        trashState.selected.delete(id);
    } else {
        trashState.selected.add(id);
    }
    const card = document.querySelector(`#trash-list .trash-item[data-id="${id}"]`);
    const cb = document.querySelector(`.trash-cb[data-id="${id}"]`);
    const isSelected = trashState.selected.has(id);
    if (card) card.classList.toggle('selected', isSelected);
    if (cb) cb.checked = isSelected;
    updateTrashToolbar();
    hapticImpact();
}

function renderTrash() {
    const container = document.getElementById('trash-list');
    const badge = document.getElementById('trash-total-badge');
    const purgeBar = document.getElementById('trash-purge-bar');
    if (!container) return;

    if (badge) badge.textContent = `${trashState.items.length} ta`;

    document.getElementById('btn-trash-enter-select')?.toggleAttribute('disabled', trashState.items.length === 0);

    if (trashState.items.length === 0) {
        container.innerHTML = stateBlockHTML({
            iconName: 'trash',
            title: "Korzina bo'sh",
            desc: "Yopilgan bo'limidan yuborilgan yozuvlar shu yerda saqlanadi.",
        });
        if (purgeBar) purgeBar.style.display = 'none';
        exitTrashSelection();
        return;
    }

    if (purgeBar) purgeBar.style.display = 'flex';

    container.innerHTML = trashState.items.map(item => renderDebtRowHTML(item, {
        isSelected: trashState.selected.has(item.id),
        cbClass: 'trash-cb',
        statusHtml: '<span class="badge badge-neutral">Korzinada</span>',
    })).join('');

    if (trashState.isSelecting) {
        container.classList.add('selection-active');
    } else {
        container.classList.remove('selection-active');
    }

    // Har bir kartochkaga gesture
    container.querySelectorAll('.trash-item').forEach(card => {
        const id = Number(card.getAttribute('data-id'));
        attachCardGesture(
            card,
            () => {
                if (!trashState.isSelecting) {
                    enterTrashSelection(id);
                } else {
                    toggleTrashItem(id);
                }
            },
            () => {
                if (trashState.isSelecting) {
                    toggleTrashItem(id);
                } else {
                    enterTrashSelection(id);
                }
            }
        );
    });

    container.querySelectorAll('.trash-cb').forEach(cb => {
        cb.addEventListener('change', () => {
            const id = Number(cb.getAttribute('data-id'));
            toggleTrashItem(id);
        });
    });
}

function updateTrashToolbar() {
    const countLabel = document.getElementById('trash-selected-count-label');
    const restoreBtn = document.getElementById('btn-restore-from-trash');
    const allBtn = document.getElementById('btn-trash-select-all-toggle');
    const cnt = trashState.selected.size;

    if (countLabel) {
        countLabel.textContent = cnt > 0 ? `${cnt} ta tanlandi` : 'Yozuvlarni tanlang';
    }
    if (restoreBtn && !restoreBtn.dataset.originalHtml) {
        restoreBtn.disabled = cnt === 0;
        restoreBtn.innerHTML = `${icon('restore')}${cnt > 0 ? `Yopilganlarga qaytarish (${cnt})` : 'Yopilganlarga qaytarish'}`;
    }
    if (allBtn) {
        const allSelected = trashState.items.length > 0 && cnt === trashState.items.length;
        allBtn.textContent = allSelected ? 'Hech biri' : 'Barchasi';
    }
}


async function fetchAndRenderTrash() {
    const container = document.getElementById('trash-list');
    if (!container) return;
    if (!trashState.items.length) container.innerHTML = skeletonRowsHTML(2);
    try {
        const res = await apiFetch(`/api/trash?limit=${LIST_LIMIT}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        trashState.items = await res.json();
        trashState.selected.clear();
        trashState.isSelecting = false;
        renderTrash();
    } catch (err) {
        console.error('Error fetching trash:', err);
        container.innerHTML = stateBlockHTML({
            iconName: 'alert-triangle',
            title: "Korzinani yuklab bo'lmadi",
            desc: "Internet aloqasini tekshiring va qayta urinib ko'ring.",
            action: { id: 'retry-trash', label: 'Qayta urinish' },
            isError: true,
        });
        document.getElementById('trash-purge-bar')?.style.setProperty('display', 'none');
    }
}

// Korzinani tozalash uchun inline confirm paneli
function showPurgeConfirm() {
    const bar = document.getElementById('trash-purge-bar');
    if (!bar) return;
    hapticImpact();
    bar.innerHTML = `
        <div class="danger-zone-texts" role="alert">
            <span class="danger-zone-title">${trashState.items.length} ta yozuv butunlay o'chirilsinmi?</span>
            <span class="purge-bar-text">Bu amalni ortga qaytarib bo'lmaydi.</span>
        </div>
        <div class="danger-zone-actions">
            <button id="btn-purge-cancel" class="btn btn-secondary btn-sm" type="button">Bekor qilish</button>
            <button id="btn-purge-confirm" class="btn btn-danger btn-sm" type="button">Ha, o'chirish</button>
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
            <span class="danger-zone-title">Korzinani tozalash</span>
            <span class="purge-bar-text">Barcha yozuvlar butunlay o'chiriladi. Bu amalni ortga qaytarib bo'lmaydi.</span>
        </div>
        <button id="btn-purge-trash" class="btn btn-danger-outline btn-sm" type="button">${icon('trash')} Tozalash</button>
    `;
    document.getElementById('btn-purge-trash')?.addEventListener('click', showPurgeConfirm);
}

async function executePurge() {
    const bar = document.getElementById('trash-purge-bar');
    const confirmBtn = document.getElementById('btn-purge-confirm');
    setButtonLoading(confirmBtn, true, 'O\'chirilmoqda…');
    const cancelBtn = document.getElementById('btn-purge-cancel');
    if (cancelBtn) cancelBtn.disabled = true;
    try {
        const res = await apiFetch('/api/trash/purge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const json = await res.json();
        if (!res.ok || json.error) throw new Error(json.error || 'Xatolik');
        hapticSuccess();
        showToast(`${json.deleted} ta yozuv butunlay o'chirildi`, 'success');
        hidePurgeConfirm();
        exitTrashSelection();
        await Promise.all([
            fetchStats(),
            fetchSummaries(),
            fetchAndRenderTrash(),
            fetchAndRenderPaidDebts(),
        ]);
    } catch (err) {
        hapticError();
        showToast(err.message, 'error');
        hidePurgeConfirm();
    }
}

function setupTrashTab() {
    // "Tanlash" tugmasi
    document.getElementById('btn-trash-enter-select')?.addEventListener('click', () => {
        enterTrashSelection();
        hapticImpact();
    });

    // "Bekor qilish" tugmasi
    document.getElementById('btn-trash-cancel-select')?.addEventListener('click', () => {
        exitTrashSelection();
        hapticImpact();
    });

    // "Barchasi / Hech biri" tugmasi
    document.getElementById('btn-trash-select-all-toggle')?.addEventListener('click', () => {
        if (trashState.selected.size === trashState.items.length) {
            trashState.selected.clear();
        } else {
            trashState.items.forEach(i => trashState.selected.add(i.id));
        }
        renderTrash();
        updateTrashToolbar();
        hapticImpact();
    });

    // "↩️ Qaytarish" tugmasi
    const restoreBtn = document.getElementById('btn-restore-from-trash');
    if (restoreBtn) {
        restoreBtn.addEventListener('click', async () => {
            const ids = [...trashState.selected];
            if (ids.length === 0) return;

            setButtonLoading(restoreBtn, true, 'Qaytarilmoqda…');
            try {
                const res = await apiFetch('/api/trash/restore', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ debt_ids: ids }),
                });
                const json = await res.json();
                if (!res.ok || json.error) throw new Error(json.error || 'Xatolik');
                hapticSuccess();
                showToast(`${json.restored} ta yozuv yopilganlarga qaytarildi`, 'success');
                setButtonLoading(restoreBtn, false);
                exitTrashSelection();
                await Promise.all([
                    fetchStats(),
                    fetchSummaries(),
                    fetchAndRenderTrash(),
                    fetchAndRenderPaidDebts(),
                ]);
            } catch (err) {
                hapticError();
                showToast(err.message, 'error');
                setButtonLoading(restoreBtn, false);
                updateTrashToolbar();
            }
        });
    }

    // Purge tugmasi — inline confirm orqali
    document.getElementById('btn-purge-trash')?.addEventListener('click', showPurgeConfirm);
}




