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
    searchQuery: '',
    selectedClientReport: null,
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

// Barcha API so'rovlarini Telegram initData imzosi bilan yuboradi.
// Server imzoni tekshiradi — begona shaxs URLni bilsa ham ma'lumot ololmaydi.
function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (tg && tg.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }
    return fetch(url, { ...options, headers });
}

function showUnauthorizedState() {
    const container = document.getElementById('clients-list');
    if (container) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔒</div>
                <p>Ma'lumotlarni ko'rish uchun ilovani Telegram ichida oching</p>
            </div>
        `;
    }
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
// TAB 1: RENDER CLIENTS LIST & SEARCH/FILTER
// ==========================================

function renderClientsList() {
    const container = document.getElementById('clients-list');
    if (!container) return;

    let list = [...state.summaries];

    // Apply Filter Chips
    if (state.filter === 'debtors') {
        list = list.filter(item => item.has_debt);
    } else if (state.filter === 'paid') {
        list = list.filter(item => !item.has_debt);
    }

    // Apply Search Query
    if (state.searchQuery.trim()) {
        const q = state.searchQuery.toLowerCase().trim();
        list = list.filter(item =>
            item.full_name.toLowerCase().includes(q) ||
            item.phone.toLowerCase().includes(q)
        );
    }

    if (list.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📂</div>
                <p>Hech qanday mijoz topilmadi</p>
            </div>
        `;
        return;
    }

    container.innerHTML = list.map(item => `
        <div class="client-item-card" data-client-id="${item.id}">
            <div class="client-item-info">
                <div class="client-item-name">${escapeHtml(item.full_name)}</div>
                <div class="client-item-phone">${escapeHtml(item.phone)}</div>
            </div>
            <div class="client-item-meta">
                <div class="client-item-debt ${item.has_debt ? 'has-debt' : 'no-debt'}">
                    ${item.has_debt ? formatMoneyMap(item.remaining) : formatMoney(0)}
                </div>
                <span class="badge ${item.has_debt ? 'badge-danger' : 'badge-success'}">
                    ${item.has_debt ? '🔴 Qarzdor' : '🟢 Yopilgan'}
                </span>
            </div>
        </div>
    `).join('');

    // Attach click handlers to open modal
    container.querySelectorAll('.client-item-card').forEach(card => {
        card.addEventListener('click', () => {
            const clientId = card.getAttribute('data-client-id');
            openClientReportModal(clientId);
        });
    });
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
    const data = await fetchClientReport(clientId);
    if (!data || !modal) {
        showToast('Mijoz ma\'lumotlarini yuklab bo\'lmadi');
        return;
    }

    state.selectedClientReport = data;

    document.getElementById('modal-client-name').textContent = data.client.full_name;
    document.getElementById('modal-client-phone').textContent = data.client.phone;
    document.getElementById('modal-total-products').textContent = formatMoneyMap(data.total_product_price);
    document.getElementById('modal-total-paid').textContent = formatMoneyMap(sumMaps(data.total_paid_after, data.total_given_money));
    document.getElementById('modal-total-remaining').textContent = formatMoneyMap(data.total_remaining_debt);

    // Render Debts History — ko'p tovarli bo'lsa har bir tovarni alohida ko'rsatadi
    const debtsList = document.getElementById('modal-debts-list');
    if (data.debts.length === 0) {
        debtsList.innerHTML = '<p class="text-muted" style="font-size:13px;">Qarzlar mavjud emas</p>';
    } else {
        debtsList.innerHTML = data.debts.map(d => {
            const products = d.products || [];
            const hasMultiProducts = products.length > 1;
            const productListHtml = hasMultiProducts
                ? products.map((p, i) => `
                    <div class="history-card-detail" style="padding-left:4px;">
                        <span>  ${i + 1}. 📦 ${escapeHtml(p.name)}${p.quantity > 1 ? ` — ${p.quantity} × ${formatMoney(p.price_per_unit, d.currency)}` : ''}</span>
                        <span>${formatMoney(p.quantity * p.price_per_unit, d.currency)}</span>
                    </div>
                `).join('')
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
    const paymentsList = document.getElementById('modal-payments-list');
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
    if (data.total_remaining_debt <= 0) {
        payBtn.style.display = 'none';
    } else {
        payBtn.style.display = 'block';
    }

    modal.style.display = 'flex';
}

function closeClientReportModal() {
    const modal = document.getElementById('report-modal');
    if (modal) modal.style.display = 'none';
    state.selectedClientReport = null;
}

// ==========================================
// TAB 2: CREATE DEBT FORM — DINAMIK TOVARLAR
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
        if (name && price > 0) {
            products.push({ name, quantity: qty, price_per_unit: price });
        }
    });
    return products;
}

function getSelectedCurrency() {
    return document.querySelector('input[name="currency"]:checked')?.value || 'UZS';
}

function updateCreateCalculation() {
    const currency = getSelectedCurrency();
    const products = getProductsData();
    const totalProductPrice = products.reduce((sum, p) => sum + p.quantity * p.price_per_unit, 0);

    // Har bir guruhning subtotal'ini yangilaymiz
    const groups = getProductGroups();
    groups.forEach(group => {
        const qty = Math.max(1, Math.floor(Number(group.querySelector('.product-qty')?.value) || 1));
        const price = Math.floor(Number(group.querySelector('.product-price')?.value) || 0);
        const subtotal = qty * price;
        const subtotalEl = group.querySelector('.product-subtotal-val');
        if (subtotalEl) {
            subtotalEl.textContent = qty > 1
                ? `${qty} × ${formatMoney(price, currency)} = ${formatMoney(subtotal, currency)}`
                : formatMoney(price, currency);
        }
    });

    const exchangeToggle = document.getElementById('create-exchange-toggle');
    const exchangePriceInput = document.getElementById('create-exchange-price');
    const givenToggle = document.getElementById('create-given-toggle');
    const givenAmountInput = document.getElementById('create-given-amount');

    const hasExchange = exchangeToggle?.checked;
    const exchangePrice = hasExchange ? (Number(exchangePriceInput?.value) || 0) : 0;
    const hasGiven = givenToggle?.checked;
    const givenAmount = hasGiven ? (Number(givenAmountInput?.value) || 0) : 0;

    const productCalcEl = document.getElementById('calc-product-price');
    if (productCalcEl) {
        if (products.length === 1) {
            const p = products[0];
            productCalcEl.textContent = p.quantity > 1
                ? `${p.quantity} × ${formatMoney(p.price_per_unit, currency)} = ${formatMoney(totalProductPrice, currency)}`
                : formatMoney(p.price_per_unit, currency);
        } else {
            productCalcEl.textContent = `${products.length} ta tovar = ${formatMoney(totalProductPrice, currency)}`;
        }
    }

    const exRow = document.getElementById('calc-exchange-row');
    if (exRow) {
        exRow.style.display = hasExchange ? 'flex' : 'none';
        document.getElementById('calc-exchange-price').textContent = `-${formatMoney(exchangePrice, currency)}`;
    }

    const givenRow = document.getElementById('calc-given-row');
    if (givenRow) {
        givenRow.style.display = hasGiven ? 'flex' : 'none';
        document.getElementById('calc-given-price').textContent = `-${formatMoney(givenAmount, currency)}`;
    }

    const totalDebt = Math.max(0, totalProductPrice - exchangePrice - givenAmount);
    document.getElementById('calc-total-debt').textContent = formatMoney(totalDebt, currency);
}

function attachProductGroupListeners(container) {
    // Narx/miqdor o'zgarganda subtotal + grand total yangilanadi
    container.querySelectorAll('.product-qty, .product-price, .product-name').forEach(el => {
        el.addEventListener('input', updateCreateCalculation);
    });
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

            // Yangi tovar nomi maydoniga foküs
            const nameInput = newGroup.querySelector('.product-name');
            if (nameInput) nameInput.focus();
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

    // Valyuta tanlanganda live hisob yangilanadi
    document.querySelectorAll('input[name="currency"]').forEach(radio => {
        radio.addEventListener('change', () => {
            updateCreateCalculation();
            hapticImpact();
        });
    });

    // Exchange/given input'lari
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
            const exchangePrice = hasExchange ? (Number(exchangePriceInput?.value) || 0) : 0;

            const hasGiven = givenToggle?.checked || false;
            const givenMoney = hasGiven ? (Number(givenAmountInput?.value) || 0) : 0;

            if (!clientName) {
                showToast('Mijoz ismini kiriting');
                return;
            }
            if (!clientPhone) {
                showToast('Telefon raqamini kiriting');
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
            const totalProductPrice = products.reduce((s, p) => s + p.quantity * p.price_per_unit, 0);
            if (exchangePrice + givenMoney > totalProductPrice) {
                showToast('Exchange va berilgan pul tovarlar jami narxidan oshmasligi kerak');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Saqlanmoqda...';

            try {
                const payload = {
                    client_name: clientName,
                    client_phone: clientPhone,
                    debt_date: debtDate,
                    products: products,
                    currency: getSelectedCurrency(),
                    exchange_exists: hasExchange,
                    exchange_product_name: exchangeName,
                    exchange_product_price: exchangePrice,
                    given_money: givenMoney,
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
                showToast('✅ Qarz muvaffaqiyatli saqlandi!');

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
                // Valyutani UZSga qaytarish
                const uzsRadio = document.querySelector('input[name="currency"][value="UZS"]');
                if (uzsRadio) uzsRadio.checked = true;

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
    const infoCard = document.getElementById('pay-client-info-card');
    const optionsWrapper = document.getElementById('pay-options-wrapper');
    const radioModes = document.querySelectorAll('input[name="payment_mode"]');
    const partialGroup = document.getElementById('partial-amount-group');
    const partialInput = document.getElementById('pay-partial-amount');
    const previewAmount = document.getElementById('pay-preview-amount');
    const previewRemaining = document.getElementById('pay-preview-remaining');
    const submitBtn = document.getElementById('btn-submit-payment');

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

    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const clientId = Number(select?.value) || 0;
            const mode = document.querySelector('input[name="payment_mode"]:checked')?.value || 'full';
            const currency = getPaymentCurrency();
            const opt = select?.selectedOptions[0];
            const totalDebt = getSelectedDebtInCurrency(opt, currency);

            if (!clientId) {
                showToast('Qarzdor mijozni tanlang');
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
                        payment_date: getTodayFormatted(),
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
}

// ==========================================
// EVENT LISTENERS INITIALIZATION
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    // Bottom Nav Tabs
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            switchTab(tabId);
            hapticImpact();
        });
    });

    // Refresh Button
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.classList.add('rotating');
            hapticImpact();
            await Promise.all([fetchStats(), fetchSummaries()]);
            setTimeout(() => refreshBtn.classList.remove('rotating'), 600);
            showToast('Yangilandi');
        });
    }

    // Search Input
    const searchInput = document.getElementById('table-search-input');
    const clearSearchBtn = document.getElementById('clear-search-btn');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            state.searchQuery = e.target.value;
            if (clearSearchBtn) clearSearchBtn.style.display = state.searchQuery ? 'block' : 'none';
            renderClientsList();
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

    // Setup forms
    setupCreateForm();
    setupPaymentForm();

    // Initial Fetch
    fetchStats();
    fetchSummaries();
});
