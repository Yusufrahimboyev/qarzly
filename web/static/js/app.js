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

function showToast(message) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function showUnauthorizedState(message = "Ushbu tizimga faqat ruxsat berilgan Telegram foydalanuvchilari kira oladi.") {
    const app = document.getElementById('app') || document.body;
    app.innerHTML = `
        <div style="min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; text-align: center; font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; background: #0f172a; color: #f8fafc;">
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 20px; padding: 36px 24px; max-width: 380px; width: 100%; box-shadow: 0 12px 32px rgba(0,0,0,0.3);">
                <div style="font-size: 3.5rem; margin-bottom: 16px;">⛔️</div>
                <h2 style="font-size: 1.35rem; font-weight: 800; color: #f1f5f9; margin-bottom: 12px;">Kirish Cheklangan</h2>
                <p style="color: #94a3b8; font-size: 0.95rem; line-height: 1.6; margin-bottom: 20px;">
                    ${message}
                </p>
                <div style="font-size: 0.85rem; color: #64748b; border-top: 1px solid #334155; padding-top: 16px;">
                    Ilovani faqat vakolatli Telegram akkauntingizdagi bot orqali oching.
                </div>
            </div>
        </div>
    `;
}

// Barcha API so'rovlarini Telegram initData imzosi bilan yuboradi.
// Server imzoni tekshiradi — begona shaxs URLni bilsa ham ma'lumot ololmaydi.
async function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (tg && tg.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
        showUnauthorizedState("Ruxsat berilmagan. Ilovani Telegram boti ichida oching.");
    } else if (res.status === 403) {
        showUnauthorizedState("⛔️ Sizning Telegram ID'ingizga ushbu tizimdan foydalanish huquqi berilmagan.");
    } else if (res.status === 502 || res.status === 503) {
        showToast("⏳ Server yangilanmoqda, 10-20 soniyadan so'ng qayta urinib ko'ring...");
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
        document.getElementById('stat-total-debt').textContent = formatMoneyMap(data.total_debt);
        document.getElementById('stat-debtors-count').textContent = `${data.debtors_count} ta`;
        document.getElementById('stat-clients-count').textContent = `${data.clients_count} ta`;
    } catch (err) {
        console.error('Error fetching stats:', err);
    }
}

async function fetchSummaries() {
    try {
        const res = await apiFetch('/api/summaries');
        if (res.status === 401 || res.status === 403) {
            showUnauthorizedState();
            return;
        }
        if (!res.ok) return;
        state.summaries = await res.json();
        renderClientsList();
        populatePaymentClients();
    } catch (err) {
        console.error('Error fetching summaries:', err);
        document.getElementById('clients-list').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <p>Ma'lumotlarni yuklab bo'lmadi</p>
            </div>
        `;
    }
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
    const dateHtml = item.latest_debt_date
        ? `<div class="client-date-tag">📅 ${escapeHtml(item.latest_debt_date)}</div>`
        : '';
    return `
        <div class="client-item-card" data-client-id="${item.id}">
            <div class="client-item-main">
                <div class="client-name">${escapeHtml(item.full_name)}</div>
                <div class="client-phone">${escapeHtml(item.phone || 'Telefonsiz')}</div>
                ${dateHtml}
            </div>
            <div class="client-item-meta">
                <div class="client-debt-badge">
                    <div class="client-debt-amount ${item.has_debt ? '' : 'is-paid'}">
                        ${item.has_debt ? formatMoneyMap(item.remaining) : formatMoney(0)}
                    </div>
                    <span class="client-status-pill ${item.has_debt ? 'pill-debt' : 'pill-paid'}">
                        ${item.has_debt ? '🔴 Qarzdor' : '🟢 Yopilgan'}
                    </span>
                </div>
                <button class="client-history-btn" data-client-id="${item.id}" title="Hisobot" aria-label="Hisobot">
                    📊
                </button>
            </div>
        </div>
    `;
}

function renderClientsList() {
    const container = document.getElementById('clients-list');
    if (!container) return;

    state.filteredList = getProcessedList();
    state.renderedCount = 0;

    if (state.filteredList.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📂</div>
                <p>Hech qanday mijoz topilmadi</p>
            </div>
        `;
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
        sentinel.style.height = '30px';
        sentinel.style.margin = '10px 0';
        sentinel.style.textAlign = 'center';
        sentinel.style.color = 'var(--text-muted)';
        sentinel.style.fontSize = '12px';
        sentinel.textContent = 'Yuklanmoqda...';
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
        document.getElementById('banner-client-phone').textContent = person.phone || '-';
        banner.style.display = 'flex';
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
    listEl.innerHTML = '<div class="banner-debt-loading">Yuklanmoqda...</div>';

    const data = await fetchClientReport(clientId);
    if (!data) {
        card.style.display = 'none';
        return;
    }

    const remaining = data.total_remaining_debt || {};
    const hasDebt = Object.values(remaining).some(v => (Number(v) || 0) > 0);
    totalEl.textContent = hasDebt ? formatMoneyMap(remaining) : "Qarz yo'q";

    const activeDebts = (data.debts || []).filter(d => d.status === 'active');
    if (activeDebts.length === 0) {
        listEl.innerHTML = '<div class="banner-no-debt">🟢 Yopilmagan qarzi yo&#8217;q</div>';
        return;
    }

    listEl.innerHTML = activeDebts.map(d => {
        const qtyLabel = d.product_quantity > 1 ? ` — ${d.product_quantity} ta` : '';
        return `
            <div class="banner-debt-item">
                <span class="banner-debt-name">📅 ${d.debt_date} — ${escapeHtml(d.product_name)}${qtyLabel}</span>
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
    const nameInput = document.getElementById('create-client-name');
    const phoneInput = document.getElementById('create-client-phone');
    if (nameInput) nameInput.value = '';
    if (phoneInput) phoneInput.value = '';
}

function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ==========================================
// CLIENT REPORT MODAL
// ==========================================

async function openClientReportModal(clientId) {
    hapticImpact();
    const modal = document.getElementById('report-modal');
    if (!modal) return;

    // 1. Keshdagi mijoz ma'lumotlari orqali modalni DARHOL ochamiz (0ms kechikish)
    const cached = state.summaries.find(s => String(s.id) === String(clientId));
    if (cached) {
        document.getElementById('modal-client-name').textContent = cached.full_name;
        document.getElementById('modal-client-phone').textContent = cached.phone || '-';
        document.getElementById('modal-total-remaining').textContent = cached.has_debt ? formatMoneyMap(cached.remaining) : "Qarz yo'q";
        document.getElementById('modal-total-products').textContent = '...';
        document.getElementById('modal-total-paid').textContent = '...';
    } else {
        document.getElementById('modal-client-name').textContent = 'Mijoz Hisoboti';
        document.getElementById('modal-client-phone').textContent = 'Yuklanmoqda...';
    }

    const debtsList = document.getElementById('modal-debts-list');
    const paymentsList = document.getElementById('modal-payments-list');
    if (debtsList) debtsList.innerHTML = '<div style="text-align:center;padding:16px;color:var(--text-muted);font-size:13px;">Tarix yuklanmoqda...</div>';
    if (paymentsList) paymentsList.innerHTML = '<div style="text-align:center;padding:16px;color:var(--text-muted);font-size:13px;">Yuklanmoqda...</div>';

    modal.style.display = 'flex';

    // 2. Fonda to'liq hisobotni yuklab, modalni to'ldiramiz
    const data = await fetchClientReport(clientId);
    if (!data) {
        showToast('Mijoz ma\'lumotlarini yuklab bo\'lmadi');
        return;
    }

    state.selectedClientReport = data;

    document.getElementById('modal-client-name').textContent = data.client.full_name;
    document.getElementById('modal-client-phone').textContent = data.client.phone || '-';
    document.getElementById('modal-total-products').textContent = formatMoneyMap(data.total_product_price);
    document.getElementById('modal-total-paid').textContent = formatMoneyMap(sumMaps(data.total_paid_after, data.total_given_money));
    document.getElementById('modal-total-remaining').textContent = formatMoneyMap(data.total_remaining_debt);

    // Render Debts History — ko'p tovarli bo'lsa har bir tovarni alohida ko'rsatadi
    if (data.debts.length === 0) {
        debtsList.innerHTML = '<p class="text-muted" style="font-size:13px;">Qarzlar mavjud emas</p>';
    } else {
        debtsList.innerHTML = data.debts.map(d => {
            const products = d.products || [];
            const hasMultiProducts = products.length > 1;
            const productListHtml = hasMultiProducts
                ? products.map((p, i) => {
                    const pCur = p.currency || d.currency;
                    return `
                    <div class="history-card-detail" style="padding-left:4px;">
                        <span>  ${i + 1}. 📦 ${escapeHtml(p.name)}${p.quantity > 1 ? ` — ${p.quantity} × ${formatMoney(p.price_per_unit, pCur)}` : ''}</span>
                        <span>${formatMoney(p.quantity * p.price_per_unit, pCur)}</span>
                    </div>
                `;}).join('')
                : '';

            const statusText = d.status === 'active'
                ? formatMoney(d.remaining_debt, d.currency)
                : '🟢 Yopilgan';
            const statusClass = d.status === 'active' ? 'text-danger' : 'text-success';

            return `
                <div class="history-card">
                    <div class="history-card-header">
                        <span>${escapeHtml(d.product_name)}${d.product_quantity > 1 ? ` — ${d.product_quantity} ta` : ''}</span>
                        <span class="${statusClass}">${statusText}</span>
                    </div>
                    ${productListHtml}
                    <div class="history-card-detail">
                        <span>📅 ${d.debt_date}</span>
                        <span>Narxi: ${formatMoney(d.product_price, d.currency)}</span>
                    </div>
                    ${d.exchange_exists ? `
                    <div class="history-card-detail" style="color:var(--accent-yellow); margin-top:2px;">
                        <span>🔄 Exchange: ${escapeHtml(d.exchange_product_name || 'Tovar')}</span>
                        <span>-${formatMoney(d.exchange_product_price, d.currency)}</span>
                    </div>` : ''}
                    ${d.given_money > 0 ? `
                    <div class="history-card-detail" style="color:var(--accent-green); margin-top:2px;">
                        <span>💵 Berilgan pul:</span>
                        <span>-${formatMoney(d.given_money, d.currency)}</span>
                    </div>` : ''}
                </div>
            `;
        }).join('');
    }

    // Render Payments History
    const actualPayments = data.payments.filter(p => p.payment_type !== 'initial');
    if (actualPayments.length === 0) {
        paymentsList.innerHTML = '<p class="text-muted" style="font-size:13px;">To\'lovlar mavjud emas</p>';
    } else {
        paymentsList.innerHTML = actualPayments.map(p => `
            <div class="history-card">
                <div class="history-card-header">
                    <span class="text-success">+${formatMoney(p.amount, p.currency)}</span>
                    <span style="font-size:11px; text-transform:uppercase;">
                        ${p.payment_type === 'full' ? 'To\'liq' : 'Qisman'}
                    </span>
                </div>
                <div class="history-card-detail">
                    <span>📅 ${p.payment_date}</span>
                </div>
            </div>
        `).join('');
    }

    const payBtn = document.getElementById('modal-pay-now-btn');
    const remainingValues = Object.values(data.total_remaining_debt || {});
    const hasAnyDebt = remainingValues.some(v => (Number(v) || 0) > 0);
    if (payBtn) payBtn.style.display = hasAnyDebt ? 'block' : 'none';
}

function closeClientReportModal() {
    const modal = document.getElementById('report-modal');
    if (modal) modal.style.display = 'none';
    state.selectedClientReport = null;
}

// ==========================================
// TAB 2: CREATE DEBT FORM — DINAMIK TOVARLAR (har biri o'z valyutasida)
// ==========================================

function createProductGroupHTML(index) {
    return `
        <div class="product-group" data-product-index="${index}">
            <div class="product-group-header">
                <span class="product-group-title">📦 ${index + 1}-tovar</span>
                ${index > 0 ? '<button type="button" class="btn-remove-product" title="O\'chirish">&times;</button>' : ''}
            </div>
            <div class="form-group">
                <label>Tovar nomi</label>
                <input type="text" class="product-name" placeholder="Masalan: Shina, Akkumulyator" required>
            </div>
            <div class="product-row">
                <div class="form-group product-row-item">
                    <label>Nechta</label>
                    <input type="number" class="product-qty" placeholder="1" min="1" step="1" value="1" required>
                </div>
                <div class="form-group product-row-item">
                    <label>Narxi</label>
                    <input type="number" class="product-price" placeholder="2500000" min="1" step="1000" required>
                </div>
            </div>
            <div class="product-currency-row">
                <span class="product-currency-label">💱 Valyuta:</span>
                <div class="currency-chips">
                    <button type="button" class="cur-chip active" data-currency="UZS">💵 So'm</button>
                    <button type="button" class="cur-chip" data-currency="USD">$ Dollar</button>
                </div>
            </div>
            <div class="product-subtotal">
                <span>Jami:</span>
                <strong class="product-subtotal-val">0 so'm</strong>
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
        if (title) title.textContent = `📦 ${i + 1}-tovar`;
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
            chip.closest('.currency-chips').querySelectorAll('.cur-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
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
        el.addEventListener('input', updateCreateCalculation);
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

    // Default Date to Today
    if (dateInput) dateInput.value = getTodayFormatted();
    if (btnToday) {
        btnToday.addEventListener('click', () => {
            if (dateInput) dateInput.value = getTodayFormatted();
            hapticImpact();
        });
    }

    // Boshlang'ich tovar guruhiga listenerlar qo'shamiz
    const container = document.getElementById('products-container');
    if (container) attachProductGroupListeners(container);

    // "➕ Yana tovar qo'shish" tugmasi
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
        if (el) el.addEventListener('input', updateCreateCalculation);
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

            if (!clientName) {
                showToast('Mijoz ismini kiriting');
                return;
            }
            if (clientPhone) {
                const phoneDigits = clientPhone.replace(/\D/g, '');
                if (phoneDigits.length < 7 || phoneDigits.length > 15) {
                    showToast('Telefon raqami noto\'g\'ri (masalan: +998901234567)');
                    return;
                }
            }
            if (!isValidDateString(debtDate)) {
                showToast('Sana noto\'g\'ri: DD.MM.YYYY ko\'rinishida kiriting');
                return;
            }
            if (products.length === 0) {
                showToast('Kamida bitta tovar kiriting');
                return;
            }
            for (let i = 0; i < products.length; i++) {
                if (!products[i].name) {
                    showToast(`${i + 1}-tovar nomini kiriting`);
                    return;
                }
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
                    const curLabel = cur === 'USD' ? 'dollar' : 'so\'m';
                    showToast(`${curLabel}da exchange va berilgan pul tovarlar jami narxidan oshmasligi kerak`);
                    return;
                }
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Saqlanmoqda...';

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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                const json = await res.json();
                if (!res.ok || json.error) {
                    throw new Error(json.error || 'Qarzni saqlashda xatolik');
                }

                hapticSuccess();
                const remainingText = json.remaining_by_currency ? formatMoneyMap(json.remaining_by_currency) : '';
                showToast(remainingText
                    ? `✅ Saqlandi! Qarz: ${remainingText}`
                    : '✅ Qarz muvaffaqiyatli saqlandi!');

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
                // Banner va eski qarzlar ro'yxati yashiriladi
                const banner = document.getElementById('create-client-banner');
                if (banner) banner.style.display = 'none';
                const debtsCard = document.getElementById('banner-debts-card');
                if (debtsCard) debtsCard.style.display = 'none';

                updateCreateCalculation();

                // Refresh data and switch to tab 1
                await fetchStats();
                await fetchSummaries();
                switchTab('tab-table');
            } catch (err) {
                hapticError();
                showToast(`❌ ${err.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '✅ Qarzni Saqlash';
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

    const debtors = state.summaries.filter(s => s.has_debt);
    select.innerHTML = '<option value="">-- Mijozni tanlang --</option>' +
        debtors.map(d => `
            <option value="${d.id}" data-phone="${escapeHtml(d.phone)}"
                    data-remaining-uzs="${(d.remaining && d.remaining.UZS) || 0}"
                    data-remaining-usd="${(d.remaining && d.remaining.USD) || 0}">
                ${escapeHtml(d.full_name)} (${formatMoneyMap(d.remaining)})
            </option>
        `).join('');
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

    // Default Payment Date to Today
    if (payDateInput) payDateInput.value = getTodayFormatted();
    if (btnPayToday) {
        btnPayToday.addEventListener('click', () => {
            if (payDateInput) payDateInput.value = getTodayFormatted();
            hapticImpact();
        });
    }

    if (select) {
        select.addEventListener('change', () => {
            const opt = select.selectedOptions[0];
            if (!opt || !opt.value) {
                if (infoCard) infoCard.style.display = 'none';
                if (optionsWrapper) optionsWrapper.style.display = 'none';
                return;
            }

            const name = opt.text.split('(')[0].trim();
            const phone = opt.getAttribute('data-phone');
            const remainingMap = {
                UZS: getSelectedDebtInCurrency(opt, 'UZS'),
                USD: getSelectedDebtInCurrency(opt, 'USD'),
            };

            document.getElementById('pay-selected-client-name').textContent = name;
            document.getElementById('pay-selected-client-phone').textContent = phone;
            document.getElementById('pay-selected-client-debt').textContent = formatMoneyMap(remainingMap);

            infoCard.style.display = 'block';
            optionsWrapper.style.display = 'block';
            updatePaymentCalculation();
            hapticImpact();
        });
    }

    radioModes.forEach(radio => {
        radio.addEventListener('change', () => {
            const isPartial = radio.value === 'partial';
            if (partialGroup) partialGroup.style.display = isPartial ? 'block' : 'none';
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    // Valyuta almashtirilganda hisob yangilanadi
    document.querySelectorAll('input[name="payment_currency"]').forEach(radio => {
        radio.addEventListener('change', () => {
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    if (partialInput) {
        partialInput.addEventListener('input', updatePaymentCalculation);
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
            updatePaymentCalculation();
            hapticImpact();
        });
    });

    function updatePaymentCalculation() {
        const opt = select?.selectedOptions[0];
        const currency = getPaymentCurrency();
        const totalDebt = getSelectedDebtInCurrency(opt, currency);
        const otherCurrency = currency === 'USD' ? 'UZS' : 'USD';
        const otherDebt = getSelectedDebtInCurrency(opt, otherCurrency);
        const mode = document.querySelector('input[name="payment_mode"]:checked')?.value || 'full';

        // Quick-chips valyutaga moslanadi: so'mda 100k/500k/1M, dollarda 10/50/100
        updateQuickChips(currency);

        let payAmount = totalDebt;
        if (mode === 'partial') {
            payAmount = Number(partialInput?.value) || 0;
        }

        const remaining = Math.max(0, totalDebt - Math.min(payAmount, totalDebt));
        if (previewAmount) previewAmount.textContent = formatMoney(payAmount, currency);
        if (previewRemaining) {
            const totalText = otherDebt > 0
                ? `${formatMoney(remaining, currency)} + ${formatMoney(otherDebt, otherCurrency)}`
                : formatMoney(remaining, currency);
            previewRemaining.textContent = totalText;
            previewRemaining.className = (remaining === 0 && otherDebt === 0) ? 'text-success' : 'text-danger';
        }
    }

    function updateQuickChips(currency) {
        const chips = document.querySelectorAll('#partial-amount-group .btn-chip');
        if (chips.length === 0) return;
        const values = currency === 'USD'
            ? [{ v: 10, label: '10$' }, { v: 50, label: '50$' }, { v: 100, label: '100$' }, { v: 'half', label: '50%' }]
            : [{ v: 100000, label: '100k' }, { v: 500000, label: '500k' }, { v: 1000000, label: '1M' }, { v: 'half', label: '50%' }];
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

            if (!clientId) {
                showToast('Qarzdor mijozni tanlang');
                return;
            }

            if (!isValidDateString(payDate)) {
                showToast('To\'lov sanasi noto\'g\'ri (masalan: 20.08.2026)');
                return;
            }

            let amount = totalDebt;
            if (mode === 'partial') {
                amount = Number(partialInput?.value) || 0;
                if (amount <= 0) {
                    showToast('To\'lov summasini kiriting');
                    return;
                }
                if (amount > totalDebt) {
                    showToast('To\'lov summasi tanlangan valyutadagi qarzdan oshmasligi kerak');
                    return;
                }
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Qabul qilinmoqda...';

            try {
                const res = await apiFetch('/api/payments', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
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
                    throw new Error(json.error || 'To\'lovni qabul qilishda xatolik');
                }

                hapticSuccess();
                showToast('✅ To\'lov muvaffaqiyatli qabul qilindi!');

                // Reset payment form
                document.getElementById('payment-form').reset();
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
                showToast(`❌ ${err.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '✅ To\'lovni Qabul Qilish';
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
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });
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
            await Promise.all([
                fetchStats(),
                fetchSummaries(),
                fetchAndRenderPaidDebts(),
                fetchAndRenderTrash(),
            ]);
            setTimeout(() => refreshBtn.classList.remove('rotating'), 600);
            showToast('Yangilandi');
        });
    }

    // Event delegation on clients list container (Single listener for entire list)
    const clientsListContainer = document.getElementById('clients-list');
    if (clientsListContainer) {
        clientsListContainer.addEventListener('click', (e) => {
            const historyBtn = e.target.closest('.client-history-btn');
            if (historyBtn) {
                e.stopPropagation();
                const clientId = historyBtn.getAttribute('data-client-id');
                if (clientId) openClientReportModal(clientId);
                return;
            }
            const card = e.target.closest('.client-item-card');
            if (card) {
                const clientId = card.getAttribute('data-client-id');
                if (clientId) openClientReportModal(clientId);
            }
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
            if (clearSearchBtn) clearSearchBtn.style.display = val ? 'block' : 'none';
            handleSearch(val);
        });
    }
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
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
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
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
    const isFormField = (el) => !!el && ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName);
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

    if (paidState.items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🟢</div>
                <p>Yopilgan qarzlar yo'q</p>
            </div>
        `;
        exitPaidSelection();
        return;
    }

    container.innerHTML = paidState.items.map(item => {
        const isSelected = paidState.selected.has(item.id);
        return `
            <div class="trash-item ${isSelected ? 'selected' : ''}" data-id="${item.id}">
                <input type="checkbox" class="trash-item-checkbox paid-cb"
                       data-id="${item.id}" ${isSelected ? 'checked' : ''}>
                <div class="trash-item-body">
                    <div class="trash-item-name">${escapeHtml(item.product_name)}${item.product_quantity > 1 ? ` — ${item.product_quantity} ta` : ''}</div>
                    <div class="trash-item-client">👤 ${escapeHtml(item.client_name)}</div>
                    <div class="trash-item-meta">
                        <span>📅 ${item.debt_date}</span>
                        <span>💰 ${formatMoney(item.original_debt, item.currency)}</span>
                    </div>
                </div>
                <div class="trash-item-price">🟢 Yopilgan</div>
            </div>
        `;
    }).join('');

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
        countLabel.textContent = `${cnt} ta tanlandi`;
    }
    if (moveBtn) {
        moveBtn.disabled = cnt === 0;
        moveBtn.textContent = cnt > 0
            ? `🗑 Tanlanganlarni Korzinaga Yuborish (${cnt})`
            : `🗑 Tanlanganlarni Korzinaga Yuborish`;
    }
    if (allBtn) {
        const allSelected = paidState.items.length > 0 && cnt === paidState.items.length;
        allBtn.textContent = allSelected ? '◻️ Bekor' : '☑️ Barchasi';
    }
}

async function fetchAndRenderPaidDebts() {
    const container = document.getElementById('paid-debts-list');
    if (!container) return;
    try {
        const res = await apiFetch('/api/paid-debts');
        if (!res.ok) throw new Error('Yuklab bo\'lmadi');
        paidState.items = await res.json();
        paidState.selected.clear();
        renderPaidDebts();
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><p>${err.message}</p></div>`;
    }
}

function setupPaidTab() {
    // "🔘 Tanlash" tugmasi
    document.getElementById('btn-paid-enter-select')?.addEventListener('click', () => {
        enterPaidSelection();
        hapticImpact();
    });

    // "✕ Bekor" tugmasi
    document.getElementById('btn-paid-cancel-select')?.addEventListener('click', () => {
        exitPaidSelection();
        hapticImpact();
    });

    // "☑️ Barchasi" tugmasi
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

    // "🗑 Tanlanganlarni Korzinaga Yuborish" tugmasi
    const moveBtn = document.getElementById('btn-move-to-trash');
    if (moveBtn) {
        moveBtn.addEventListener('click', async () => {
            const ids = [...paidState.selected];
            if (ids.length === 0) return;

            moveBtn.disabled = true;
            moveBtn.textContent = 'Yuborilmoqda...';

            try {
                const res = await apiFetch('/api/trash/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ debt_ids: ids }),
                });
                const json = await res.json();
                if (!res.ok || json.error) throw new Error(json.error || 'Xatolik');
                hapticSuccess();
                showToast(`🗑 ${json.moved} ta qarz korzinaga yuborildi`);
                exitPaidSelection();
                await Promise.all([
                    fetchStats(),
                    fetchSummaries(),
                    fetchAndRenderPaidDebts(),
                    fetchAndRenderTrash(),
                ]);
            } catch (err) {
                hapticError();
                showToast(`❌ ${err.message}`);
                moveBtn.disabled = false;
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

    if (trashState.items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🗑</div>
                <p>Korzina bo'sh</p>
            </div>
        `;
        if (purgeBar) purgeBar.style.display = 'none';
        exitTrashSelection();
        return;
    }

    if (purgeBar) purgeBar.style.display = 'flex';

    container.innerHTML = trashState.items.map(item => {
        const isSelected = trashState.selected.has(item.id);
        return `
            <div class="trash-item ${isSelected ? 'selected' : ''}" data-id="${item.id}">
                <input type="checkbox" class="trash-item-checkbox trash-cb"
                       data-id="${item.id}" ${isSelected ? 'checked' : ''}>
                <div class="trash-item-body">
                    <div class="trash-item-name">${escapeHtml(item.product_name)}${item.product_quantity > 1 ? ` — ${item.product_quantity} ta` : ''}</div>
                    <div class="trash-item-client">👤 ${escapeHtml(item.client_name)}</div>
                    <div class="trash-item-meta">
                        <span>📅 ${item.debt_date}</span>
                        <span>💰 ${formatMoney(item.original_debt, item.currency)}</span>
                    </div>
                </div>
                <div class="trash-item-price" style="color: var(--text-muted);">🗑</div>
            </div>
        `;
    }).join('');

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
        countLabel.textContent = `${cnt} ta tanlandi`;
    }
    if (restoreBtn) {
        restoreBtn.disabled = cnt === 0;
        restoreBtn.textContent = cnt > 0
            ? `↩️ Tanlanganlarni Yopilganga Qaytarish (${cnt})`
            : `↩️ Tanlanganlarni Yopilganga Qaytarish`;
    }
    if (allBtn) {
        const allSelected = trashState.items.length > 0 && cnt === trashState.items.length;
        allBtn.textContent = allSelected ? '◻️ Bekor' : '☑️ Barchasi';
    }
}


async function fetchAndRenderTrash() {
    const container = document.getElementById('trash-list');
    if (!container) return;
    container.innerHTML = '<div class="empty-state"><p>Yuklanmoqda...</p></div>';
    try {
        const res = await apiFetch('/api/trash');
        if (!res.ok) throw new Error('Yuklab bo\'lmadi');
        trashState.items = await res.json();
        trashState.selected.clear();
        trashState.isSelecting = false;
        renderTrash();
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><p>${err.message}</p></div>`;
    }
}

// Korzinani tozalash uchun inline confirm paneli
function showPurgeConfirm() {
    const bar = document.getElementById('trash-purge-bar');
    if (!bar) return;
    bar.innerHTML = `
        <span class="purge-bar-text">⚠️ Ishonchingiz komilmi? Bu amalni bekor qilib bo'lmaydi!</span>
        <div style="display:flex;gap:8px;">
            <button id="btn-purge-cancel" class="btn btn-secondary btn-sm">Bekor</button>
            <button id="btn-purge-confirm" class="btn btn-danger btn-sm">Ha, tozala</button>
        </div>
    `;
    document.getElementById('btn-purge-cancel')?.addEventListener('click', hidePurgeConfirm);
    document.getElementById('btn-purge-confirm')?.addEventListener('click', executePurge);
}

function hidePurgeConfirm() {
    const bar = document.getElementById('trash-purge-bar');
    if (!bar) return;
    bar.innerHTML = `
        <span class="purge-bar-text">⚠️ Tozalangandan so'ng qayta tiklab bo'lmaydi</span>
        <button id="btn-purge-trash" class="btn btn-danger btn-sm">🗑 Korzinani Tozalash</button>
    `;
    document.getElementById('btn-purge-trash')?.addEventListener('click', showPurgeConfirm);
}

async function executePurge() {
    const bar = document.getElementById('trash-purge-bar');
    if (bar) bar.innerHTML = '<span class="purge-bar-text">Tozalanmoqda...</span>';
    try {
        const res = await apiFetch('/api/trash/purge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const json = await res.json();
        if (!res.ok || json.error) throw new Error(json.error || 'Xatolik');
        hapticSuccess();
        showToast(`🗑 ${json.deleted} ta yozuv butunlay o'chirildi`);
        exitTrashSelection();
        await Promise.all([
            fetchStats(),
            fetchSummaries(),
            fetchAndRenderTrash(),
            fetchAndRenderPaidDebts(),
        ]);
    } catch (err) {
        hapticError();
        showToast(`❌ ${err.message}`);
        hidePurgeConfirm();
    }
}

function setupTrashTab() {
    // "🔘 Tanlash" tugmasi
    document.getElementById('btn-trash-enter-select')?.addEventListener('click', () => {
        enterTrashSelection();
        hapticImpact();
    });

    // "✕ Bekor" tugmasi
    document.getElementById('btn-trash-cancel-select')?.addEventListener('click', () => {
        exitTrashSelection();
        hapticImpact();
    });

    // "☑️ Barchasi" tugmasi
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

            restoreBtn.disabled = true;
            restoreBtn.textContent = 'Qaytarilmoqda...';
            try {
                const res = await apiFetch('/api/trash/restore', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ debt_ids: ids }),
                });
                const json = await res.json();
                if (!res.ok || json.error) throw new Error(json.error || 'Xatolik');
                hapticSuccess();
                showToast(`✅ ${json.restored} ta qarz yopilganga qaytarildi`);
                exitTrashSelection();
                await Promise.all([
                    fetchStats(),
                    fetchSummaries(),
                    fetchAndRenderTrash(),
                    fetchAndRenderPaidDebts(),
                ]);
            } catch (err) {
                hapticError();
                showToast(`❌ ${err.message}`);
                restoreBtn.disabled = false;
                updateTrashToolbar();
            }
        });
    }

    // Purge tugmasi — inline confirm orqali
    document.getElementById('btn-purge-trash')?.addEventListener('click', showPurgeConfirm);
}




